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
    
    # -----------------
    # Per-service saves
    # -----------------
    def save_per_service_results(self,
                                 found_accounts: List[Dict[str, Any]],
                                 out_dir: str,
                                 *,
                                 output_format: Optional[str] = None,
                                 number_format: str = 'local',
                                 filename_pattern: str = '{service}.{ext}') -> Dict[str, str]:
        """Save results split per service/platform.

        Returns a mapping {service_key: file_path} for files that were written.
        """
        if not found_accounts:
            print("No accounts to save per service.")
            return {}

        fmt = (output_format or 'json').lower()
        if fmt not in ('json', 'csv', 'txt'):
            print(f"Unsupported per-service format: {fmt}")
            return {}

        os.makedirs(out_dir or '.', exist_ok=True)

        # Group by platform
        by_platform: Dict[str, List[Dict[str, Any]]] = {}
        for a in found_accounts:
            p = a.get('platform') or 'unknown'
            by_platform.setdefault(p, []).append(a)

        written: Dict[str, str] = {}
        for platform, accounts in by_platform.items():
            accounts_fmt = self._format_numbers(accounts, number_format)
            ext = fmt
            filepath = os.path.join(out_dir, filename_pattern.format(service=platform, ext=ext))
            try:
                if fmt == 'json':
                    data = {
                        'timestamp': time.time(),
                        'service': platform,
                        'total_found': len(accounts_fmt),
                        'accounts': accounts_fmt,
                    }
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                elif fmt == 'csv':
                    self._write_csv(filepath, accounts_fmt)
                elif fmt == 'txt':
                    self._write_txt(filepath, accounts_fmt)
                print(f"Saved {len(accounts_fmt)} accounts for {platform} -> {filepath}")
                written[platform] = filepath
            except Exception as e:
                print(f"Error saving per-service file for {platform}: {e}")

        return written
    
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
    
    # ----------------------
    # Cross-reference logic
    # ----------------------
    def cross_reference_files(self,
                               inputs: List[str],
                               output_file: str,
                               *,
                               output_format: Optional[str] = None,
                               require_all: bool = False,
                               number_format: str = 'local') -> bool:
        """Cross-reference multiple result files/directories and save numbers appearing
        in multiple files (>=2) or in all files (require_all=True).
        """
        files = self._collect_input_files(inputs)
        if len(files) < 2:
            print("Need at least two input files to cross-reference.")
            return False

        # Map: file -> set(numbers)
        per_file_numbers: Dict[str, set] = {}
        number_services: Dict[str, set] = {}

        for fp in files:
            try:
                accounts = self._read_any_results(fp)
                nums_for_file = set()
                for a in accounts:
                    num = a.get('number')
                    if not num:
                        continue
                    nums_for_file.add(num)
                    svc = a.get('platform') or self._infer_service_from_filename(fp)
                    if svc:
                        number_services.setdefault(num, set()).add(svc)
                per_file_numbers[fp] = nums_for_file
            except Exception as e:
                print(f"Warning: Skipping {fp}: {e}")

        # Determine candidate numbers
        if require_all:
            # Intersection across all files
            common = None
            for s in per_file_numbers.values():
                common = s if common is None else (common & s)
            candidate_numbers = common or set()
        else:
            # Numbers appearing in at least 2 files
            counts: Dict[str, int] = {}
            for s in per_file_numbers.values():
                for n in s:
                    counts[n] = counts.get(n, 0) + 1
            candidate_numbers = {n for n, c in counts.items() if c >= 2}

        # Build records
        records: List[Dict[str, Any]] = []
        for num in sorted(candidate_numbers):
            services = sorted(number_services.get(num, []))
            records.append({'number': num, 'services': services, 'occurrences': len(services)})

        fmt = (output_format or self._infer_format_from_path(output_file)).lower()
        try:
            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            if fmt == 'json':
                data = {
                    'timestamp': time.time(),
                    'require_all': require_all,
                    'inputs': files,
                    'total_numbers': len(records),
                    'numbers': records,
                }
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif fmt == 'csv':
                self._write_crossref_csv(output_file, records)
            elif fmt == 'txt':
                self._write_crossref_txt(output_file, records)
            else:
                print(f"Unsupported output format: {fmt}")
                return False
            print(f"Cross-reference saved to {output_file} ({len(records)} numbers)")
            return True
        except Exception as e:
            print(f"Error writing cross-reference file: {e}")
            return False

    def _collect_input_files(self, inputs: List[str]) -> List[str]:
        """Expand files and directories into a flat list of candidate files."""
        from glob import glob
        from tessera_2600.config import OUTPUT_FILE_PATTERNS
        files: List[str] = []
        for p in inputs:
            if os.path.isdir(p):
                for pat in OUTPUT_FILE_PATTERNS:
                    files.extend(sorted(glob(os.path.join(p, pat))))
            else:
                files.append(p)
        # Filter to existing files only
        return [f for f in files if os.path.isfile(f)]

    def _read_any_results(self, filepath: str) -> List[Dict[str, Any]]:
        """Read results from JSON/CSV/TXT produced by this tool."""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.json':
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'accounts' in data:
                    return data['accounts']
                if isinstance(data, dict) and 'numbers' in data:
                    # cross-ref JSON style
                    return [{'number': n.get('number'), 'platform': None} for n in data['numbers']]
                raise ValueError('Unsupported JSON structure')
        elif ext == '.csv':
            import csv
            rows: List[Dict[str, Any]] = []
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({'number': row.get('number'), 'platform': row.get('platform')})
            return rows
        elif ext in ('.txt', '.log'):
            rows: List[Dict[str, Any]] = []
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    # Expect: number | platform | status
                    parts = [p.strip() for p in line.strip().split('|')]
                    if not parts or not parts[0]:
                        continue
                    number = parts[0]
                    platform = parts[1] if len(parts) > 1 else None
                    rows.append({'number': number, 'platform': platform})
            return rows
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _infer_service_from_filename(self, filepath: str) -> Optional[str]:
        base = os.path.basename(filepath)
        name, _ = os.path.splitext(base)
        return name

    def _write_crossref_csv(self, filepath: str, records: List[Dict[str, Any]]):
        import csv
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['number', 'occurrences', 'services'])
            writer.writeheader()
            for r in records:
                writer.writerow({
                    'number': r['number'],
                    'occurrences': r.get('occurrences', 0),
                    'services': ','.join(r.get('services', []))
                })

    def _write_crossref_txt(self, filepath: str, records: List[Dict[str, Any]]):
        with open(filepath, 'w', encoding='utf-8') as f:
            for r in records:
                f.write(f"{r['number']} | {r.get('occurrences', 0)} | {','.join(r.get('services', []))}\n")
    
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