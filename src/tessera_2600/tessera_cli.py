#!/usr/bin/env python3
"""
Tessera-CLI - Command Line Interface (CLI-only)
OSINT tool for phone number reconnaissance with rich terminal feedback.
"""

import argparse
import os
import sys
import logging
import time
from typing import List, Dict, Tuple, Optional

# Ensure local source package is importable when running this file directly or as a script
try:  # pragma: no cover - runtime convenience for direct script execution
    import os as _os, sys as _sys
    _src_root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
    if _src_root not in _sys.path:
        # Prepend to take precedence over any installed package in site-packages
        _sys.path.insert(0, _src_root)
except Exception:
    pass

# Import core modules (use absolute package imports for PyPI compatibility)
from tessera_2600.generator import expand_phone_number, validate_pattern, can_use_country_prefixes
from tessera_2600.checker import SocialMediaChecker
from tessera_2600.services import (
    SERVICE_CONFIGURATIONS,
    validate_services,
    get_descriptor_source,
    get_duplicate_warnings,
)
from tessera_2600.utils import load_proxies, confirm_action, format_phone_number
from tessera_2600.config import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION, DEFAULT_TIMEOUT, DEFAULT_MAX_VARIATIONS,
    DEFAULT_PAUSE_ON_FOUND, DEFAULT_AUTO_CONTINUE, CONFIRMATION_THRESHOLD,
    ERROR_MESSAGES, SUCCESS_MESSAGES, COUNTRY_PATTERNS
)

# Import operations
from tessera_2600.operations.variation_generator import VariationGenerator
from tessera_2600.operations.results_handler import ResultsHandler
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn


console = Console()


class ConsoleUI:
    """Rich-based console UI for the CLI."""

    @staticmethod
    def print_banner():
        console.print(Panel.fit(f"[bold cyan]{APP_NAME}[/] CLI v{APP_VERSION}\n[dim]{APP_DESCRIPTION}[/]", border_style="cyan"))

    @staticmethod
    def print_service_info(services: List[str]):
        table = Table(title="Enabled Services", box=box.SIMPLE_HEAD, expand=False)
        table.add_column("Service", style="bold")
        table.add_column("Delay (s)")
        table.add_column("Proxy")
        table.add_column("Risk")
        table.add_column("Descriptor")
        table.add_column("Notes", overflow="fold")
        for service_key in services:
            if service_key in SERVICE_CONFIGURATIONS:
                config = SERVICE_CONFIGURATIONS[service_key]
                proxy_recommended = config.get('proxy_recommended', config.get('requires_proxy', False))
                proxy_req = "Recommended" if proxy_recommended else "Optional"
                severity = (config.get('rate_limit_severity', 'unknown') or 'unknown').capitalize()
                # Resolve descriptor (filename with extension) if available
                src = None
                try:
                    src = get_descriptor_source(service_key)
                except Exception:
                    src = None
                descriptor_file = (src or {}).get('selected_file') or config.get('descriptor_file', '') or ''
                table.add_row(
                    config['name'],
                    str(config['recommended_delay']),
                    proxy_req,
                    severity,
                    descriptor_file,
                    config.get('description', '')
                )
        console.print(table)

    @staticmethod
    def _get_single_key() -> str:
        """Read a single key without requiring Enter. Falls back to input()."""
        try:
            # POSIX
            import sys as _sys
            import termios as _termios
            import tty as _tty
            fd = _sys.stdin.fileno()
            old = _termios.tcgetattr(fd)
            try:
                _tty.setraw(fd)
                ch = _sys.stdin.read(1)
            finally:
                _termios.tcsetattr(fd, _termios.TCSADRAIN, old)
            return ch
        except Exception:
            try:
                # Windows
                import msvcrt  # type: ignore
                ch = msvcrt.getch()
                if isinstance(ch, bytes):
                    ch = ch.decode('utf-8', errors='ignore')
                return ch
            except Exception:
                # Fallback: require Enter
                try:
                    return input("")[:1]
                except Exception:
                    return ""

    @staticmethod
    def get_pause_choice() -> str:
        try:
            console.print("\n[bold]Account found![/] Press: [dim][ENTER][/dim] to continue, [bold]s[/bold] to stop, [bold]a[/bold] to enable auto-continue")
            response = ConsoleUI._get_single_key().strip().lower()
            if response == 's':
                return 'stop'
            elif response == 'a':
                return 'auto'
            else:
                return 'continue'
        except (KeyboardInterrupt, EOFError):
            return 'stop'

    @staticmethod
    def print_summary(found_accounts: List[Dict], total_checked: int, elapsed_time: int):
        from tessera_2600.utils import format_duration
        console.print(Panel.fit(
            f"Checked: [bold]{total_checked:,}[/] | Found: [bold green]{len(found_accounts)}[/] | Elapsed: [bold]{format_duration(elapsed_time)}[/]",
            title="Summary",
            border_style="green",
        ))
        if found_accounts:
            table = Table(title="Found Accounts", box=box.SIMPLE_HEAD)
            table.add_column("#", justify="right")
            table.add_column("Phone")
            table.add_column("Service")
            table.add_column("Status")
            table.add_column("When")
            for i, acc in enumerate(found_accounts, 1):
                when = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(acc.get('timestamp', time.time())))
                table.add_row(str(i), acc.get('number', ''), acc.get('platform', ''), acc.get('status', ''), when)
            console.print(table)


