#!/usr/bin/env python3
"""
Services Package

Dynamic service registration and lookup (descriptor-only).

Goals:
- Avoid hard-coded imports/registrations.
- Allow flexible service naming (case/format variations) when users specify
  services on the CLI.
- Keep implementation simple by using JSON/YAML descriptors only.

Descriptor source resolution rules when duplicates exist (same basename):
- Prefer JSON (.json) over YAML (.yaml/.yml).
- YAML files are only considered if PyYAML is installed.
- When multiple files exist for the same basename, a warning is logged and the
  selected file path is recorded for display in the CLI.
"""

from tessera_2600.core.declarative_service import DeclarativeService
from tessera_2600.core.descriptor_models import from_dict as descriptor_from_dict, ServiceDescriptor
import os
import json
from typing import Optional
import re
import logging

# Optional YAML support for descriptors (.yaml/.yml)
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore

# Service registry for easy access. Everything is dynamic via descriptors only.
SERVICE_REGISTRY = {}

# Service metadata/configurations (populated dynamically from descriptors)
SERVICE_CONFIGURATIONS = {}

# Selected descriptors (after resolving duplicates)
DESCRIPTOR_REGISTRY = {}

# Track descriptor source paths and duplicates for transparency in CLI
DESCRIPTOR_SOURCES = {}
_DUPLICATE_WARNINGS = []

