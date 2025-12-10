#!/usr/bin/env python3
"""
Phone Number Generator Module
Generates all possible variations of a partial phone number with wildcards.
Enhanced with country-specific default prefixes.
"""

import re
import logging
from typing import List, Optional
from tessera_2600.config import MAX_WILDCARDS, COUNTRY_PATTERNS, PHONE_PATTERN

logger = logging.getLogger(__name__)

class PhoneNumberGenerator:
    """Generate all possible variations of a partial phone number with wildcards."""
    
    def __init__(self, partial_number: str, use_country_prefixes: bool = False):
        self.partial_number = partial_number.strip()
        self.use_country_prefixes = use_country_prefixes
        self.country_code = None
        self.base_number = None
        self._parse_phone_number()
    
    def _parse_phone_number(self):
        """Parse phone number to extract country code and base number."""
        # Remove all non-digit characters except + and x
        cleaned = re.sub(r'[^\d+xX\s\-\(\)]', '', self.partial_number)
        cleaned = re.sub(r'[^\d+xX]', '', cleaned)  # Remove spaces, dashes, brackets
        
        # Extract country code
        if cleaned.startswith('+'):
            # Find where the country code ends (before the main number)
            for i in range(2, min(6, len(cleaned))):  # Country codes are 1-4 digits
                potential_code = cleaned[1:i]
                if potential_code in COUNTRY_PATTERNS:
                    self.country_code = potential_code
                    self.base_number = cleaned[i:]
                    logger.debug(f"Parsed country code: +{self.country_code}, base: {self.base_number}")
                    break
        
        if not self.country_code:
            logger.debug(f"Could not extract country code from: {self.partial_number}")
    
    def should_use_country_prefixes(self) -> bool:
        """Check if we should use country-specific prefixes."""
        if not self.use_country_prefixes:
            return False
            
        if not self.country_code or self.country_code not in COUNTRY_PATTERNS:
            logger.debug(f"Country code {self.country_code} not in supported patterns")
            return False
            
        # Check if the first character of the base number is 'x' (meaning unknown)
        if not self.base_number or self.base_number[0].lower() != 'x':
            logger.debug(f"First digit is not unknown (x), base: {self.base_number}")
            return False
            
        logger.debug(f"Will use country prefixes for {self.country_code}")
        return True
    
    def generate_variations(self) -> List[str]:
        """Generate all possible variations by replacing 'x' with digits 0-9."""
        if self.should_use_country_prefixes():
            return self._generate_with_country_prefixes()
        else:
            return self._generate_standard()
    
    def _generate_standard(self) -> List[str]:
        """Standard generation method (original behavior)."""
        variations = []
        self._generate_helper(self.partial_number, variations)
        logger.info(f"Generated {len(variations)} variations for pattern: {self.partial_number}")
        return variations
    
    def _generate_with_country_prefixes(self) -> List[str]:
        """Generate variations using country-specific prefixes for the first digit."""
        all_variations = []
        country_info = COUNTRY_PATTERNS[self.country_code]
        
        logger.info(f"Using country prefixes for {country_info['name']} (+{self.country_code})")
        logger.info(f"Valid mobile prefixes: {', '.join(country_info['prefixes'])}")
        
        # For each valid prefix, replace the first 'x' and generate variations
        for prefix in country_info['prefixes']:
            # Create pattern with country code + prefix + remaining pattern
            pattern_with_prefix = f"+{self.country_code}{prefix}{self.base_number[1:]}"
            
            # Generate all variations for this prefix
            variations = []
            self._generate_helper(pattern_with_prefix, variations)
            all_variations.extend(variations)
            
            logger.debug(f"Generated {len(variations)} variations for prefix {prefix}")
        
        logger.info(f"Generated {len(all_variations)} total variations using country prefixes")
        return all_variations
    
    def _generate_helper(self, current: str, variations: List[str]):
        """Recursive helper to generate variations."""
        if 'x' not in current.lower():
            variations.append(current)
            return
        
        # Find first 'x' (case insensitive)
        index = current.lower().index('x')
        for digit in range(10):
            new_number = current[:index] + str(digit) + current[index + 1:]
            self._generate_helper(new_number, variations)

def validate_phone_number(phone_number: str) -> bool:
    """Validate phone number pattern using config.PHONE_PATTERN."""
    return bool(re.match(PHONE_PATTERN, phone_number, re.IGNORECASE))

def validate_pattern(pattern: str) -> bool:
    """Validate that the pattern contains wildcards and is properly formatted."""
    if not validate_phone_number(pattern):
        logger.error(f"Invalid phone number format: {pattern}")
        return False
    
    # Must contain at least one wildcard
    if 'x' not in pattern.lower():
        logger.warning("Pattern should contain at least one 'x' wildcard")
        return False
    
    # Check for reasonable number of wildcards (to prevent excessive generation)
    wildcard_count = pattern.lower().count('x')
    if wildcard_count > MAX_WILDCARDS:
        logger.error(f"Too many wildcards ({wildcard_count}). Maximum {MAX_WILDCARDS} allowed to prevent excessive generation.")
        return False
    
    return True

def can_use_country_prefixes(pattern: str) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Check if pattern can use country prefixes.
    Returns: (can_use, country_code, country_name)
    """
    generator = PhoneNumberGenerator(pattern, use_country_prefixes=True)
    
    if generator.country_code and generator.base_number:
        # Check if first digit is unknown
        if generator.base_number[0].lower() == 'x':
            country_info = COUNTRY_PATTERNS[generator.country_code]
            return True, generator.country_code, country_info['name']
    
    return False, None, None

def expand_phone_number(pattern: str, use_country_prefixes: bool = False) -> List[str]:
    """Generate all variations of a phone number pattern."""
    generator = PhoneNumberGenerator(pattern, use_country_prefixes)
    return generator.generate_variations()