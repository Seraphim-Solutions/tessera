#!/usr/bin/env python3
"""
Variation Generator Module
Handles phone number variation generation and validation.
"""

import logging
from typing import List, Tuple
from tessera_2600.generator import expand_phone_number, can_use_country_prefixes
from tessera_2600.config import SUCCESS_MESSAGES, ERROR_MESSAGES, COUNTRY_PATTERNS

logger = logging.getLogger(__name__)

class VariationGenerator:
    """Handles phone number variation generation and validation without UI side-effects."""
    
    def suggest_country_prefixes(self, pattern: str) -> bool:
        """Return True if pattern can benefit from country prefixes (no UI here)."""
        can_use, country_code, country_name = can_use_country_prefixes(pattern)
        return bool(can_use)
    
    def generate_variations(self, pattern: str, max_variations: int, use_country_prefixes: bool = False,
                           start_index: int = 0) -> Tuple[List[Tuple[int, str]], int]:
        """Generate phone number variations with validation and optional start position.
        Pure function: no printing/UI.
        """
        if use_country_prefixes:
            can_use, _, _ = can_use_country_prefixes(pattern)
            if not can_use:
                use_country_prefixes = False
        
        try:
            all_numbers = expand_phone_number(pattern, use_country_prefixes)
        except Exception:
            return [], 0
        
        total_variations = len(all_numbers)
        
        if total_variations == 0:
            return [], 0
        
        if start_index >= total_variations:
            return [], 0
        
        # Create work items with indices
        work_items = []
        for i, number in enumerate(all_numbers[start_index:], start_index + 1):
            work_items.append((i, number))
        
        if len(work_items) > max_variations:
            return [], 0
        
        return work_items, start_index