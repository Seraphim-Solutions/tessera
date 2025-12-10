#!/usr/bin/env python3
"""
Results Handler Module
Handles saving and managing results from phone number checks.
"""

import os
import json
import time
import logging
from typing import List, Dict, Optional, Any
from tessera_2600.core.models import CheckResult

logger = logging.getLogger(__name__)

class ResultsHandler:
    """Handles saving and managing results from phone number checks (CLI-only)."""
    
    def __init__(self):
        pass
    
    def save_results(self, found_accounts: List[Dict[str, Any]], output_file: str, *, output_format: Optional[str] = None, number_format: str = 'local') -> bool:
        """Save aggregated results to file with conflict handling and multiple formats.
        Only 'found' accounts are expected in found_accounts.
        Each item should include: number, platform, status, details, timestamp, index.
        """
        if not output_file or not found_accounts:
            if not found_accounts:
                print("No accounts to save.")
            return False
        
        final_filepath = output_file
        fmt = (output_format or self._infer_format_from_path(output_file)).lower()
        accounts = self._format_numbers(found_accounts, number_format)
        data_to_save = {
            'timestamp': time.time(),
            'total_found': len(accounts),
            'accounts': accounts
        }
        
        # Only JSON supports merge for now
        merge_supported = fmt == 'json'
        if os.path.exists(output_file):
            choice = self._confirm_file_conflict(output_file)
            
            if choice == 'cancel':
                print("Save operation cancelled by user.")
                return False
            
            elif choice == 'merge' and merge_supported:
                existing_data = self._load_existing_results(output_file)
                if existing_data is not None:
                    data_to_save = self._merge_results(existing_data, accounts)
                else:
                    print("Could not read existing file for merging. Will overwrite instead.")
            
            elif choice == 'new':
                try:
                    final_filepath = self._generate_new_filename(output_file)
                    print(f"Will save to new file: {final_filepath}")
                except ValueError as e:
                    print(f"Error generating new filename: {e}")
                    return False
            # overwrite is default
        
        try:
            os.makedirs(os.path.dirname(final_filepath) if os.path.dirname(final_filepath) else '.', exist_ok=True)
            
            if fmt == 'json':
                with open(final_filepath, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            elif fmt == 'csv':
                self._write_csv(final_filepath, accounts)
            elif fmt == 'txt':
                self._write_txt(final_filepath, accounts)
            else:
                print(f"Unsupported output format: {fmt}")
                return False
            
            print(f"Results saved to {final_filepath}")
            
            if 'merge_info' in data_to_save:
                print("File was merged with existing results.")
            elif final_filepath != output_file:
                print("File was saved with a new name to avoid conflicts.")
            
            return True
            
        except PermissionError:
            print(f"Error: Permission denied writing to {final_filepath}")
            return False
        except OSError as e:
            print(f"Error saving results to {final_filepath}: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error saving results: {e}")
            return False
    
    def _confirm_file_conflict(self, filepath: str) -> str:
        """Ask user what to do when output file already exists."""
        # Get file info
        file_info = {}
        try:
            stat = os.stat(filepath)
            file_info = {
                'size': stat.st_size,
                'modified': time.ctime(stat.st_mtime)
            }
        except:
            pass
        
        # Check if we have Rich UI available and use it
        if (self.display_manager and 
            hasattr(self.display_manager, '_ui_impl') and 
            hasattr(self.display_manager._ui_impl, 'show_file_conflict_dialog')):
            return self.display_manager._ui_impl.show_file_conflict_dialog(filepath, file_info)
        else:
            return self._basic_file_conflict(filepath, file_info)
    
    def _basic_file_conflict(self, filepath: str, file_info: Dict) -> str:
        """Basic text implementation of file conflict resolution."""
        print(f"\nFile '{filepath}' already exists!")
        
        if file_info:
            print(f"  File size: {file_info.get('size', 'unknown')} bytes")
            print(f"  Last modified: {file_info.get('modified', 'unknown')}")
        
        while True:
            try:
                print("\nWhat would you like to do?")
                print("  [m] Merge with existing results")
                print("  [o] Overwrite the existing file")
                print("  [n] Create a new file with different name")
                print("  [c] Cancel and don't save")
                
                response = input("Choice: ").strip().lower()
                
                if response in ('m', 'merge'):
                    return 'merge'
                elif response in ('o', 'overwrite'):
                    return 'overwrite'
                elif response in ('n', 'new'):
                    return 'new'
                elif response in ('c', 'cancel'):
                    return 'cancel'
                else:
                    print("Invalid choice. Please enter 'm', 'o', 'n', or 'c'.")
                    
            except KeyboardInterrupt:
                print("\nOperation cancelled by user")
                return 'cancel'
            except EOFError:
                return 'cancel'
    
    def _infer_format_from_path(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext == '.json':
            return 'json'
        if ext == '.csv':
            return 'csv'
        if ext in ('.txt', '.log'):
            return 'txt'
        return 'json'
    
    def _write_csv(self, filepath: str, accounts: List[Dict[str, Any]]):
        import csv
        fieldnames = ['number', 'platform', 'status', 'timestamp', 'index']
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for a in accounts:
                row = {
                    'number': a.get('number', ''),
                    'platform': a.get('platform', ''),
                    'status': a.get('status') or a.get('result', ''),
                    'timestamp': a.get('timestamp', ''),
                    'index': a.get('index', ''),
                }
                writer.writerow(row)
    
    def _write_txt(self, filepath: str, accounts: List[Dict[str, Any]]):
        with open(filepath, 'w', encoding='utf-8') as f:
            for a in accounts:
                status = a.get('status') or a.get('result', '')
                f.write(f"{a.get('number','')} | {a.get('platform','')} | {status}\n")
    
    # Template output removed in CLI-only version
    
    def _format_numbers(self, accounts: List[Dict[str, Any]], number_format: str) -> List[Dict[str, Any]]:
        from tessera_2600.services.utils import format_international_phone
        formatted = []
        for a in accounts:
            num = a.get('number', '')
            try:
                if number_format == 'intl':
                    num = format_international_phone(num)
                elif number_format == 'raw':
                    num = ''.join(ch for ch in num if ch.isdigit() or ch == '+')
                # else 'local' keep as-is
            except Exception:
                pass
            b = dict(a)
            b['number'] = num
            formatted.append(b)
        return formatted

    def append_jsonl(self, filepath: str, result: CheckResult) -> None:
        """Append a single CheckResult as JSONL line for durability."""
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'a', encoding='utf-8') as f:
            json.dump(result.to_dict(), f)
            f.write('\n')
    
    def _load_existing_results(self, filepath: str) -> Optional[Dict]:
        """Load existing results from JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
            print(f"Warning: Could not read existing file for merging: {e}")
            return None
    
    def _merge_results(self, existing_data: Dict, new_accounts: List[Dict]) -> Dict:
        """Merge new results with existing results."""
        existing_accounts = existing_data.get('accounts', [])
        
        existing_numbers = set()
        for account in existing_accounts:
            number = account.get('number', '')
            platform = account.get('platform', '')
            existing_numbers.add(f"{number}:{platform}")
        
        added_count = 0
        for account in new_accounts:
            number = account.get('number', '')
            platform = account.get('platform', '')
            key = f"{number}:{platform}"
            
            if key not in existing_numbers:
                existing_accounts.append(account)
                existing_numbers.add(key)
                added_count += 1
        
        merged_data = {
            'timestamp': time.time(),
            'last_merge': time.time(),
            'total_found': len(existing_accounts),
            'accounts': existing_accounts,
            'merge_info': {
                'new_accounts_added': added_count,
                'duplicates_skipped': len(new_accounts) - added_count,
                'previous_timestamp': existing_data.get('timestamp'),
                'previous_total': existing_data.get('total_found', 0)
            }
        }
        
        print(f"Merge summary:")
        print(f"  Previous accounts: {existing_data.get('total_found', 0)}")
        print(f"  New accounts added: {added_count}")
        print(f"  Duplicates skipped: {len(new_accounts) - added_count}")
        print(f"  Total after merge: {len(existing_accounts)}")
        
        return merged_data
    
    def _generate_new_filename(self, original_filepath: str) -> str:
        """Generate a new filename by adding a number suffix."""
        base_path, ext = os.path.splitext(original_filepath)
        counter = 1
        
        while True:
            new_path = f"{base_path}_{counter}{ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1
            
            if counter > 1000:
                raise ValueError("Could not generate unique filename after 1000 attempts")