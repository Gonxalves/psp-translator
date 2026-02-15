"""
Glossary Fetcher with Caching

Retrieves the French-English glossary from an Excel file (OneDrive synced)
and caches results for performance.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv

from tools.excel_client import get_client, get_glossary_path, ensure_glossary_exists

# Load environment variables
load_dotenv()

# Configuration
CACHE_FILE = Path(__file__).parent.parent / '.tmp' / 'cached_glossary.json'
CACHE_TTL_MINUTES = int(os.getenv('CACHE_TTL_MINUTES', '5'))
GLOSSARY_SHEET_NAME = os.getenv('GLOSSARY_SHEET_NAME', 'Glossary')


def fetch_glossary(force_refresh: bool = False) -> Dict[str, str]:
    """
    Fetch the glossary from Excel file with caching.

    The glossary is expected to have:
    - Column A: French Term
    - Column B: English Term
    - Column C: Notes/Context (optional)

    Args:
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        Dictionary mapping French terms to English terms

    Raises:
        ValueError: If EXCEL_GLOSSARY_PATH is not set in .env
        Exception: If Excel file read fails
    """
    # Check if glossary path is configured
    try:
        glossary_path = get_glossary_path()
    except ValueError as e:
        raise e

    # Try to load from cache first (if not force refreshing)
    if not force_refresh:
        cached_glossary, cache_valid = _load_from_cache()
        if cache_valid and cached_glossary is not None:
            print(f"[OK] Loaded glossary from cache ({len(cached_glossary)} terms)")
            return cached_glossary

    # Fetch fresh data from Excel file
    print("Fetching glossary from Excel file...")
    try:
        # Download latest version from SharePoint (if configured)
        from tools.sharepoint_client import is_sharepoint_enabled, download_glossary
        if is_sharepoint_enabled():
            print("Syncing glossary from SharePoint...")
            download_glossary(str(glossary_path))

        # Ensure file exists (creates with headers if not)
        ensure_glossary_exists()

        client = get_client()
        values = client.read_sheet(glossary_path, GLOSSARY_SHEET_NAME)

        if not values:
            print("Warning: No data found in glossary file")
            return {}

        # Parse into dictionary (skip header row)
        glossary = {}
        for i, row in enumerate(values):
            # Skip header row
            if i == 0 and len(row) > 0 and row[0].lower() in ['french term', 'terme français', 'french']:
                continue

            # Skip if row is empty or has less than 2 columns
            if len(row) < 2:
                continue

            french_term = row[0].strip()
            english_term = row[1].strip()

            # Skip empty terms
            if not french_term or not english_term:
                continue

            # Store in dictionary
            glossary[french_term] = english_term

        # Save to cache
        _save_to_cache(glossary)

        print(f"[OK] Fetched {len(glossary)} terms from Excel file")
        return glossary

    except Exception as e:
        print(f"[ERROR] Error fetching glossary: {e}")

        # Try to fall back to cached data even if expired
        cached_glossary, _ = _load_from_cache()
        if cached_glossary:
            print(f"[WARNING] Using expired cache ({len(cached_glossary)} terms)")
            return cached_glossary

        raise


def _load_from_cache() -> Tuple[Optional[Dict[str, str]], bool]:
    """
    Load glossary from cache file.

    Returns:
        Tuple of (glossary_dict, is_valid)
        - glossary_dict: The cached glossary or None if cache doesn't exist
        - is_valid: True if cache exists and is not expired
    """
    if not CACHE_FILE.exists():
        return None, False

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        # Check if cache is expired
        cached_time = datetime.fromisoformat(cache_data['timestamp'])
        cache_age = datetime.now() - cached_time

        is_valid = cache_age < timedelta(minutes=CACHE_TTL_MINUTES)

        return cache_data['glossary'], is_valid

    except Exception as e:
        print(f"Warning: Failed to load cache: {e}")
        return None, False


def _save_to_cache(glossary: Dict[str, str]):
    """
    Save glossary to cache file.

    Args:
        glossary: Dictionary mapping French terms to English terms
    """
    try:
        # Ensure cache directory exists
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'glossary': glossary,
            'term_count': len(glossary)
        }

        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        print(f"[OK] Saved glossary to cache")

    except Exception as e:
        print(f"Warning: Failed to save cache: {e}")


def invalidate_cache():
    """
    Delete the cache file to force a fresh fetch on next request.
    Used when glossary is updated.
    """
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print("[OK] Cache invalidated")


def get_glossary_stats() -> dict:
    """
    Get statistics about the cached glossary.

    Returns:
        Dictionary with cache status, term count, and last update time
    """
    if not CACHE_FILE.exists():
        return {
            'cached': False,
            'term_count': 0,
            'last_updated': None,
            'cache_valid': False
        }

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        cached_time = datetime.fromisoformat(cache_data['timestamp'])
        cache_age = datetime.now() - cached_time
        is_valid = cache_age < timedelta(minutes=CACHE_TTL_MINUTES)

        return {
            'cached': True,
            'term_count': cache_data['term_count'],
            'last_updated': cached_time.strftime('%Y-%m-%d %H:%M:%S'),
            'cache_valid': is_valid,
            'cache_age_minutes': int(cache_age.total_seconds() / 60)
        }

    except Exception as e:
        return {
            'cached': False,
            'term_count': 0,
            'last_updated': None,
            'cache_valid': False,
            'error': str(e)
        }


if __name__ == "__main__":
    # Test the glossary fetcher
    print("Testing Glossary Fetcher...")
    print("-" * 50)

    try:
        # Test fetching glossary
        glossary = fetch_glossary()
        print(f"\nGlossary loaded successfully!")
        print(f"Total terms: {len(glossary)}")

        # Show sample terms (first 5)
        print("\nSample terms:")
        for i, (fr, en) in enumerate(list(glossary.items())[:5]):
            print(f"  {fr} -> {en}")

        # Show cache stats
        print("\nCache statistics:")
        stats = get_glossary_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
