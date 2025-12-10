#!/usr/bin/env python3
"""
Service Utilities Module
Common utility functions for service implementations.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def format_international_phone(phone_number: str) -> Optional[str]:
    """Format phone number for international services."""
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone_number)
    
    # Ensure it starts with +
    if not cleaned.startswith('+'):
        # Try to guess country code - this is basic, you might want to enhance
        if len(cleaned) == 9 and cleaned.startswith(('6', '7')):
            # Likely Czech number
            cleaned = '+420' + cleaned
        elif len(cleaned) == 10:
            # Could be US number, but this is just a guess
            cleaned = '+1' + cleaned
    
    # Basic validation - should be at least 10 digits total
    digits_only = re.sub(r'[^\d]', '', cleaned)
    if len(digits_only) >= 10:
        return cleaned
    
    logger.debug(f"Could not format phone number: {phone_number}")
    return None