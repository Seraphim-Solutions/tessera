#!/usr/bin/env python3
"""
Updated Checker Coordinator Module
Coordinates the phone number checking operations with proper UI updates.
"""

import time
import threading
import logging
from typing import List, Dict, Tuple, Optional

from tessera_2600.checker import SocialMediaChecker
from tessera_2600.core.proxy_manager import ProxyManager
from tessera_2600.core.work_distributor import WorkDistributor
from tessera_2600.core.threading_manager import ThreadingManager
from tessera_2600.utils import format_phone_number, sleep_with_message
from tessera_2600.config import STATUS_MESSAGES, ERROR_MESSAGES
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn

logger = logging.getLogger(__name__)


class CheckerCoordinator:
    """Coordinates phone number checking operations across services with proper UI integration."""
    
    def __init__(self, services: List[str], proxies: List[str], timeout: int, display_manager=None):
        self.services = services
        self.proxies = proxies
        self.timeout = timeout
        self.found_accounts = []
        self.results_lock = threading.Lock()
        self.display_manager = display_manager
        
        # Check if we're in Rich UI mode
        self._is_rich_mode = self._check_rich_mode()
        
        # Progress tracking for UI updates
        self._progress_data = {
            'proxy_status': {'available': len(proxies), 'total': len(proxies), 'cooling_down': 0},
            'work_progress': {'completed': 0, 'in_progress': 0, 'remaining': 0}
        }
        self._progress_lock = threading.Lock()
    
    def _check_rich_mode(self) -> bool:
        """Check if we're running in Rich UI mode."""
        # CLI-only build: no Rich/Textual display backends are used.
        # Always treat the environment as basic console mode.
        return False
    
    def _print_if_basic(self, message: str):
        """Print message only if in basic UI mode."""
        if not self._is_rich_mode:
            print(message)
    
    def run_checks(self, work_items: List[Tuple[int, str]], threads: int, start_index: int,
                   pause_on_found: bool, auto_continue: bool, ui) -> Tuple[List[Dict], int]:
        """Run the checking operation either threaded or sequential."""
        
        # Initialize progress tracking
        with self._progress_lock:
            self._progress_data['work_progress'] = {
                'completed': 0,
                'in_progress': 0,
                'remaining': len(work_items)
            }
        
        if threads > 0:
            return self._run_threaded_checks(
                work_items, threads, start_index, pause_on_found, auto_continue, ui
            )
        else:
            return self._run_sequential_checks(
                work_items, start_index, pause_on_found, auto_continue, ui
            )
    
    def _update_progress(self, proxy_manager: Optional[ProxyManager] = None, 
                        work_distributor: Optional[WorkDistributor] = None):
        """Update progress data and notify display."""
        with self._progress_lock:
            if proxy_manager:
                self._progress_data['proxy_status'] = proxy_manager.get_status()
            if work_distributor:
                self._progress_data['work_progress'] = work_distributor.get_progress()
            
            # Notify display manager
            if self.display_manager and hasattr(self.display_manager, 'show_progress_status'):
                self.display_manager.show_progress_status(
                    self._progress_data['proxy_status'],
                    self._progress_data['work_progress']
                )
    
    def _run_threaded_checks(self, work_items: List[Tuple[int, str]], threads: int,
                            start_index: int, pause_on_found: bool, auto_continue: bool, ui) -> Tuple[List[Dict], int]:
        """Run threaded checking operation with proper progress updates."""
        proxy_manager = ProxyManager(self.proxies)
        work_distributor = WorkDistributor(work_items, start_index)
        threading_manager = ThreadingManager(threads)
        
        if auto_continue:
            threading_manager.enable_auto_continue()
        
        if self.display_manager:
            self.display_manager.show_checking_status(
                self.services, len(self.proxies), self.timeout, threads, pause_on_found, auto_continue
            )
        
        try:
            total_variations = len(work_items)

            # If no external display manager is provided, render a Rich progress bar here
            if not self.display_manager:
                # Mark rich mode to suppress basic prints from workers
                prev_mode = self._is_rich_mode
                self._is_rich_mode = True

                # Temporarily suppress info logs to avoid breaking live progress
                prev_disabled = logging.root.manager.disable
                logging.disable(logging.INFO)

                try:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("{task.description}"),
                        BarColumn(),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        TimeElapsedColumn(),
                        TimeRemainingColumn(),
                        transient=True,
                        refresh_per_second=10,
                    ) as progress_bar:
                        task = progress_bar.add_task("Checking variations • Found: 0", total=total_variations)

                        def _cb(status: Dict):
                            try:
                                prog = (status or {}).get('progress', {})
                                completed = int(prog.get('completed', 0))
                                with self.results_lock:
                                    found = len(self.found_accounts)
                                # Set completed explicitly; ThreadingManager also monitors completion
                                progress_bar.update(task, completed=completed,
                                                    description=f"Checking variations • Found: {found}")
                            except Exception:
                                pass

                        # Run threaded checks with progress callback
                        final_progress = threading_manager.run_threaded_checks(
                            work_distributor=work_distributor,
                            proxy_manager=proxy_manager,
                            worker_function=self._worker_thread,
                            progress_callback=_cb,
                            timeout=self.timeout,
                            enabled_services=self.services,
                            pause_on_found=pause_on_found,
                            ui=ui,
                        )

                    # Final explicit update (after context exits)
                    self._update_progress(proxy_manager, work_distributor)

                    return self.found_accounts, final_progress.get('completed', 0)
                finally:
                    # Restore logging and mode
                    try:
                        logging.disable(prev_disabled)
                    except Exception:
                        logging.disable(logging.NOTSET)
                    self._is_rich_mode = prev_mode

            # Else: if a display manager exists, keep the legacy periodic updater
            # Start a progress update thread
            progress_stop_event = threading.Event()
            progress_thread = threading.Thread(
                target=self._progress_update_worker,
                args=(proxy_manager, work_distributor, progress_stop_event)
            )
            progress_thread.daemon = True
            progress_thread.start()

            # Start threaded checks (no Rich progress; external display handles it)
            progress = threading_manager.run_threaded_checks(
                work_distributor=work_distributor,
                proxy_manager=proxy_manager,
                worker_function=self._worker_thread,
                timeout=self.timeout,
                enabled_services=self.services,
                pause_on_found=pause_on_found,
                ui=ui
            )

            # Stop progress updates
            progress_stop_event.set()
            progress_thread.join(timeout=1.0)

            # Final progress update
            self._update_progress(proxy_manager, work_distributor)

            return self.found_accounts, progress['completed']

        except KeyboardInterrupt:
            self._print_if_basic(f"\n\n{ERROR_MESSAGES['interrupted']}")
            threading_manager.stop()
            # Ensure any updater is stopped if it was started
            try:
                progress_stop_event.set()
            except Exception:
                pass
            progress = work_distributor.get_progress()
            return self.found_accounts, progress['completed']
    
    def _progress_update_worker(self, proxy_manager: ProxyManager, work_distributor: WorkDistributor, 
                               stop_event: threading.Event):
        """Dedicated thread for updating progress every second."""
        while not stop_event.is_set():
            try:
                self._update_progress(proxy_manager, work_distributor)
                time.sleep(1.0)  # Update every second
            except Exception as e:
                logger.debug(f"Progress update error: {e}")
                time.sleep(1.0)
    
    def _run_sequential_checks(self, work_items: List[Tuple[int, str]], start_index: int,
                              pause_on_found: bool, auto_continue: bool, ui) -> Tuple[List[Dict], int]:
        """Run sequential checking operation with progress updates."""
        total_variations = len(work_items)
        auto_continue_enabled = auto_continue
        
        # Initialize single checker
        checker = SocialMediaChecker(proxy_list=self.proxies, timeout=self.timeout, enabled_services=self.services)
        
        if self.display_manager:
            self.display_manager.show_checking_status(
                self.services, len(self.proxies), self.timeout, 0, pause_on_found, auto_continue_enabled
            )
        
        try:
            for i, (idx, number) in enumerate(work_items, 1):
                formatted_number = format_phone_number(number)
                
                # Update progress
                with self._progress_lock:
                    self._progress_data['work_progress'] = {
                        'completed': i - 1,
                        'in_progress': 1,
                        'remaining': len(work_items) - i
                    }
                    if self.display_manager and hasattr(self.display_manager, 'show_progress_status'):
                        self.display_manager.show_progress_status(
                            self._progress_data['proxy_status'],
                            self._progress_data['work_progress']
                        )
                
                if self.display_manager:
                    self.display_manager.show_worker_status(worker_id=0, index=idx, phone_number=formatted_number, action="Checking")
                
                try:
                    results = checker.check_phone_number(formatted_number)
                    
                    for platform, result in results.items():
                        if self.display_manager:
                            self.display_manager.show_result(idx, platform, result)
                        
                        if "[FOUND]" in result:
                            account = {
                                'number': formatted_number,
                                'platform': platform,
                                'result': result,
                                'timestamp': time.time(),
                                'index': idx
                            }
                            self.found_accounts.append(account)
                            
                            if pause_on_found and not auto_continue_enabled:
                                if self.display_manager:
                                    self.display_manager.show_found_account_alert(account)
                                
                                while True:
                                    choice = ui.get_pause_choice()
                                    
                                    if choice == 'continue':
                                        self._print_if_basic("User continued operation")
                                        break
                                    elif choice == 'stop':
                                        self._print_if_basic("Stopping as requested by user")
                                        return self.found_accounts, i
                                    elif choice == 'auto':
                                        self._print_if_basic("Auto-continue enabled for remaining checks")
                                        auto_continue_enabled = True
                                        break
                            
                            elif auto_continue_enabled:
                                self._print_if_basic(f"  Auto-continuing...")
                                time.sleep(1)
                
                except Exception as e:
                    if self.display_manager:
                        self.display_manager.show_result(idx, "ERROR", f"Unexpected error: {e}")
                
                # Sleep between requests (except for last one)
                if i < total_variations and self.timeout > 0:
                    sleep_with_message(self.timeout)
            
            # Final progress update
            with self._progress_lock:
                self._progress_data['work_progress'] = {
                    'completed': len(work_items),
                    'in_progress': 0,
                    'remaining': 0
                }
                if self.display_manager and hasattr(self.display_manager, 'show_progress_status'):
                    self.display_manager.show_progress_status(
                        self._progress_data['proxy_status'],
                        self._progress_data['work_progress']
                    )
            
            return self.found_accounts, len(work_items)
            
        except KeyboardInterrupt:
            self._print_if_basic(f"\n\n{ERROR_MESSAGES['interrupted']}")
            return self.found_accounts, i if 'i' in locals() else 0
    
    def _worker_thread(self, worker_id: int, work_distributor: WorkDistributor, proxy_manager: ProxyManager,
                      stop_event: threading.Event, pause_event: threading.Event, 
                      auto_continue_enabled: threading.Event, progress_lock: threading.Lock,
                      timeout: int, enabled_services: List[str], pause_on_found: bool, ui):
        """Worker thread function for processing phone numbers."""
        checker = None
        
        while not stop_event.is_set():
            # Check if we should pause
            if pause_event.is_set() and not auto_continue_enabled.is_set():
                time.sleep(0.1)
                continue
            
            # Get work item
            work_item = work_distributor.get_work()
            if work_item is None:
                break  # No more work
            
            idx, number = work_item
            formatted_number = format_phone_number(number)
            
            try:
                # Get available proxy
                proxy_url = proxy_manager.get_available_proxy()
                
                if proxy_url is None and proxy_manager.proxies:
                    # No proxies available, wait and retry
                    if self.display_manager:
                        with progress_lock:
                            self.display_manager.show_worker_status(worker_id, idx, formatted_number, "Waiting for proxy availability")
                    
                    # Wait up to 30 seconds for a proxy to become available
                    for _ in range(30):
                        time.sleep(1)
                        proxy_url = proxy_manager.get_available_proxy()
                        if proxy_url or stop_event.is_set():
                            break
                    
                    if proxy_url is None:
                        if self.display_manager and not self._is_rich_mode:
                            with progress_lock:
                                print(f"[{idx:4d}] Worker {worker_id}: No proxies available, skipping...")
                        work_distributor.mark_failed(idx)
                        continue
                
                # Create or update checker
                if checker is None:
                    checker = SocialMediaChecker(
                        proxy_list=[proxy_url] if proxy_url else [], 
                        timeout=timeout,
                        enabled_services=enabled_services
                    )
                else:
                    checker.proxy_list = [proxy_url] if proxy_url else []
                    checker.enabled_services = enabled_services
                
                if self.display_manager:
                    with progress_lock:
                        self.display_manager.show_worker_status(worker_id, idx, formatted_number)

                # Perform the check
                results = checker.check_phone_number(formatted_number)

                # Process results (structured CheckResult objects)
                for platform, structured in results.items():
                    if self.display_manager:
                        with progress_lock:
                            # Best-effort: pass a readable string if a display manager exists
                            disp = f"[{structured.status.upper()}]"
                            self.display_manager.show_result(idx, platform, disp, worker_id)

                    if structured.status == "found":
                        account = {
                            'number': formatted_number,
                            'platform': platform,
                            'status': structured.status,
                            'details': structured.details,
                            'timestamp': structured.ts,
                            'index': idx,
                            'worker_id': worker_id
                        }

                        with self.results_lock:
                            self.found_accounts.append(account)

                        # Signal pause if needed (main thread will handle it)
                        if pause_on_found and not auto_continue_enabled.is_set():
                            pause_event.set()
                            if self.display_manager:
                                with progress_lock:
                                    self.display_manager.show_found_account_alert(account)

                            # Always prompt via UI (even without display_manager) to avoid deadlocks
                            while pause_event.is_set() and not auto_continue_enabled.is_set():
                                choice = ui.get_pause_choice()

                                if choice == 'continue':
                                    self._print_if_basic("User continued operation")
                                    pause_event.clear()
                                    break
                                elif choice == 'stop':
                                    self._print_if_basic("Stopping as requested by user")
                                    stop_event.set()
                                    break
                                elif choice == 'auto':
                                    self._print_if_basic("Auto-continue enabled for remaining checks")
                                    auto_continue_enabled.set()
                                    pause_event.clear()
                                    break

                    elif structured.status == "rate_limited":
                        if proxy_url:
                            proxy_manager.report_rate_limit(proxy_url)

                    elif structured.status == "error":
                        # Treat explicit blocked indications as proxy errors where applicable
                        raw = (structured.error or "") + " " + str(structured.details.get('raw', ''))
                        if proxy_url and ("blocked" in raw.lower()):
                            proxy_manager.report_error(proxy_url)
                
                work_distributor.mark_completed(idx)
                
                # Apply timeout delay
                if timeout > 0:
                    time.sleep(timeout)
            
            except Exception as e:
                if self.display_manager:
                    with progress_lock:
                        self.display_manager.show_result(idx, "ERROR", f"Worker {worker_id} error: {e}")
                work_distributor.mark_failed(idx)
                
                if proxy_url:
                    proxy_manager.report_error(proxy_url)