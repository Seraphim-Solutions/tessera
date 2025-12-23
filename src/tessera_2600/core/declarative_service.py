#!/usr/bin/env python3
"""
DeclarativeService executes simple service checks defined via JSON/YAML descriptors.
"""

from __future__ import annotations

import re
import time
import logging
from typing import Any, Dict, Optional
import os

import requests
import importlib

from tessera_2600.core.descriptor_models import ServiceDescriptor, Endpoint
from tessera_2600.core.proxy_manager import ProxyManager
from tessera_2600.config import CONFIRMATION_THRESHOLD, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class DeclarativeService:
    """Runtime for descriptor-defined services (no BaseService dependency)."""

    def __init__(self, descriptor: ServiceDescriptor, proxy_list=None, timeout: int = 5):
        self.descriptor = descriptor
        self.proxy_list = list(proxy_list or [])
        self._proxy_manager: Optional[ProxyManager] = (
            ProxyManager(self.proxy_list) if self.proxy_list else None
        )
        self._last_proxy_url: Optional[str] = None

        # Session and timeouts
        self.session = requests.Session()
        self._setup_session()
        effective_timeout = int(descriptor.timeouts.get("request", timeout or REQUEST_TIMEOUT))
        self.timeout = max(effective_timeout, 1)

    # --- Compatibility properties used by checker/adapters ---
    @property
    def service_name(self) -> str:
        return self.descriptor.display_name

    @property
    def requires_proxy(self) -> bool:
        return bool(self.descriptor.requires_proxy)

    @property
    def recommended_delay(self) -> int:
        # If descriptor specifies, otherwise conservative 2s
        return int(self.descriptor.recommended_delay or 2)

    # --- Session / Proxy helpers (inline, replacing BaseService bits) ---
    def _setup_session(self):
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        )

    def _get_proxy(self) -> Optional[Dict[str, str]]:
        if self._proxy_manager:
            proxy_url = self._proxy_manager.get_available_proxy()
            if proxy_url:
                self._last_proxy_url = proxy_url
                logger.debug(f"Using proxy: {proxy_url}")
                return {"http": proxy_url, "https": proxy_url}
        self._last_proxy_url = None
        return None

    def _report_rate_limit(self):
        if self._proxy_manager and self._last_proxy_url:
            self._proxy_manager.report_rate_limit(self._last_proxy_url)

    def _report_error(self):
        if self._proxy_manager and self._last_proxy_url:
            self._proxy_manager.report_error(self._last_proxy_url)

    # --- Descriptor execution helpers ---
    def render(self, template: str, ctx: Dict[str, Any]) -> str:
        if not isinstance(template, str):
            return template
        out = template
        for k, v in ctx.items():
            out = out.replace(f"${{{k}}}", str(v))
        return out

    def _load_signer(self, spec: str):
        """Load a signer callable from a string spec 'module:attr' or 'module.func'."""
        if not spec:
            return None
        module_path = spec
        attr = None
        if ':' in spec:
            module_path, attr = spec.split(':', 1)
        elif '.' in spec:
            # Try to split on last dot as module.attr
            parts = spec.rsplit('.', 1)
            if len(parts) == 2:
                module_path, attr = parts
        mod = importlib.import_module(module_path)
        return getattr(mod, attr) if attr else mod

    def _evaluate_signals(self, ep: Endpoint, resp: requests.Response) -> float:
        score = 0.0
        text = resp.text or ""
        try:
            data = resp.json()
        except Exception:
            data = None

        def add_if(cond: bool, weight: float, sign: int = 1):
            nonlocal score
            if cond:
                score += sign * (weight * 100.0)  # scale to 0..100

        for s in ep.success_signals:
            if s.type == "status" and s.equals is not None:
                add_if(str(resp.status_code) == str(s.equals), s.weight)
            elif s.type == "json_path" and data is not None and s.path and s.equals is not None:
                key = s.path.lstrip("$.")
                if isinstance(data, dict):
                    add_if(data.get(key) == s.equals, s.weight)
            elif s.type == "regex" and s.pattern:
                add_if(re.search(s.pattern, text) is not None, s.weight)

        for s in ep.failure_signals:
            if s.type == "status" and s.equals is not None:
                add_if(str(resp.status_code) == str(s.equals), s.weight, sign=-1)
            elif s.type == "json_path" and data is not None and s.path and s.equals is not None:
                key = s.path.lstrip("$.")
                if isinstance(data, dict):
                    add_if(data.get(key) == s.equals, s.weight, sign=-1)
            elif s.type == "regex" and s.pattern:
                add_if(re.search(s.pattern, text) is not None, s.weight, sign=-1)

        return score

    def check_phone_number(self, phone_number: str) -> str:
        # Context available to templates
        ctx = {"phone": phone_number}
        confidence = 0.0
        last_status: Optional[int] = None

        for ep in self.descriptor.endpoints:
            tries = 0
            while True:
                tries += 1
                # Render URL, headers, body
                url = self.render(ep.url, ctx)
                headers = {k: self.render(v, ctx) for k, v in ep.headers.items()}
                body = {k: self.render(v, ctx) for k, v in ep.body.items()}
                params = {k: self.render(v, ctx) for k, v in ep.query.items()}

                # Apply optional signer hook for request mutation
                if getattr(ep, 'signer', None):
                    try:
                        signer = self._load_signer(ep.signer)  # type: ignore[attr-defined]
                        if callable(signer):
                            headers, params, body = signer(headers, params, body, ctx, **getattr(ep, 'signer_params', {}))  # type: ignore
                    except Exception as _e:
                        self._report_error()
                        return f"[ERROR]: Signer failed: {_e}"

                proxy = self._get_proxy()
                timeout = int(self.descriptor.timeouts.get("request", self.timeout))
                method = ep.method.upper()

                try:
                    resp = self.session.request(
                        method,
                        url,
                        headers=headers,
                        params=params or None,
                        data=body or None,
                        proxies=proxy,
                        timeout=max(timeout, 1),
                    )
                    last_status = resp.status_code
                    score = self._evaluate_signals(ep, resp)
                    confidence += score
                    try:
                        preview = (resp.text or "")[:200].replace("\n", " ")
                    except Exception:
                        preview = "<no preview>"
                    line = (
                        f"Descriptor {self.descriptor.service_key}/{ep.name}: "
                        f"status={last_status}, score_add={score}, total_conf={confidence}, preview={preview!r}"
                    )
                    logger.info(line)
                    # Optional hard print for environments where logging is captured/hidden
                    if os.environ.get("TESSERA_DEBUG_REQUESTS") == "1":
                        try:
                            print(line, flush=True)
                        except Exception:
                            pass
                except requests.exceptions.Timeout:
                    self._report_error()
                    return "[ERROR]: Request timeout"
                except requests.exceptions.ProxyError:
                    self._report_error()
                    return "[ERROR]: Proxy connection failed"
                except requests.exceptions.ConnectionError:
                    self._report_error()
                    return "[ERROR]: Connection failed"
                except Exception as e:
                    self._report_error()
                    return f"[ERROR]: {e}"

                if confidence >= CONFIRMATION_THRESHOLD:
                    return "[FOUND]: Confirmed by descriptor signals"

                # Retry policy: only retry on transient conditions (429 or 5xx).
                # Do NOT retry on 2xx/4xx outcomes as those are typically definitive and
                # introduce unnecessary delays (e.g., 200 with exists=false, or 404).
                should_retry = False
                if tries <= (ep.retry.max_retries or 0):
                    if last_status == 429 or (last_status is not None and 500 <= int(last_status) < 600):
                        should_retry = True

                if not should_retry:
                    break

                time.sleep((ep.retry.backoff_ms or 0) / 1000.0)

        # Decide final legacy string outcome
        if confidence >= CONFIRMATION_THRESHOLD:
            return "[FOUND]: Confirmed by descriptor signals"
        # Heuristics: if we have any positive signal but below threshold
        if confidence > 0:
            return "[UNKNOWN]: Signals inconclusive"
        # Negative or none
        if last_status == 429:
            self._report_rate_limit()
            return "[RATE LIMITED]: Too many requests"
        return "[NOT FOUND]: No signals matched"
