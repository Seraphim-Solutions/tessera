#!/usr/bin/env python3
"""
Proxy Manager Module
Thread-safe proxy management with rate limiting and cooldowns.
"""

import time
import threading
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ProxyStatus:
    """Track proxy status and rate limiting."""
    proxy_url: str
    is_available: bool = True
    cooldown_until: float = 0.0
    last_used: float = 0.0
    error_count: int = 0
    
    def is_cooled_down(self) -> bool:
        return time.time() >= self.cooldown_until
    
    def set_cooldown(self, duration: int = 600):  # 10 minutes default
        self.cooldown_until = time.time() + duration
        self.is_available = False
    
    def reset_cooldown(self):
        self.cooldown_until = 0.0
        self.is_available = True

class ProxyManager:
    """Thread-safe proxy management with rate limiting and cooldowns."""
    
    def __init__(self, proxy_list: List[str]):
        self.proxies = [ProxyStatus(proxy) for proxy in proxy_list]
        self.lock = threading.Lock()
        self.round_robin_index = 0
        logger.info(f"Initialized ProxyManager with {len(proxy_list)} proxies")
        
    def get_available_proxy(self) -> Optional[str]:
        """Get an available proxy, cycling through them and respecting cooldowns."""
        with self.lock:
            if not self.proxies:
                return None
            
            # First pass: look for available proxies
            available_proxies = [p for p in self.proxies if p.is_available and p.is_cooled_down()]
            
            if available_proxies:
                # Use round-robin among available proxies
                proxy = available_proxies[self.round_robin_index % len(available_proxies)]
                self.round_robin_index = (self.round_robin_index + 1) % len(available_proxies)
                proxy.last_used = time.time()
                return proxy.proxy_url
            
            # Second pass: check if any proxies have cooled down
            cooled_down = []
            for proxy in self.proxies:
                if not proxy.is_available and proxy.is_cooled_down():
                    proxy.reset_cooldown()
                    cooled_down.append(proxy)
            
            if cooled_down:
                proxy = cooled_down[0]  # Take first cooled down proxy
                proxy.last_used = time.time()
                return proxy.proxy_url
            
            return None  # No proxies available
    
    def report_rate_limit(self, proxy_url: str):
        """Report that a proxy has been rate limited."""
        with self.lock:
            for proxy in self.proxies:
                if proxy.proxy_url == proxy_url:
                    proxy.set_cooldown(600)  # 10 minutes
                    proxy.error_count += 1
                    logger.warning(f"Proxy {proxy_url} rate limited, cooling down for 10 minutes")
                    break
    
    def report_error(self, proxy_url: str):
        """Report a general error with a proxy."""
        with self.lock:
            for proxy in self.proxies:
                if proxy.proxy_url == proxy_url:
                    proxy.error_count += 1
                    # Set shorter cooldown for general errors
                    if proxy.error_count >= 3:
                        proxy.set_cooldown(300)  # 5 minutes after 3 errors
                    break
    
    def get_status(self) -> Dict:
        """Get current status of all proxies."""
        with self.lock:
            available = sum(1 for p in self.proxies if p.is_available and p.is_cooled_down())
            cooling_down = sum(1 for p in self.proxies if not p.is_available)
            return {
                'total': len(self.proxies),
                'available': available,
                'cooling_down': cooling_down
            }