logger = logging.getLogger(__name__)
try:
    # Collect descriptor search directories: package defaults plus any extras from env
    _desc_dir = os.path.join(os.path.dirname(__file__), 'descriptors')
    _search_dirs = []
    if os.path.isdir(_desc_dir):
        _search_dirs.append(_desc_dir)
    # Allow injecting additional descriptor directories via env (path-separated)
    # e.g., TESSERA_EXTRA_DESCRIPTOR_DIRS="/path/to/repo/src/tessera_2600/services/descriptors"
    _extra = os.environ.get('TESSERA_EXTRA_DESCRIPTOR_DIRS') or os.environ.get('TESSERA_DESCRIPTOR_DIRS')
    if _extra:
        for d in _extra.split(os.path.pathsep):
            d = d.strip()
            if d and os.path.isdir(d):
                _search_dirs.append(d)

    if _search_dirs:
        # Group files by base name to detect duplicates regardless of YAML availability
        groups = {}
        for d in _search_dirs:
            try:
                files = [f for f in os.listdir(d) if f.lower().endswith(('.json', '.yaml', '.yml'))]
            except Exception:
                files = []
            for fname in files:
                base, ext = os.path.splitext(fname)
                groups.setdefault(base, []).append((os.path.join(d, fname), ext.lower()))

        def _parse_descriptor(path: str) -> Optional[ServiceDescriptor]:
            try:
                if path.endswith('.json'):
                    with open(path, 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                elif (path.endswith('.yaml') or path.endswith('.yml')) and yaml is not None:
                    with open(path, 'r', encoding='utf-8') as fh:
                        data = yaml.safe_load(fh)
                else:
                    return None
                if not isinstance(data, dict):
                    logger.warning(f"Descriptor file is not a mapping: {os.path.basename(path)}")
                    return None
                return descriptor_from_dict(data)
            except Exception as e:
                # Make descriptor loading failures visible to help diagnose why a service is missing
                logger.warning(f"Failed to parse descriptor '{os.path.basename(path)}': {e}")
                return None

        # Resolve per-group selection with priority: .json > .yaml/.yml
        for base, abs_candidates in groups.items():
            
            # Prefer JSON
            json_candidates = [p for p, ext in abs_candidates if ext == '.json']
            yaml_candidates = [p for p, ext in abs_candidates if ext in ('.yaml', '.yml')]

            selected_path: Optional[str] = None
            considered = []

            if json_candidates:
                selected_path = sorted(json_candidates)[0]
                considered = sorted([os.path.basename(p) for p in json_candidates + yaml_candidates])
            elif yaml is not None and yaml_candidates:
                selected_path = sorted(yaml_candidates)[0]
                considered = sorted([os.path.basename(p) for p in yaml_candidates])
            else:
                # Only YAML present but PyYAML not installed; skip with notice
                if yaml_candidates:
                    warning = (
                        f"Descriptor '{base}' has only YAML candidates but PyYAML is not installed; "
                        f"files ignored: {', '.join(sorted(os.path.basename(p) for p in yaml_candidates))}"
                    )
                    _DUPLICATE_WARNINGS.append(warning)
                    logger.warning(warning)
                continue

            # Warn if duplicates exist for this base
            if len(abs_candidates) > 1:
                warning = (
                    f"Multiple descriptor files for service '{base}': {', '.join(sorted(os.path.basename(p) for p, _ in abs_candidates))}. "
                    f"Selected '{os.path.basename(selected_path)}' (JSON preferred)."
                )
                _DUPLICATE_WARNINGS.append(warning)
                logger.warning(warning)

            # Parse the selected descriptor
            desc = _parse_descriptor(selected_path)
            if not desc:
                continue

            key = desc.service_key
            DESCRIPTOR_REGISTRY[key] = desc
            DESCRIPTOR_SOURCES[key] = {
                'selected_path': selected_path,
                'selected_file': os.path.basename(selected_path),
                'candidates': [p for p, _ in abs_candidates],
            }

            # Expose every descriptor as a service
            if key not in SERVICE_REGISTRY:
                SERVICE_REGISTRY[key] = DeclarativeService  # factory will pass descriptor
                # Add minimal configuration for CLI/help surfaces
                SERVICE_CONFIGURATIONS[key] = {
                    'name': desc.display_name,
                    'description': desc.description or 'Declarative service',
                    'country': 'Global',
                    'type': 'generic',
                    'max_requests_per_minute': desc.rate_limits.get('rpm', 0) if desc.rate_limits else 0,
                    'recommended_delay': desc.recommended_delay or 0,
                    'requires_proxy': bool(desc.requires_proxy),
                    'proxy_recommended': bool(desc.requires_proxy),
                    'rate_limit_severity': 'medium',
                    # include normalized display name as an alias for lookup
                    'aliases': [desc.display_name],
                    # descriptor file info for CLI display
                    'descriptor_file': os.path.basename(selected_path),
                    'descriptor_path': selected_path,
                }
except Exception:
    # Descriptor loading is optional; ignore failures entirely
    DESCRIPTOR_REGISTRY = {}


# --- Flexible name handling -------------------------------------------------

def _normalize_name(name: str) -> str:
    """Normalize user-provided service names for flexible matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _build_name_index():
    """Build a mapping of normalized names to canonical service keys."""
    index = {}
    for key, cfg in SERVICE_CONFIGURATIONS.items():
        # Map canonical key
        index[_normalize_name(key)] = key
        # Map configured name
        human = cfg.get('name')
        if isinstance(human, str):
            index[_normalize_name(human)] = key
        # Map aliases
        for alias in cfg.get('aliases', []) or []:
            if isinstance(alias, str):
                index[_normalize_name(alias)] = key
        # Convenience: if key ends with country code like 'seznamcz', also map without suffix
        m = re.match(r"^([a-z]+)[a-z]{2}$", key)
        if m:
            index[_normalize_name(m.group(1))] = key
    # Also include descriptor keys that don't have explicit config
    for key, desc in DESCRIPTOR_REGISTRY.items():
        if _normalize_name(key) not in index:
            index[_normalize_name(key)] = key
        dn = getattr(desc, 'display_name', None)
        if isinstance(dn, str):
            index[_normalize_name(dn)] = key
    return index


_NAME_INDEX = _build_name_index()


def resolve_service_key(name_or_key: str) -> Optional[str]:
    """Resolve a user-provided service identifier to a canonical key."""
    if not name_or_key:
        return None
    # Fast path exact match
    if name_or_key in SERVICE_REGISTRY:
        return name_or_key
    return _NAME_INDEX.get(_normalize_name(name_or_key))

def create_service(service_key, *args, **kwargs):
    """Factory function to create a service instance by key (descriptor-only).

    Instantiates DeclarativeService and passes the loaded ServiceDescriptor.
    """
    # Allow flexible identifiers
    canonical = resolve_service_key(service_key) or service_key
    service_cls = SERVICE_REGISTRY.get(canonical)
    if not service_cls:
        raise ValueError(f"Service '{service_key}' is not registered.")
    # If this is a descriptor-only service, construct DeclarativeService with descriptor
    if service_cls is DeclarativeService and canonical in DESCRIPTOR_REGISTRY:
        descriptor = DESCRIPTOR_REGISTRY[canonical]
        return DeclarativeService(descriptor=descriptor, **kwargs)
    return service_cls(*args, **kwargs)

def validate_services(service_list=None):
    """
    Validate service list and return valid services.
    If no list provided, returns all available services.
    """
    if service_list is None:
        return list(SERVICE_REGISTRY.keys())
    
    valid_services = []
    for service in service_list:
        canonical = resolve_service_key(service)
        if canonical in SERVICE_REGISTRY:
            valid_services.append(canonical)
        else:
            print(f"Warning: Unknown service '{service}'. Available services: {', '.join(SERVICE_REGISTRY.keys())}")
    
    return valid_services

def get_service_info(service_key):
    """Get configuration info for a service (accepts aliases)."""
    canonical = resolve_service_key(service_key) or service_key
    return SERVICE_CONFIGURATIONS.get(canonical)

def get_descriptor_source(service_key):
    """Return descriptor source information for a given service key (accepts aliases).

    Returns a dict like:
    {
        'selected_path': '/abs/path/services/descriptors/seznamcz.json',
        'selected_file': 'seznamcz.json',
        'candidates': ['/abs/.../seznamcz.json', '/abs/.../seznamcz.yaml']
    }
    or None if not a descriptor-backed service or info unavailable.
    """
    canonical = resolve_service_key(service_key) or service_key
    return DESCRIPTOR_SOURCES.get(canonical)

def get_duplicate_warnings():
    """Expose any duplicate/selection warnings captured during descriptor loading."""
    return list(_DUPLICATE_WARNINGS)

def get_proxy_required_services(service_list=None):
    """Get list of services that require proxies."""
    services_to_check = service_list or SERVICE_REGISTRY.keys()
    # Normalize any provided identifiers
    services_to_check = [resolve_service_key(s) or s for s in services_to_check]
    return [
        service for service in services_to_check 
        if service in SERVICE_CONFIGURATIONS and SERVICE_CONFIGURATIONS[service].get('requires_proxy', False)
    ]

def get_max_recommended_delay(service_list=None):
    """Get maximum recommended delay for a list of services."""
    services_to_check = service_list or SERVICE_REGISTRY.keys()
    services_to_check = [resolve_service_key(s) or s for s in services_to_check]
    max_delay = 0
    
    for service in services_to_check:
        if service in SERVICE_CONFIGURATIONS:
            delay = SERVICE_CONFIGURATIONS[service]['recommended_delay']
            max_delay = max(max_delay, delay)
    
    return max_delay