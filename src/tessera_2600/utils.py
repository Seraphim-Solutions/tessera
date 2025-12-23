import logging
import time
from typing import List, Dict
from tessera_2600.config import PHONE_PATTERN

logger = logging.getLogger(__name__)

def validate_phone_number(phone_number: str) -> bool:
    """
    Validate phone number format.
    
    Args:
        phone_number: Phone number string to validate
        
    Returns:
        bool: True if valid format, False otherwise
    """
    import re
    # Use central regex from tessera_2600.config to ensure consistency. Validate whole string.
    is_valid = bool(re.fullmatch(PHONE_PATTERN, phone_number, re.IGNORECASE))
    
    if not is_valid:
        logger.debug(f"Invalid phone number format: {phone_number}")
    
    return is_valid

def format_phone_number(phone_number: str) -> str:
    """
    Format phone number for display.
    
    Args:
        phone_number: Raw phone number string
        
    Returns:
        str: Formatted phone number
    """
    return phone_number.strip()

def log_message(message: str, level: str = "INFO"):
    """
    Log a message with the specified level.
    
    Args:
        message: Message to log
        level: Log level (INFO, WARNING, ERROR, DEBUG)
    """
    level = level.upper()
    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)

def load_proxies(proxy_file: str) -> List[str]:
    """
    Load proxy list from file.
    
    Args:
        proxy_file: Path to proxy file
        
    Returns:
        List[str]: List of proxy URLs
    """
    proxies = []
    try:
        with open(proxy_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Add protocol if not present
                if not line.startswith(('http://', 'https://')):
                    line = f"http://{line}"
                
                # Basic validation
                if '://' in line and ':' in line.split('://', 1)[1]:
                    proxies.append(line)
                    logger.debug(f"Loaded proxy: {line}")
                else:
                    logger.warning(f"Invalid proxy format on line {line_num}: {line}")
        
        logger.info(f"Successfully loaded {len(proxies)} proxies from {proxy_file}")
        return proxies
        
    except FileNotFoundError:
        logger.error(f"Proxy file '{proxy_file}' not found")
        return []
    except PermissionError:
        logger.error(f"Permission denied reading proxy file '{proxy_file}'")
        return []
    except Exception as e:
        logger.error(f"Error loading proxies from '{proxy_file}': {e}")
        return []

def sleep_with_message(seconds: int):
    """
    Sleep with a countdown message.
    
    Args:
        seconds: Number of seconds to sleep
    """
    if seconds <= 0:
        return
        
    try:
        for i in range(seconds, 0, -1):
            print(f"\rWaiting {i} seconds...", end='', flush=True)
            time.sleep(1)
        print("\r" + " " * 20 + "\r", end='', flush=True)  # Clear the line
    except KeyboardInterrupt:
        print("\r" + " " * 20 + "\r", end='', flush=True)  # Clear the line
        raise

def confirm_action(message: str, default: bool = False) -> bool:
    """
    Ask user for confirmation.
    
    Args:
        message: Confirmation message
        default: Default choice if user just presses Enter
        
    Returns:
        bool: True if user confirms, False otherwise
    """
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        response = input(f"{message} {suffix}: ").strip().lower()
        
        if not response:  # Empty response, use default
            return default
        
        return response in ('y', 'yes')
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return False
    except EOFError:
        return default

def format_duration(seconds: int) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        str: Formatted duration string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}h {remaining_minutes}m"

def calculate_estimated_time(total_items: int, timeout: int, threads: int = 1) -> str:
    """
    Calculate estimated completion time accounting for threading.
    
    Args:
        total_items: Total number of items to process
        timeout: Timeout between each request
        threads: Number of threads (1 for sequential)
        
    Returns:
        str: Estimated time string
    """
    # Base processing time per request (network request + processing overhead)
    base_processing_time = 2.0  # seconds
    
    if threads <= 1:
        # Sequential processing: timeout + processing time for each item
        estimated_seconds = total_items * (timeout + base_processing_time)
    else:
        # Threaded processing calculation
        # Each thread processes items in parallel, but still needs to respect timeout
        items_per_thread = total_items / threads
        
        # Time for one thread to complete its portion
        # In threading, the timeout still applies but work is distributed
        time_per_thread = items_per_thread * (timeout + base_processing_time)
        
        # Add some overhead for thread coordination and resource contention
        thread_overhead = 1.2  # 20% overhead for coordination
        
        # The total time is roughly the time for the slowest thread
        estimated_seconds = time_per_thread * thread_overhead
        
        # Add a small constant overhead for thread startup/shutdown
        startup_overhead = min(30, threads * 2)  # Max 30 seconds, or 2 seconds per thread
        estimated_seconds += startup_overhead
    
    return format_duration(int(estimated_seconds))

