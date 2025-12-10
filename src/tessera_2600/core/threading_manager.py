#!/usr/bin/env python3
"""
Threading Manager Module
Manages worker threads and coordination for phone number checking.
"""

import threading
import logging
from typing import Dict, Callable, Optional

from tessera_2600.core.proxy_manager import ProxyManager
from tessera_2600.core.work_distributor import WorkDistributor

logger = logging.getLogger(__name__)

class ThreadingManager:
    """Manages worker threads and coordination."""
    
    def __init__(self, max_threads: int = 1):
        self.max_threads = max_threads
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.auto_continue_enabled = threading.Event()
        self.progress_lock = threading.Lock()
        
    def run_threaded_checks(self, work_distributor: WorkDistributor, proxy_manager: ProxyManager,
                           worker_function: Callable, progress_callback: Optional[Callable[[Dict], None]] = None, **worker_kwargs) -> Dict:
        """Run threaded checks with proper coordination."""
        threads = []
        
        # Start worker threads
        for worker_id in range(self.max_threads):
            thread = threading.Thread(
                target=self._worker_wrapper,
                args=(worker_id, work_distributor, proxy_manager, worker_function),
                kwargs=worker_kwargs
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)
        
        logger.info(f"Started {len(threads)} worker threads")
        
        try:
            # Monitor progress with cooperative waiting to reduce CPU usage
            while True:
                # Exit if all threads have finished
                if not any(t.is_alive() for t in threads):
                    break

                if self.stop_event.is_set():
                    break

                # Periodic progress update via callback
                if progress_callback is not None:
                    try:
                        status = {
                            'progress': work_distributor.get_progress(),
                            'proxy_status': proxy_manager.get_status()
                        }
                        progress_callback(status)
                    except Exception:
                        # Swallow callback errors to avoid interrupting workers
                        logger.debug("Progress callback raised but was ignored", exc_info=True)

                # Wait a bit while still being responsive to stop signal
                self.stop_event.wait(0.5)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, stopping threads")
            self.stop_event.set()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Return final progress
        return work_distributor.get_progress()
    
    def _worker_wrapper(self, worker_id: int, work_distributor: WorkDistributor, 
                       proxy_manager: ProxyManager, worker_function: Callable, **kwargs):
        """Wrapper for worker function with error handling."""
        try:
            worker_function(
                worker_id=worker_id,
                work_distributor=work_distributor,
                proxy_manager=proxy_manager,
                stop_event=self.stop_event,
                pause_event=self.pause_event,
                auto_continue_enabled=self.auto_continue_enabled,
                progress_lock=self.progress_lock,
                **kwargs
            )
        except Exception:
            # Include traceback for easier debugging/maintenance
            logger.exception(f"Worker {worker_id} encountered an unexpected error")
    
    def stop(self):
        """Signal all threads to stop."""
        self.stop_event.set()
    
    def pause(self):
        """Signal threads to pause."""
        self.pause_event.set()
    
    def resume(self):
        """Resume paused threads."""
        self.pause_event.clear()
    
    def enable_auto_continue(self):
        """Enable auto-continue mode."""
        self.auto_continue_enabled.set()
        self.pause_event.clear()
    
    def is_stopped(self) -> bool:
        """Check if stop signal is set."""
        return self.stop_event.is_set()
    
    def is_paused(self) -> bool:
        """Check if pause signal is set."""
        return self.pause_event.is_set()
    
    def is_auto_continue(self) -> bool:
        """Check if auto-continue is enabled."""
        return self.auto_continue_enabled.is_set()