class CLIChecker:
    """Main checker for CLI version with Rich feedback."""

    def __init__(self, services: List[str], proxies: List[str], timeout: int, jsonl_out: Optional[str] = None):
        self.services = services
        self.proxies = proxies
        self.timeout = timeout
        self.ui = ConsoleUI()
        self.found_accounts: List[Dict] = []
        self.jsonl_out = jsonl_out
        self.found_count = 0

    def run_checks(self, work_items: List[Tuple[int, str]], pause_on_found: bool,
                   auto_continue: bool) -> Tuple[List[Dict], int]:
        total_variations = len(work_items)
        auto_continue_enabled = auto_continue

        checker = SocialMediaChecker(
            proxy_list=self.proxies,
            timeout=self.timeout,
            enabled_services=self.services
        )

        console.print(f"\n[bold]Starting checks[/] with {len(self.proxies)} proxies, timeout {self.timeout}s")
        console.print(f"Services: [cyan]{', '.join(self.services)}[/]")
        if pause_on_found and not auto_continue_enabled:
            console.print("Pause-on-found: [yellow]ENABLED[/]")
        elif auto_continue_enabled:
            console.print("Auto-continue: [green]ENABLED[/]")

        from tessera_2600.operations.results_handler import ResultsHandler
        rh = ResultsHandler()

        try:
            # Temporarily suppress INFO/DEBUG logs so they don't break the live progress area
            prev_disabled = logging.root.manager.disable
            logging.disable(logging.INFO)

            # Include a running found counter in the task description; avoid per-hit prints in auto-continue
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                transient=True,
                refresh_per_second=10,
                console=console,
                disable=not console.is_terminal,
            ) as progress:
                task = progress.add_task("Checking variations • Found: 0", total=total_variations)
                for i, (idx, number) in enumerate(work_items, 1):
                    try:
                        results = checker.check_phone_number(number)
                        for platform, structured in results.items():
                            # Stream all results if requested
                            if self.jsonl_out:
                                rh.append_jsonl(self.jsonl_out, structured)
                            if structured.status == "found":
                                account = {
                                    'number': number,
                                    'platform': platform,
                                    'status': structured.status,
                                    'details': structured.details,
                                    'timestamp': structured.ts,
                                    'index': idx,
                                }
                                self.found_accounts.append(account)
                                self.found_count += 1
                                # If we're pausing on found and auto-continue isn't enabled yet, prompt; else only update counter
                                if pause_on_found and not auto_continue_enabled:
                                    progress.console.print(Panel.fit(
                                        f"[bold green]Found[/] [white]{account['number']}[/] on [cyan]{account['platform']}[/]",
                                        border_style="green"
                                    ))
                                    choice = self.ui.get_pause_choice()
                                    if choice == 'stop':
                                        progress.update(task, advance=1)
                                        return self.found_accounts, i
                                    elif choice == 'auto':
                                        auto_continue_enabled = True
                                        progress.console.print("Auto-continue [green]enabled[/]")
                                # Always reflect the new-found counter in the task description without printing a new line
                                progress.update(task, description=f"Checking variations • Found: {self.found_count}")
                    except Exception as e:
                        progress.console.print(f"\n  [red]Error[/] checking {number}: {e}")
                    finally:
                        if i < total_variations and self.timeout > 0:
                            time.sleep(self.timeout)
                        progress.update(task, advance=1)

            return self.found_accounts, len(work_items)

        except KeyboardInterrupt:
            console.print(f"\n\n{ERROR_MESSAGES['interrupted']}")
            return self.found_accounts, i if 'i' in locals() else 0
        finally:
            # Restore previous logging disable threshold
            try:
                logging.disable(prev_disabled)
            except Exception:
                logging.disable(logging.NOTSET)


