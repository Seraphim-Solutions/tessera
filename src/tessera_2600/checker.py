#!/usr/bin/env python3
"""
Social Media Checker Module
Main checker class that orchestrates service calls.
"""

import logging
from typing import List, Dict, Optional
from tessera_2600.core.adapters import to_check_result
from tessera_2600.core.models import CheckResult
from tessera_2600.services import SERVICE_REGISTRY, SERVICE_CONFIGURATIONS, create_service, validate_services

logger = logging.getLogger(__name__)

class SocialMediaChecker:
    """Main checker class that coordinates service calls."""
    
    def __init__(self, proxy_list: Optional[List[str]] = None, timeout: int = 5, 
                 enabled_services: Optional[List[str]] = None):
        self.proxy_list = proxy_list or []
        self.timeout = timeout
        self.enabled_services = enabled_services or list(SERVICE_REGISTRY.keys())
        self.services = {}
        
        # Validate and initialize services
        self.enabled_services = validate_services(self.enabled_services)
        self._initialize_services()
        
        logger.info(f"Initialized checker with {len(self.proxy_list)} proxies")
        logger.info(f"Enabled services: {', '.join(self.enabled_services)}")
    
    def _initialize_services(self):
        """Initialize service instances."""
        for service_key in self.enabled_services:
            try:
                self.services[service_key] = create_service(
                    service_key, 
                    proxy_list=self.proxy_list, 
                    timeout=self.timeout
                )
                logger.debug(f"Initialized {service_key} service")
            except Exception as e:
                logger.error(f"Failed to initialize {service_key}: {e}")
    
    def check_phone_number(self, phone_number: str) -> Dict[str, CheckResult]:
        """Check a phone number across all configured services.
        Returns a mapping of service display name to CheckResult.
        """
        results: Dict[str, CheckResult] = {}
        
        for service_key in self.enabled_services:
            if service_key in self.services:
                try:
                    service = self.services[service_key]
                    legacy = service.check_phone_number(phone_number)
                    structured = to_check_result(service.service_name, phone_number, legacy)
                    results[service.service_name] = structured
                    logger.debug(f"{service.service_name}: {structured.status}")
                except Exception as e:
                    # On unexpected exception, record an error CheckResult
                    service_name = SERVICE_CONFIGURATIONS[service_key]['name']
                    results[service_name] = CheckResult(
                        service=service_name,
                        phone=phone_number,
                        status="error",
                        details={"exception": str(e)},
                        error=str(e),
                    )
                    logger.error(f"Error checking {service_key}: {e}")
            else:
                logger.warning(f"Service {service_key} not initialized")
        
        return results

# Legacy compatibility functions
SERVICE_RATE_LIMITS = {
    config['name']: {
        'recommended_delay': config['recommended_delay'],
        'max_requests_per_minute': config['max_requests_per_minute'],
        'description': config['description']
    }
    for config in SERVICE_CONFIGURATIONS.values()
}

def get_recommended_timeout(enabled_services: Optional[List[str]] = None) -> int:
    """Get recommended timeout based on enabled services."""
    if not enabled_services:
        enabled_services = list(SERVICE_REGISTRY.keys())
    
    max_delay = 0
    for service in enabled_services:
        if service in SERVICE_CONFIGURATIONS:
            delay = SERVICE_CONFIGURATIONS[service]['recommended_delay']
            max_delay = max(max_delay, delay)
    
    return max_delay

def print_rate_limit_info(enabled_services: Optional[List[str]] = None):
    """Print rate limiting information for enabled services."""
    if not enabled_services:
        enabled_services = list(SERVICE_REGISTRY.keys())
    
    print("\n" + "="*60)
    print("SERVICE RATE LIMIT INFORMATION")
    print("="*60)
    
    for service in enabled_services:
        if service in SERVICE_CONFIGURATIONS:
            config = SERVICE_CONFIGURATIONS[service]
            print(f"\n{config['name']}:")
            print(f"  Recommended delay: {config['recommended_delay']}s between requests")
            print(f"  Est. max requests/min: {config['max_requests_per_minute']}")
            print(f"  Notes: {config['description']}")
    
    recommended_timeout = get_recommended_timeout(enabled_services)
    print(f"\nRECOMMENDED TIMEOUT: {recommended_timeout}s")
    print("(Use --timeout {recommended_timeout} for safest operation across selected services)")
    print("="*60)