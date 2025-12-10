#!/usr/bin/env python3
"""
Descriptor models for declarative services.

These dataclasses define a minimal, dependency-free schema for authoring
JSON descriptors that describe simple, single-request-or-few-requests
service checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Signal:
    type: str  # "status" | "json_path" | "regex"
    equals: Optional[str] = None
    path: Optional[str] = None
    pattern: Optional[str] = None
    weight: float = 0.5  # normalized (0..1); runtime scales to 0..100


@dataclass
class Retry:
    max_retries: int = 0
    backoff_ms: int = 0


@dataclass
class Endpoint:
    name: str
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    query: Dict[str, str] = field(default_factory=dict)
    body: Dict[str, str] = field(default_factory=dict)
    success_signals: List[Signal] = field(default_factory=list)
    failure_signals: List[Signal] = field(default_factory=list)
    retry: Retry = field(default_factory=Retry)


@dataclass
class ServiceDescriptor:
    schema_version: int
    service_key: str
    display_name: str
    description: str = ""
    requires_proxy: bool = False
    max_threads: int = 1
    timeouts: Dict[str, int] = field(default_factory=dict)  # e.g., {"request": 10}
    rate_limits: Dict[str, int] = field(default_factory=dict)  # e.g., {"rpm": 30, "burst": 5}
    recommended_delay: Optional[int] = None  # seconds (optional)
    endpoints: List[Endpoint] = field(default_factory=list)


def _coerce_signal(obj: dict) -> Signal:
    return Signal(
        type=str(obj.get("type", "status")),
        equals=obj.get("equals"),
        path=obj.get("path"),
        pattern=obj.get("pattern"),
        weight=float(obj.get("weight", 0.5)),
    )


def _coerce_retry(obj: Optional[dict]) -> Retry:
    if not obj:
        return Retry()
    return Retry(
        max_retries=int(obj.get("max_retries", 0)),
        backoff_ms=int(obj.get("backoff_ms", 0)),
    )


def _coerce_endpoint(obj: dict) -> Endpoint:
    return Endpoint(
        name=str(obj.get("name", "step")),
        method=str(obj.get("method", "GET")).upper(),
        url=str(obj["url"]),
        headers=dict(obj.get("headers", {})),
        query=dict(obj.get("query", {})),
        body=dict(obj.get("body", {})),
        success_signals=[_coerce_signal(s) for s in obj.get("success_signals", [])],
        failure_signals=[_coerce_signal(s) for s in obj.get("failure_signals", [])],
        retry=_coerce_retry(obj.get("retry")),
    )


def from_dict(data: dict) -> ServiceDescriptor:
    """Create a ServiceDescriptor from a dict with minimal validation."""
    schema_version = int(data.get("schema_version", 1))
    service_key = str(data["service_key"]).strip()
    display_name = str(data.get("display_name", service_key)).strip()
    desc = str(data.get("description", "")).strip()
    requires_proxy = bool(data.get("requires_proxy", False))
    max_threads = int(data.get("max_threads", 1))
    timeouts = dict(data.get("timeouts", {}))
    rate_limits = dict(data.get("rate_limits", {}))
    recommended_delay = data.get("recommended_delay")
    eps = [
        _coerce_endpoint(e)
        for e in data.get("endpoints", [])
        if isinstance(e, dict) and e.get("url")
    ]

    return ServiceDescriptor(
        schema_version=schema_version,
        service_key=service_key,
        display_name=display_name,
        description=desc,
        requires_proxy=requires_proxy,
        max_threads=max_threads,
        timeouts=timeouts,
        rate_limits=rate_limits,
        recommended_delay=int(recommended_delay) if recommended_delay is not None else None,
        endpoints=eps,
    )