def truncate_string(text: str, max_length: int = 50) -> str:
    """
    Truncate string if it's too long.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        str: Truncated string with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def print_separator(char: str = "=", length: int = 60):
    """
    Print a separator line.
    
    Args:
        char: Character to use for separator
        length: Length of separator
    """
    print(char * length)

def print_header(title: str):
    """
    Print a formatted header.
    
    Args:
        title: Header title
    """
    print_separator()
    print(f" {title}")
    print_separator()

def wait_for_user_input(message: str = "Press Enter to continue", timeout: int = None) -> bool:
    """
    Wait for user input with optional timeout.
    
    Args:
        message: Message to display to user
        timeout: Optional timeout in seconds (None for no timeout)
        
    Returns:
        bool: True if user pressed Enter, False if timeout or interrupted
    """
    import select
    import sys
    
    print(f"\nPause: {message}...")
    
    try:
        if timeout is None:
            # Wait indefinitely for user input
            input()
            return True
        else:
            # Wait with timeout (Unix/Linux only)
            if hasattr(select, 'select'):
                ready, _, _ = select.select([sys.stdin], [], [], timeout)
                if ready:
                    input()
                    return True
                else:
                    print(f"\nTimeout after {timeout}s, continuing automatically...")
                    return False
            else:
                # Fallback for Windows - just wait for input
                input()
                return True
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        raise
    except EOFError:
        return True

def pause_on_found(found_result: str, phone_number: str, platform: str, auto_continue: bool = False) -> bool:
    """
    Pause execution when an account is found, unless auto-continue is enabled.
    
    Args:
        found_result: The result string from the checker
        phone_number: The phone number that was found
        platform: The platform where it was found
        auto_continue: If True, don't pause and continue automatically
        
    Returns:
        bool: True to continue, False to stop
    """
    from tessera_2600.config import SUCCESS_MESSAGES
    
    print(f"\n{'='*60}")
    print(f"ACCOUNT FOUND!")
    print(f"Phone: {phone_number}")
    print(f"Platform: {platform}")
    print(f"Details: {found_result}")
    print(f"{'='*60}")
    
    if auto_continue:
        print(f"{SUCCESS_MESSAGES['auto_continuing']}")
        time.sleep(2)  # Brief pause to let user see the result
        return True
    
    try:
        response = input("\nAccount found! What would you like to do?\n"
                        "  [ENTER] Continue checking\n"
                        "  [s] Stop and exit\n"
                        "  [a] Enable auto-continue for remaining checks\n"
                        "Choice: ").strip().lower()
        
        if response == 's':
            print("Stopping as requested by user")
            return False
        elif response == 'a':
            print("Auto-continue enabled for remaining checks")
            return 'auto'  # Special return value to enable auto-continue
        else:
            print(f"{SUCCESS_MESSAGES['user_continued']}")
            return True
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        raise
    except EOFError:
        return True

def get_pause_choice() -> str:
    """
    Get user's choice when pausing after finding an account.
    
    Returns:
        str: 'continue', 'stop', 'auto', or 'recent'
    """
    try:
        print("\nAccount found! What would you like to do?")
        print("  [ENTER] Continue checking")
        print("  [s] Stop and exit")
        print("  [a] Enable auto-continue for remaining checks")
        print("  [r] Show recent found accounts")
        
        response = input("Choice: ").strip().lower()
        
        if response == 's' or response == 'stop':
            return 'stop'
        elif response == 'a' or response == 'auto':
            return 'auto'
        elif response == 'r' or response == 'recent':
            return 'recent'
        else:  # Default to continue on any other input (including empty)
            return 'continue'
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        raise
    except EOFError:
        return 'continue'

def show_found_summary(found_accounts: List[Dict], current_index: int, total_variations: int):
    """
    Show a summary of recently found accounts.
    
    Args:
        found_accounts: List of found account dictionaries
        current_index: Current processing index
        total_variations: Total number of variations
    """
    if not found_accounts:
        print("\nNo accounts found yet.")
        return
    
    print(f"\n{'='*60}")
    print(f"FOUND ACCOUNTS SUMMARY ({len(found_accounts)} total)")
    print(f"{'='*60}")
    print(f"Progress: {current_index}/{total_variations} variations checked")
    print()
    
    # Show last 10 found accounts (most recent first)
    recent_accounts = found_accounts[-10:]
    for i, account in enumerate(reversed(recent_accounts), 1):
        time_ago = int(time.time() - account.get('timestamp', 0))
        time_str = format_duration(time_ago) if time_ago > 0 else "just now"
        worker_info = f" by worker {account.get('worker_id', '?')}" if 'worker_id' in account else ""
        
        print(f"  {i:2d}. {account['number']}")
        print(f"      {account['platform']}: {account['result']}")
        print(f"      Found {time_str} ago (variation #{account.get('index', '?')}){worker_info}")
        print()
    
    if len(found_accounts) > 10:
        print(f"   ... and {len(found_accounts) - 10} more")
    
    print(f"{'='*60}")