def setup_logging(verbose: bool = False):
    """Setup logging configuration.
    Default to WARNING to avoid flooding the live progress. Use --verbose for DEBUG.
    Route logs through Rich so live progress isn't broken.
    """
    level = logging.DEBUG if verbose else logging.WARNING
    # Configure Rich handler to cooperate with live progress rendering
    handler = RichHandler(
        console=console,
        show_time=True,
        show_path=verbose,
        rich_tracebacks=verbose,
        markup=True,
    )
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[handler],
        force=True,
    )
    # Quiet noisy libraries unless verbose
    for name in ("urllib3", "requests", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING if not verbose else logging.INFO)
    # Our own modules: enable extra debug when verbose, including core runtime
    for name in ("services", "generator", "checker", "tessera_2600.core", "tessera_2600.core.declarative_service"):
        logging.getLogger(name).setLevel(logging.WARNING if not verbose else logging.DEBUG)


def validate_args(args) -> bool:
    """Validate command line arguments."""
    if not validate_pattern(args.number):
        print(ERROR_MESSAGES['invalid_pattern'])
        return False
    
    if args.timeout is not None:
        if args.timeout < 0:
            print("Timeout must be non-negative")
            return False
    
    if args.max_variations <= 0:
        print("Max variations must be positive")
        return False
    
    if args.start < 0:
        print("Start position must be non-negative")
        return False
    
    # Validate threads
    if hasattr(args, 'threads') and args.threads is not None:
        if args.threads < 1:
            print("Threads must be a positive integer")
            return False
    
    # Validate services
    if args.services:
        validated_services = validate_services(args.services)
        if not validated_services:
            print("Error: No valid services specified")
            return False
        args.services = validated_services
    else:
        # Default to all registered services
        from tessera_2600.services import SERVICE_REGISTRY
        args.services = list(SERVICE_REGISTRY.keys())
    
    return True


