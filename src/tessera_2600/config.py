#!/usr/bin/env python3
"""
Tessera Configuration Module
"""

import logging

# Application Information
APP_NAME = "Tessera"
APP_VERSION = "1.0.1"
APP_DESCRIPTION = "Generate and check phone number variations across social media platforms"

# Default Settings
DEFAULT_TIMEOUT = 2
DEFAULT_MAX_VARIATIONS = 1000000
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_PAUSE_ON_FOUND = True
DEFAULT_AUTO_CONTINUE = False

# Rate Limiting
MAX_WILDCARDS = 6
CONFIRMATION_THRESHOLD = 100

# Request Settings
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

# Country codes and their mobile number patterns
COUNTRY_PATTERNS = {
    '420': {  # Czech Republic
        'length': 9,
        'prefixes': ['6', '7'],
        'name': 'Czech Republic'
    },
    '421': {  # Slovakia
        'length': 9,
        'prefixes': ['9'],
        'name': 'Slovakia'
    },
    '1': {    # USA/Canada
        'length': 10,
        'prefixes': ['2', '3', '4', '5', '6', '7', '8', '9'],
        'name': 'USA/Canada'
    },
    '44': {   # United Kingdom
        'length': 10,
        'prefixes': ['7'],
        'name': 'United Kingdom'
    },
    '49': {   # Germany
        'length': 10,
        'prefixes': ['1'],
        'name': 'Germany'
    }
}

# Status messages
STATUS_MESSAGES = {
    'found': '✅',
    'not_found': '❌',
    'error': '🚨',
    'warning': '⚠️',
    'info': 'ℹ️',
    'success': '🎉',
    'processing': '🔍',
    'generating': '🔢',
    'checking': '📱'
}

# Logging configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# File patterns
PROXY_FILE_PATTERNS = ['*.txt', '*.list', '*.proxies']
OUTPUT_FILE_PATTERNS = ['*.json', '*.csv', '*.txt']

# Error messages
ERROR_MESSAGES = {
    'invalid_pattern': "❌ Invalid phone number pattern. Example: '+420 731x4x748'",
    'too_many_wildcards': "❌ Too many wildcards. Maximum {max} allowed.",
    'no_variations': "❌ No variations generated from pattern.",
    'proxy_file_not_found': "⚠️  Proxy file not found: {file}",
    'no_proxies_loaded': "⚠️  No proxies loaded, continuing without proxies.",
    'interrupted': "⚠️  Operation interrupted by user.",
    'rate_limited': "⚠️  Rate limited by service.",
    'connection_error': "❌ Connection error occurred.",
    'timeout_error': "❌ Request timeout occurred.",
    'service_blocked': "🚨 Service blocked access (IP/proxy may be blacklisted)",
    'captcha_required': "🤖 CAPTCHA required by service",
}

# Success messages
SUCCESS_MESSAGES = {
    'variations_generated': "✅ Generated {count} variations",
    'proxies_loaded': "✅ Loaded {count} proxies",
    'check_complete': "🎯 Check completed: {found} accounts found",
    'pattern_valid': "✅ Pattern is valid",
    'account_found': "🎉 ACCOUNT FOUND!",
    'continuing_search': "▶️  Continuing search...",
    'user_continued': "✅ User continued operation",
    'auto_continuing': "🔄 Auto-continuing (--auto-continue enabled)",
    'service_recommendations': "📋 Service rate limit recommendations shown",
}

# Validation patterns
PHONE_PATTERN = r'^(\+\d{1,4}\s?)[\d\sx\-\(\)]+'
WILDCARD_PATTERN = r'[xX]'

# Output formats
OUTPUT_FORMATS = ['json', 'csv', 'txt']

# Threading recommendations based on services
def get_max_recommended_threads(enabled_services=None):
    """Get maximum recommended threads for enabled services."""
    # Import here to avoid circular imports
    try:
        from tessera_2600.services import SERVICE_CONFIGURATIONS, get_service_info
        
        if enabled_services is None:
            enabled_services = list(SERVICE_CONFIGURATIONS.keys())
        
        # Conservative recommendations
        thread_limits = {
            'facebook': 2,
            'instagram': 4,
            'amazon': 3,
            'seznamcz': 8
        }
        
        if not enabled_services:
            return 4  # Default
        
        # Return the most conservative recommendation
        min_threads = min(thread_limits.get(service, 8) for service in enabled_services)
        return max(1, min_threads)
        
    except ImportError:
        # Fallback if services module not available
        return 4

def get_recommended_timeout_for_services(enabled_services=None):
    """Get recommended timeout based on enabled services."""
    try:
        from tessera_2600.services import SERVICE_CONFIGURATIONS, get_max_recommended_delay
        
        if enabled_services is None:
            enabled_services = list(SERVICE_CONFIGURATIONS.keys())
        
        if not enabled_services:
            return DEFAULT_TIMEOUT
        
        max_delay = get_max_recommended_delay(enabled_services)
        return max_delay
        
    except ImportError:
        # Fallback if services module not available
        return DEFAULT_TIMEOUT

def get_proxy_required_services():
    """Get list of services that require proxies."""
    try:
        from tessera_2600.services import get_proxy_required_services as get_proxy_services
        return get_proxy_services()
    except ImportError:
        # Fallback if services module not available
        return []