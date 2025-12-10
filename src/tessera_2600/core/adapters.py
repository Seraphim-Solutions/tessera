#!/usr/bin/env python3
"""
Adapters to map legacy service string results to structured models.
"""

from __future__ import annotations

from typing import Dict, Any
import time

from tessera_2600.core.models import CheckResult, Status


def parse_legacy_status(result_str: str) -> Status:
    s = result_str.lower() if result_str else ""
    if "[found]" in s:
        return "found"
    if "[not found]" in s or "not found" in s:
        return "not_found"
    if "rate limited" in s or "429" in s:
        return "rate_limited"
    if "invalid" in s:
        return "invalid"
    if "error" in s or "blocked" in s:
        return "error"
    return "unknown"


def to_check_result(service_name: str, phone: str, legacy_result: str) -> CheckResult:
    status = parse_legacy_status(legacy_result)
    details: Dict[str, Any] = {"raw": legacy_result}
    error = None
    if status == "error":
        error = legacy_result
    return CheckResult(service=service_name, phone=phone, status=status, details=details, ts=time.time(), error=error)