def main():
    """Main function."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Handle information-only flags
    if args.show_services:
        svc_list = validate_services(args.services) if args.services else list(SERVICE_CONFIGURATIONS.keys())
        ConsoleUI.print_service_info(svc_list)
        # Show any duplicate descriptor warnings
        try:
            dup_warnings = get_duplicate_warnings()
            if dup_warnings:
                console.print("\n[yellow]Descriptor selection notices:[/]")
                for w in dup_warnings:
                    console.print(f"[yellow]- {w}[/]")
        except Exception:
            pass
        return 0
    
    if args.show_rate_limits:
        _print_rate_limit_table(args.services if args.services else list(SERVICE_CONFIGURATIONS.keys()))
        return 0
    
    # Cross-reference mode (no scanning)
    if args.cross_ref:
        if not args.cross_ref_output:
            console.print("[red]--cross-ref-output is required when using --cross-ref[/]")
            return 2
        rh = ResultsHandler()
        ok = rh.cross_reference_files(
            inputs=args.cross_ref,
            output_file=args.cross_ref_output,
            require_all=args.cross_ref_all
        )
        return 0 if ok else 1
    
    # Require --number for actual execution
    if not args.number:
        parser.error("--number is required (unless using --show-services, --show-rate-limits, or --cross-ref)")
    
    # Validate arguments
    if not validate_args(args):
        return 1
    
    # Compute dynamic timeout if not provided
    if args.timeout is None:
        try:
            from tessera_2600.config import get_recommended_timeout_for_services
            args.timeout = get_recommended_timeout_for_services(args.services)
            console.print(f"⏱️ Using recommended timeout: {args.timeout}s (based on selected services)")
        except Exception:
            from tessera_2600.config import DEFAULT_TIMEOUT
            args.timeout = DEFAULT_TIMEOUT
            console.print(f"⏱️ Using default timeout: {args.timeout}s")

    # Determine threads (default to conservative recommendation)
    try:
        from tessera_2600.config import get_max_recommended_threads
        threads = args.threads if hasattr(args, 'threads') and args.threads is not None else get_max_recommended_threads(args.services)
    except Exception:
        threads = args.threads if hasattr(args, 'threads') and args.threads is not None else 1
    console.print(f"🧵 Using threads: {threads}")
    
    # Show banner and service info
    if not args.no_banner:
        ConsoleUI.print_banner()
        ConsoleUI.print_service_info(args.services)
        # Show duplicate warnings once at startup
        try:
            dup_warnings = get_duplicate_warnings()
            if dup_warnings:
                console.print("[yellow]\nNote: Multiple descriptor files detected for some services. JSON is preferred. Details:[/]")
                for w in dup_warnings:
                    console.print(f"[yellow]- {w}[/]")
        except Exception:
            pass
    
    # Initialize managers
    ui = ConsoleUI()
    variation_gen = VariationGenerator()
    results_handler = ResultsHandler()
    
    start_time = time.time()
    
    try:
        # Show country prefix suggestion
        if not args.use_country_prefixes:
            can_use, country_code, country_name = can_use_country_prefixes(args.number)
            if can_use:
                console.print(f"💡 TIP: Pattern detected for {country_name} (+{country_code})")
                console.print(f"   Use --use-country-prefixes for better coverage\n")
        
        # Load proxies
        proxies = []
        if args.proxy_file:
            proxies = load_proxies(args.proxy_file)
            if proxies:
                console.print(f"✅ Loaded {len(proxies)} proxies")
            else:
                console.print(f"⚠️  No proxies loaded from {args.proxy_file}")
        
        # Check if proxies are needed
        proxy_recommended = [s for s in args.services 
                             if SERVICE_CONFIGURATIONS[s].get('proxy_recommended', SERVICE_CONFIGURATIONS[s].get('requires_proxy', False))]
        if proxy_recommended and not proxies:
            console.print(f"⚠️  Services with proxies recommended: {', '.join(proxy_recommended)}")
            console.print("   Consider using --proxy-file for better success rates\n")
        
        # Generate work items
        work_items, start_index = variation_gen.generate_variations(
            args.number, args.max_variations, args.use_country_prefixes, args.start
        )
        if not work_items:
            console.print("[red]No variations to process.[/]")
            return 1
        
        # Confirm large operations
        if len(work_items) > CONFIRMATION_THRESHOLD:
            from tessera_2600.config import get_recommended_timeout_for_services
            from tessera_2600.utils import format_duration
            n = len(work_items)
            svc_count = max(1, len(args.services))
            total_http = n * svc_count

            # Estimate bounds
            rec_delay = get_recommended_timeout_for_services(args.services)
            # Optimistic: very fast endpoints like Seznam can be ~50–70 ms per variation when timeout is 0
            optimistic_per_var = max(0.05, float(args.timeout)) if args.timeout is not None else 0.05
            # If we know services have non-zero recommended delay, use it as conservative bound
            if rec_delay and rec_delay > 0:
                conservative_per_var = float(rec_delay)
            else:
                # Otherwise assume a small per-service overhead (≈60 ms each)
                conservative_per_var = max(optimistic_per_var, 0.06 * svc_count)

            est_low = n * optimistic_per_var
            est_high = n * conservative_per_var
            est_range = f"~{format_duration(int(est_low))}–{format_duration(int(est_high))}"

            message = (
                f"This will perform roughly {total_http:,} HTTP checks "
                f"({n:,} variations × {svc_count} service{'s' if svc_count==1 else 's'}).\n"
                f"Estimated duration: {est_range} (actual depends on network and rate limits)."
            )
            
            if not confirm_action(message, default=True):
                console.print("Operation cancelled")
                return 0
        
        # Initialize and run checker (threaded or sequential)
        if threads and threads > 1:
            from tessera_2600.operations.checker_coordinator import CheckerCoordinator
            coordinator = CheckerCoordinator(
                services=args.services,
                proxies=proxies,
                timeout=args.timeout,
                display_manager=None,
            )
            found_accounts, total_checked = coordinator.run_checks(
                work_items=work_items,
                threads=threads,
                start_index=start_index,
                pause_on_found=not args.no_pause,
                auto_continue=args.auto_continue,
                ui=ui,
            )
        else:
            checker = CLIChecker(
                services=args.services,
                proxies=proxies,
                timeout=args.timeout,
                jsonl_out=args.jsonl_out
            )
            found_accounts, total_checked = checker.run_checks(
                work_items=work_items,
                pause_on_found=not args.no_pause,
                auto_continue=args.auto_continue
            )
        
        # Show summary
        elapsed_time = int(time.time() - start_time)
        ui.print_summary(found_accounts, total_checked, elapsed_time)
        
        # Save results if requested
        if args.output:
            if results_handler.save_results(found_accounts, args.output):
                console.print(f"\n✅ Results saved to {args.output}")
        
        # Save per-service outputs if requested
        written_files = {}
        if args.per_service_out_dir:
            try:
                written_files = results_handler.save_per_service_results(
                    found_accounts,
                    args.per_service_out_dir,
                    output_format=args.per_service_format
                )
                if written_files:
                    console.print(f"📁 Per-service outputs saved in {args.per_service_out_dir} ({len(written_files)} files)")
            except Exception as e:
                console.print(f"[red]Failed to save per-service outputs:[/] {e}")
        
        # Offer cross-reference of per-service outputs
        if written_files and len(written_files) >= 2:
            do_cross = args.cross_ref_after_scan or confirm_action(
                "Cross-reference per-service output files for numbers appearing in multiple services?",
                default=False
            )
            if do_cross:
                require_all = args.cross_ref_all
                if not args.cross_ref_after_scan:
                    # Ask whether to require presence in ALL files
                    require_all = confirm_action(
                        "Require numbers to appear in ALL per-service files? (No = at least two)",
                        default=False
                    )
                # Determine output path
                out_path = args.cross_ref_output
                if not out_path:
                    # default file in the same dir
                    out_path = os.path.join(args.per_service_out_dir, 'crossref.json')
                ok = results_handler.cross_reference_files(
                    inputs=list(written_files.values()),
                    output_file=out_path,
                    require_all=require_all
                )
                if ok:
                    console.print(f"🔗 Cross-reference written to {out_path}")
        
        return 0
        
    except KeyboardInterrupt:
        console.print(f"\n{ERROR_MESSAGES['interrupted']}")
        return 130
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def create_argument_parser():
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} CLI - {APP_DESCRIPTION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  %(prog)s -n "+420 731x4x748"
  
  # Use a specific services
  %(prog)s -n "+420 731x4x748" --services seznamcz service2 service3
  
  # Use country-specific prefixes
  %(prog)s -n "+420 xxxxxxxx" --use-country-prefixes
  
  # Use proxy file
  %(prog)s -n "+420 731x4x748" --proxy-file proxies.txt
  
  # Start from specific variation (for resuming)
  %(prog)s -n "+420 xxxxxxxx" --start 50000
  
  # Save results
  %(prog)s -n "+420 731x4x748" --output results.json
  
  # Show service information
  %(prog)s --show-services
        """
    )
    
    parser.add_argument("--number", "-n", help='Phone number pattern with wildcards (x)')
    parser.add_argument("--services", "-s", nargs='+', help='Services to check')
    parser.add_argument("--start", type=int, default=0, help="Start from specific variation number")
    parser.add_argument("--use-country-prefixes", action="store_true", help="Use country-specific mobile prefixes")
    parser.add_argument("--proxy-file", help="File containing proxy list")
    parser.add_argument("--timeout", type=int, default=None, help="Timeout between requests in seconds (default: auto based on selected services)")
    parser.add_argument("--threads", "-t", type=int, default=None, help="Number of worker threads (default: auto based on selected services; 1 = sequential)")
    parser.add_argument("--max-variations", type=int, default=DEFAULT_MAX_VARIATIONS, help=f"Maximum variations to generate (default: {DEFAULT_MAX_VARIATIONS:,})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", "-o", help="Save aggregated found results to JSON/CSV/TXT file (inferred by extension)")
    parser.add_argument("--jsonl-out", help="Stream all per-check results to a JSONL file for durability")
    parser.add_argument("--no-pause", action="store_true", help="Don't pause when accounts are found")
    parser.add_argument("--auto-continue", action="store_true", help="Auto-continue on found accounts")
    parser.add_argument("--no-banner", action="store_true", help="Don't show application banner")
    parser.add_argument("--show-services", action="store_true", help="Show service information and exit")
    parser.add_argument("--show-rate-limits", action="store_true", help="Show rate limiting recommendations")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} CLI v{APP_VERSION}")

    # Per-service outputs
    parser.add_argument("--per-service-out-dir", help="Directory to save per-service outputs (e.g., facebook.json, instagram.json)")
    parser.add_argument("--per-service-format", choices=['json', 'csv', 'txt'], default='json', help="Format for per-service outputs (default: json)")

    # Cross-reference mode and options
    parser.add_argument("--cross-ref", nargs='+', help="Cross-reference mode: provide result files and/or directories to analyze; skips scanning")
    parser.add_argument("--cross-ref-output", help="Path to save cross-reference results; format inferred by extension (json/csv/txt)")
    parser.add_argument("--cross-ref-all", action="store_true", help="Require numbers to appear in all inputs (default: numbers present in at least two)")
    parser.add_argument("--cross-ref-after-scan", action="store_true", help="After scanning and saving per-service outputs, cross-reference automatically without prompting")
    
    return parser


def _print_rate_limit_table(services: List[str]):
    """Render a Rich table with rate limit and proxy info for services."""
    table = Table(title="Service Rate Limit Information", box=box.SIMPLE_HEAD)
    table.add_column("Service", style="bold")
    table.add_column("Recommended Delay (s)", justify="right")
    table.add_column("Est. Max req/min", justify="right")
    table.add_column("Proxy")
    table.add_column("Risk")
    table.add_column("Notes", overflow="fold")
    for service in services:
        cfg = SERVICE_CONFIGURATIONS.get(service)
        if not cfg:
            continue
        table.add_row(
            cfg['name'],
            str(cfg.get('recommended_delay', '')),
            str(cfg.get('max_requests_per_minute', '')),
            ("Recommended" if cfg.get('proxy_recommended', cfg.get('requires_proxy', False)) else "Optional"),
            (cfg.get('rate_limit_severity') or 'unknown').capitalize(),
            cfg.get('description', ''),
        )
    console.print(table)


if __name__ == "__main__":
    sys.exit(main())