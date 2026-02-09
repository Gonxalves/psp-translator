"""
Action Log Setup Script

This script helps you set up and verify the Action Log in Google Sheets.
"""

import sys
from tools.google_sheets_client import get_client
from tools.log_action import log, get_action_stats
from datetime import datetime


def verify_sheet_access():
    """Verify we can access the Google Sheet."""
    print("Step 1: Verifying Google Sheets access...")
    print("-" * 60)

    try:
        client = get_client()
        print("[OK] Google Sheets authentication successful")
        return client
    except Exception as e:
        print(f"[ERROR] Failed to authenticate: {e}")
        print("\nPlease ensure:")
        print("  1. credentials.json is in the project root")
        print("  2. You've authorized the app (token.json)")
        return None


def check_action_log_structure(client, sheet_id):
    """Check if Action Log tab exists with proper headers."""
    print("\nStep 2: Checking Action Log structure...")
    print("-" * 60)

    try:
        # Try to read the first row (headers)
        values = client.read_sheet(sheet_id, 'Action Log!A1:E1')

        if not values:
            print("[ERROR] Action Log tab exists but has no headers")
            print("\nRequired headers (Row 1):")
            print("  A1: Timestamp")
            print("  B1: French Term")
            print("  C1: English Term")
            print("  D1: Source")
            print("  E1: Added to Glossary")
            return False

        headers = values[0] if values else []
        expected = ["Timestamp", "French Term", "English Term", "Source", "Added to Glossary"]

        if len(headers) >= 5 and headers[:5] == expected:
            print("[OK] Action Log tab found with correct headers")
            return True
        else:
            print(f"[ERROR] Headers don't match expected format")
            print(f"  Found: {headers}")
            print(f"  Expected: {expected}")
            return False

    except Exception as e:
        error_msg = str(e)
        if "Unable to parse range" in error_msg or "not found" in error_msg.lower():
            print("[ERROR] Action Log tab not found")
            print("\nManual Setup Required:")
            print("  1. Open your Google Sheet:")
            print(f"     https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
            print("  2. Create a new tab called 'Action Log'")
            print("  3. Add these headers in Row 1:")
            print("     A1: Timestamp")
            print("     B1: French Term")
            print("     C1: English Term")
            print("     D1: Source")
            print("     E1: Added to Glossary")
            print("  4. Run this script again")
            return False
        else:
            print(f"[ERROR] Error checking structure: {e}")
            return False


def test_logging(client, sheet_id):
    """Test logging a sample action."""
    print("\nStep 3: Testing action logging...")
    print("-" * 60)

    try:
        # Log a test action
        test_term = f"test_{datetime.now().strftime('%H%M%S')}"
        success = log(
            french_term=test_term,
            english_term="test_translation",
            source="TEST",
            added_to_glossary=False
        )

        if success:
            print(f"[OK] Test action logged successfully: {test_term}")
            return True
        else:
            print("[ERROR] Failed to log test action")
            return False

    except Exception as e:
        print(f"[ERROR] Error logging test action: {e}")
        return False


def display_stats():
    """Display current action log statistics."""
    print("\nStep 4: Retrieving action log statistics...")
    print("-" * 60)

    try:
        stats = get_action_stats()

        if 'error' in stats:
            print(f"[WARNING] {stats['error']}")
            return

        print(f"Total logged actions: {stats['total_actions']}")
        print(f"TERMIUM lookups: {stats['termium_count']}")
        print(f"OQLF lookups: {stats['oqlf_count']}")
        print(f"Terms added to glossary: {stats['added_to_glossary_count']}")

        if stats.get('most_checked_terms'):
            print("\nMost frequently checked terms:")
            for item in stats['most_checked_terms'][:5]:
                print(f"  - {item['term']}: {item['count']} time(s)")

    except Exception as e:
        print(f"[ERROR] Error retrieving stats: {e}")


def main():
    """Run the setup verification process."""
    print("\n" + "=" * 60)
    print("ACTION LOG SETUP & VERIFICATION")
    print("=" * 60 + "\n")

    # Get sheet ID from environment
    import os
    from dotenv import load_dotenv
    load_dotenv()

    sheet_id = os.getenv('GOOGLE_SHEETS_ACTION_LOG_ID')
    if not sheet_id:
        print("[ERROR] GOOGLE_SHEETS_ACTION_LOG_ID not set in .env file")
        return 1

    print(f"Target Sheet ID: {sheet_id}\n")

    # Step 1: Verify authentication
    client = verify_sheet_access()
    if not client:
        return 1

    # Step 2: Check structure
    structure_ok = check_action_log_structure(client, sheet_id)
    if not structure_ok:
        return 1

    # Step 3: Test logging
    logging_ok = test_logging(client, sheet_id)
    if not logging_ok:
        return 1

    # Step 4: Display stats
    display_stats()

    # Success!
    print("\n" + "=" * 60)
    print("[SUCCESS] ACTION LOG SETUP COMPLETE!")
    print("=" * 60)
    print("\nYour Action Log is ready to use.")
    print("All term lookups and glossary additions will be tracked.")
    print(f"\nView your log: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
