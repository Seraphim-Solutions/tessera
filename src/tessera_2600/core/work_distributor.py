#!/usr/bin/env python3
"""
Work Distributor Module
Thread-safe work distribution to avoid duplicate processing.
"""

import queue
import threading
import logging
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger(__name__)

class WorkDistributor:
    """Thread-safe work distribution to avoid duplicate processing."""
    
    def __init__(self, work_items: List[Tuple[int, str]], start_index: int = 0):
        self.work_queue = queue.Queue()
        self.completed = set()
        self.in_progress = set()
        self.lock = threading.Lock()
        self.start_index = start_index
        
        # Populate work queue
        for item in work_items:
            self.work_queue.put(item)
        
        logger.info(f"WorkDistributor initialized with {len(work_items)} items, starting at index {start_index}")
    
    def get_work(self) -> Optional[Tuple[int, str]]:
        """Get next work item that isn't completed or in progress."""
        try:
            while True:
                item = self.work_queue.get_nowait()
                idx, number = item
                
                with self.lock:
                    if idx not in self.completed and idx not in self.in_progress:
                        self.in_progress.add(idx)
                        return item
                    # Item already processed or being processed, try next
                    
        except queue.Empty:
            return None
    
    def mark_completed(self, idx: int):
        """Mark work item as completed."""
        with self.lock:
            self.in_progress.discard(idx)
            self.completed.add(idx)
    
    def mark_failed(self, idx: int):
        """Mark work item as failed, making it available for retry."""
        with self.lock:
            self.in_progress.discard(idx)
            # Could implement retry logic here if needed
    
    def get_progress(self) -> Dict:
        """Get current progress statistics."""
        with self.lock:
            return {
                'completed': len(self.completed),
                'in_progress': len(self.in_progress),
                'remaining': self.work_queue.qsize(),
                'total_processed': len(self.completed) + len(self.in_progress)
            }
    
    def is_complete(self) -> bool:
        """Check if all work is completed."""
        with self.lock:
            return self.work_queue.empty() and len(self.in_progress) == 0