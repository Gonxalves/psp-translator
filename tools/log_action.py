"""
Action Logger

Logs term-checking actions to an Excel file for tracking and analysis.
"""

import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from tools.excel_client import get_client, get_action_log_path, ensure_action_log_exists

# Load environment variables
load_dotenv()

# Configuration
ACTION_LOG_SHEET_NAME = os.getenv('ACTION_LOG_SHEET_NAME', 'Action Log')


def log(
    french_term: str,
    english_term: str,
    source: str,
    added_to_glossary: bool,
    timestamp: Optional[datetime] = None
) -> bool:
    """
    Log a term-checking action to Excel file.

    Expected Excel structure (Action Log sheet):
    Column A: Timestamp
    Column B: French Term
    Column C: English Term
    Column D: Source (TERMIUM/OQLF)
    Column E: Added to Glossary (YES/NO)

    Args:
        french_term: The French term that was checked
        english_term: The English translation selected
        source: Source of the translation ("TERMIUM" or "OQLF")
        added_to_glossary: Whether the term was added to the glossary
        timestamp: Optional timestamp (defaults to now)

    Returns:
        True if logging successful, False otherwise

    Raises:
        ValueError: If EXCEL_ACTION_LOG_PATH is not set
    """
    # Check if action log path is configured
    try:
        action_log_path = get_action_log_path()
    except ValueError as e:
        raise e

    # Use current time if timestamp not provided
    if timestamp is None:
        timestamp = datetime.now()

    # Format timestamp
    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')

    # Format added_to_glossary as YES/NO
    added_str = "YES" if added_to_glossary else "NO"

    # Prepare row data
    row_data = [[
        timestamp_str,
        french_term,
        english_term,
        source,
        added_str
    ]]

    try:
        # Ensure file exists
        ensure_action_log_exists()

        # Get Excel client
        client = get_client()

        # Append row to Action Log file
        result = client.append_row(
            file_path=action_log_path,
            sheet_name=ACTION_LOG_SHEET_NAME,
            values=row_data
        )

        print(f"[OK] Action logged: {french_term} -> {english_term} (from {source})")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to log action: {e}")
        return False


def log_translation(
    glossary_used: bool,
    timestamp: Optional[datetime] = None
) -> bool:
    """
    Log a translation action to Excel file (basic: timestamp + glossary used).

    Row format: [Timestamp, "TRANSLATION", "", "TRANSLATION", glossary_used (YES/NO)]

    Args:
        glossary_used: Whether glossary terms were found in the source text
        timestamp: Optional timestamp (defaults to now)

    Returns:
        True if logging successful, False otherwise
    """
    try:
        action_log_path = get_action_log_path()
    except ValueError as e:
        raise e

    if timestamp is None:
        timestamp = datetime.now()

    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
    glossary_str = "YES" if glossary_used else "NO"

    row_data = [[
        timestamp_str,
        "TRANSLATION",
        "",
        "TRANSLATION",
        glossary_str
    ]]

    try:
        ensure_action_log_exists()
        client = get_client()

        client.append_row(
            file_path=action_log_path,
            sheet_name=ACTION_LOG_SHEET_NAME,
            values=row_data
        )

        print(f"[OK] Translation logged (glossary used: {glossary_str})")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to log translation: {e}")
        return False


def get_action_stats(limit: int = 100) -> dict:
    """
    Retrieve statistics about logged actions.

    Args:
        limit: Maximum number of recent actions to analyze

    Returns:
        Dictionary containing:
        - total_actions: Total number of logged actions
        - termium_count: Number of TERMIUM lookups
        - oqlf_count: Number of OQLF lookups
        - added_to_glossary_count: Number of terms added to glossary
        - most_checked_terms: List of most frequently checked terms
    """
    try:
        action_log_path = get_action_log_path()
    except ValueError:
        return {
            'error': 'EXCEL_ACTION_LOG_PATH not configured',
            'total_actions': 0
        }

    try:
        # Ensure file exists
        ensure_action_log_exists()

        # Get Excel client
        client = get_client()

        # Read action log
        values = client.read_sheet(action_log_path, ACTION_LOG_SHEET_NAME)

        if not values:
            return {
                'total_actions': 0,
                'termium_count': 0,
                'oqlf_count': 0,
                'added_to_glossary_count': 0,
                'most_checked_terms': []
            }

        # Skip header row if present
        if values[0][0].lower() in ['timestamp', 'date', 'time']:
            values = values[1:]

        # Analyze data
        total_actions = len(values)
        termium_count = sum(1 for row in values if len(row) > 3 and row[3] == 'TERMIUM')
        oqlf_count = sum(1 for row in values if len(row) > 3 and row[3] == 'OQLF')
        added_count = sum(1 for row in values if len(row) > 4 and row[4] == 'YES')

        # Count term frequencies
        term_counts = {}
        for row in values:
            if len(row) > 1:
                french_term = row[1]
                term_counts[french_term] = term_counts.get(french_term, 0) + 1

        # Get top terms
        most_checked = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'total_actions': total_actions,
            'termium_count': termium_count,
            'oqlf_count': oqlf_count,
            'added_to_glossary_count': added_count,
            'most_checked_terms': [{'term': term, 'count': count} for term, count in most_checked]
        }

    except Exception as e:
        print(f"[ERROR] Failed to get action stats: {e}")
        return {
            'error': str(e),
            'total_actions': 0
        }


if __name__ == "__main__":
    # Test the action logger
    print("Testing Action Logger...")
    print("-" * 50)

    # Test logging an action
    try:
        success = log(
            french_term="couleur",
            english_term="colour",
            source="TERMIUM",
            added_to_glossary=True
        )

        if success:
            print("\n[OK] Test action logged successfully")
        else:
            print("\n[ERROR] Failed to log test action")

        # Get action stats
        print("\nAction Statistics:")
        print("-" * 50)
        stats = get_action_stats()

        print(f"Total actions: {stats.get('total_actions', 0)}")
        print(f"TERMIUM lookups: {stats.get('termium_count', 0)}")
        print(f"OQLF lookups: {stats.get('oqlf_count', 0)}")
        print(f"Added to glossary: {stats.get('added_to_glossary_count', 0)}")

        if stats.get('most_checked_terms'):
            print("\nMost checked terms:")
            for item in stats['most_checked_terms'][:5]:
                print(f"  {item['term']}: {item['count']} time(s)")

    except Exception as e:
        print(f"\n[ERROR] {e}")
