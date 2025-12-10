#!/usr/bin/env python3
"""
Plugin API and discovery utilities for Tessera-2600.

External services can register via Python entry points under:
  entry_points = { 'tessera.services': [ 'key = pkg.module:ServiceClass' ] }

This module exposes discovery functions and a small, stable programmatic API
that tools or UI wrappers can use without going through the CLI. The intent is
to provide a minimal facade over Tessera's internals without re‑implementing
core logic.

Contracts for external ServiceClass implementations (plugins):
- Constructor accepts keyword args: proxy_list: Optional[List[str]], timeout: int
- Property/attribute: service_name (human‑readable string)
- Method: check_phone_number(phone: str) -> str (legacy status string)

Returned results are normalized to core.models.CheckResult.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Type

from tessera_2600.core.adapters import to_check_result
from tessera_2600.core.models import CheckResult

# Bump when programmatic surface changes (additive, backward compatible)
PLUGIN_API_VERSION = "1.1"


def discover_service_plugins() -> Dict[str, Type]:
    """Discover external service plugins registered under 'tessera.services'.

    Returns a mapping of service_key -> ServiceClass. Any failure in discovery
    is swallowed to keep the core functional.
    """
    services: Dict[str, Type] = {}
    try:
        try:
            # Python 3.10+
            from importlib.metadata import entry_points  # type: ignore
            eps = entry_points()
            entries = eps.select(group='tessera.services') if hasattr(eps, 'select') else eps.get('tessera.services', [])
        except Exception:
            # Python 3.8/3.9 fallback
            from importlib_metadata import entry_points  # type: ignore
            eps = entry_points(group='tessera.services')
            entries = eps

        for ep in entries:
            try:
                key = ep.name
                obj = ep.load()
                # Expect obj to be a class; if it is a factory, call to get class
                if isinstance(obj, type):
                    services[key] = obj
                else:
                    maybe_cls = obj() if callable(obj) else None
                    if isinstance(maybe_cls, type):
                        services[key] = maybe_cls
            except Exception:
                # Ignore individual plugin load failures
                continue
    except Exception:
        pass
    return services


# -------- Public programmatic API (for tools/UI wrappers) --------------------

def get_api_version() -> str:
    """Return the Plugin API version string."""
    return PLUGIN_API_VERSION


def list_services(include_plugins: bool = True) -> Dict[str, Dict[str, Any]]:
    """List available services with basic metadata.

    Returns a mapping of service_key -> info dict. Built‑in descriptor services
    come from tessera_2600.services.SERVICE_CONFIGURATIONS. If include_plugins is True, any
    discovered entry‑point services are also included with minimal metadata.
    """
    from tessera_2600.services import SERVICE_CONFIGURATIONS  # local import to avoid cycles at import time

    listing: Dict[str, Dict[str, Any]] = {}
    # Built‑in/descriptor services
    for key, cfg in SERVICE_CONFIGURATIONS.items():
        listing[key] = {
            **cfg,
            'origin': 'builtin',
        }

    if include_plugins:
        for key, cls in discover_service_plugins().items():
            if key not in listing:
                # Best‑effort introspection of plugin metadata
                name = getattr(cls, 'service_name', None) or getattr(cls, 'SERVICE_NAME', None) or key
                listing[key] = {
                    'name': str(name),
                    'description': 'External plugin service',
                    'type': 'plugin',
                    'requires_proxy': bool(getattr(cls, 'REQUIRES_PROXY', False)),
                    'recommended_delay': int(getattr(cls, 'RECOMMENDED_DELAY', 0)),
                    'max_requests_per_minute': int(getattr(cls, 'MAX_RPM', 0)),
                    'aliases': [str(name)] if isinstance(name, str) else [],
                    'origin': 'plugin',
                }

    return listing


def service_info(service_key: str) -> Optional[Dict[str, Any]]:
    """Get info for a specific service key (accepts aliases for built‑ins)."""
    from tessera_2600.services import get_service_info, resolve_service_key

    info = get_service_info(service_key)
    if info:
        # Ensure origin field for built‑ins
        return {**info, 'origin': 'builtin'}

    # Check plugins (no aliasing for external keys)
    plugins = discover_service_plugins()
    if service_key in plugins:
        cls = plugins[service_key]
        name = getattr(cls, 'service_name', None) or getattr(cls, 'SERVICE_NAME', None) or service_key
        return {
            'name': str(name),
            'description': 'External plugin service',
            'type': 'plugin',
            'requires_proxy': bool(getattr(cls, 'REQUIRES_PROXY', False)),
            'recommended_delay': int(getattr(cls, 'RECOMMENDED_DELAY', 0)),
            'max_requests_per_minute': int(getattr(cls, 'MAX_RPM', 0)),
            'aliases': [str(name)] if isinstance(name, str) else [],
            'origin': 'plugin',
        }

    # Try resolving alias to canonical (might have been a builtin alias)
    canonical = resolve_service_key(service_key)
    if canonical and canonical != service_key:
        info = get_service_info(canonical)
        if info:
            return {**info, 'origin': 'builtin'}
    return None


def create_service_instance(service_key: str, proxy_list: Optional[List[str]] = None, timeout: int = 5):
    """Create a service instance by key for programmatic use.

    For built‑in descriptor services, use services.create_service. For plugin
    services discovered via entry points, instantiates the class directly.
    """
    from tessera_2600.services import SERVICE_REGISTRY, resolve_service_key, create_service as _create

    canonical = resolve_service_key(service_key) or service_key
    if canonical in SERVICE_REGISTRY:
        return _create(canonical, proxy_list=proxy_list or [], timeout=timeout)

    plugins = discover_service_plugins()
    if canonical in plugins:
        cls = plugins[canonical]
        return cls(proxy_list=proxy_list or [], timeout=timeout)

    raise ValueError(f"Unknown service '{service_key}'.")


def check_phone(service_key: str, phone: str, proxy_list: Optional[List[str]] = None, timeout: int = 5) -> CheckResult:
    """Check a single phone with a single service and return a CheckResult."""
    svc = create_service_instance(service_key, proxy_list=proxy_list, timeout=timeout)
    # Fallback name if attribute not present
    service_name = getattr(svc, 'service_name', None) or str(service_key)
    legacy = svc.check_phone_number(phone)
    return to_check_result(service_name, phone, legacy)


def iter_check(phones: Iterable[str], services_keys: Optional[List[str]] = None,
               proxy_list: Optional[List[str]] = None, timeout: int = 5) -> Iterator[CheckResult]:
    """Iterate over checks for provided phones and services, yielding CheckResult.

    Execution is sequential and conservative by default to be safe for wrappers.
    Callers can implement their own concurrency if needed.
    """
    from tessera_2600.services import validate_services

    enabled = validate_services(services_keys) if services_keys else None
    # If None, validate_services(None) returns all available services
    if enabled is None:
        from tessera_2600.services import validate_services as _validate
        enabled = _validate(None)

    for phone in phones:
        for key in enabled:
            try:
                yield check_phone(key, phone, proxy_list=proxy_list, timeout=timeout)
            except Exception as e:
                # Ensure a result is yielded for each attempt
                yield CheckResult(
                    service=key,
                    phone=phone,
                    status="error",
                    details={"exception": str(e)},
                    error=str(e),
                )
