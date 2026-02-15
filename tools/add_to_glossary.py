"""
Glossary Updater

Adds new French-English term pairs to the glossary Excel file.
"""

import os
from typing import Optional, Tuple
from dotenv import load_dotenv

from tools.excel_client import get_client, get_glossary_path, ensure_glossary_exists
from tools.fetch_glossary import invalidate_cache, fetch_glossary

# Load environment variables
load_dotenv()

# Configuration
GLOSSARY_SHEET_NAME = os.getenv('GLOSSARY_SHEET_NAME', 'Glossary')


def add(
    french_term: str,
    english_term: str,
    notes: str = "",
    check_duplicates: bool = True
) -> Tuple[bool, str]:
    """
    Add a new term pair to the glossary Excel file.

    Expected Excel structure:
    Column A: French Term
    Column B: English Term
    Column C: Notes/Context

    Args:
        french_term: The French term to add
        english_term: The English translation
        notes: Optional notes or context
        check_duplicates: If True, check for existing terms before adding

    Returns:
        Tuple of (success: bool, message: str)

    Raises:
        ValueError: If EXCEL_GLOSSARY_PATH is not set
    """
    # Check if glossary path is configured
    try:
        glossary_path = get_glossary_path()
    except ValueError as e:
        raise e

    # Validate inputs
    if not french_term or not french_term.strip():
        return False, "French term cannot be empty"

    if not english_term or not english_term.strip():
        return False, "English term cannot be empty"

    # Clean terms
    french_term = french_term.strip()
    english_term = english_term.strip()
    notes = notes.strip()

    try:
        # Ensure file exists
        ensure_glossary_exists()

        # Check for duplicates if requested
        if check_duplicates:
            existing_glossary = fetch_glossary()

            if french_term in existing_glossary:
                existing_translation = existing_glossary[french_term]
                if existing_translation == english_term:
                    return False, f"Term pair already exists in glossary: {french_term} -> {english_term}"
                else:
                    return False, (
                        f"French term '{french_term}' already exists with different translation: "
                        f"'{existing_translation}'. Please update manually if you want to change it."
                    )

        # Prepare row data
        row_data = [[french_term, english_term, notes]]

        # Get Excel client
        client = get_client()

        # Append row to glossary file
        result = client.append_row(
            file_path=glossary_path,
            sheet_name=GLOSSARY_SHEET_NAME,
            values=row_data
        )

        # Upload updated file back to SharePoint (if configured)
        from tools.sharepoint_client import is_sharepoint_enabled, upload_glossary
        if is_sharepoint_enabled():
            print("Syncing glossary back to SharePoint...")
            upload_glossary(str(glossary_path))

        # Invalidate cache to force refresh
        invalidate_cache()

        print(f"[OK] Added to glossary: {french_term} -> {english_term}")
        return True, f"Successfully added: {french_term} -> {english_term}"

    except Exception as e:
        error_msg = f"Failed to add term to glossary: {e}"
        print(f"[ERROR] {error_msg}")
        return False, error_msg


def update(
    french_term: str,
    new_english_term: str,
    new_notes: str = ""
) -> Tuple[bool, str]:
    """
    Update an existing term in the glossary.

    Note: This searches for the term and updates the first match.
    For more precise updates, manual editing in Excel is recommended.

    Args:
        french_term: The French term to update
        new_english_term: The new English translation
        new_notes: Optional new notes

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        glossary_path = get_glossary_path()
    except ValueError as e:
        raise e

    try:
        # Ensure file exists
        ensure_glossary_exists()

        # Get Excel client
        client = get_client()

        # Read entire glossary
        values = client.read_sheet(glossary_path, GLOSSARY_SHEET_NAME)

        if not values:
            return False, "Glossary is empty"

        # Find the term (skip header row)
        found = False
        row_index = -1

        for i, row in enumerate(values):
            # Skip header row
            if i == 0 and len(row) > 0 and row[0].lower() in ['french term', 'terme français', 'french']:
                continue

            if len(row) > 0 and row[0].strip() == french_term:
                found = True
                row_index = i + 1  # +1 because Excel rows are 1-indexed
                break

        if not found:
            return False, f"Term '{french_term}' not found in glossary"

        # Update the row using batch update
        updates = [
            {'row': row_index, 'col': 2, 'value': new_english_term}  # Column B (English)
        ]

        if new_notes:
            updates.append({'row': row_index, 'col': 3, 'value': new_notes})  # Column C (Notes)

        client.batch_update(glossary_path, GLOSSARY_SHEET_NAME, updates)

        # Upload updated file back to SharePoint (if configured)
        from tools.sharepoint_client import is_sharepoint_enabled, upload_glossary
        if is_sharepoint_enabled():
            upload_glossary(str(glossary_path))

        # Invalidate cache
        invalidate_cache()

        print(f"[OK] Updated glossary: {french_term} -> {new_english_term}")
        return True, f"Successfully updated: {french_term} -> {new_english_term}"

    except Exception as e:
        error_msg = f"Failed to update term: {e}"
        print(f"[ERROR] {error_msg}")
        return False, error_msg


def remove(french_term: str) -> Tuple[bool, str]:
    """
    Remove a term from the glossary.

    Note: This function is intentionally limited.
    For term removal, manual editing in Excel is recommended
    to prevent accidental deletions.

    Args:
        french_term: The French term to remove

    Returns:
        Tuple of (success: bool, message: str)
    """
    return False, (
        "Term removal is not supported via the app for safety reasons. "
        "Please edit the Excel file directly to remove terms."
    )


if __name__ == "__main__":
    # Test the glossary updater
    print("Testing Glossary Updater...")
    print("-" * 50)

    # Test adding a new term
    test_french = "test_term"
    test_english = "test translation"
    test_notes = "This is a test entry"

    try:
        print(f"\nAdding test term: {test_french} -> {test_english}")
        success, message = add(test_french, test_english, test_notes)

        print(f"\nResult: {message}")

        if success:
            print("\n[OK] Test term added successfully")

            # Try adding the same term again (should fail with duplicate check)
            print("\nTrying to add the same term again...")
            success2, message2 = add(test_french, test_english)
            print(f"Result: {message2}")

            # Test updating the term
            print("\nUpdating test term...")
            success3, message3 = update(test_french, "updated translation", "Updated notes")
            print(f"Result: {message3}")

        else:
            print("\n[WARNING] Failed to add test term (may already exist)")

    except Exception as e:
        print(f"\n[ERROR] {e}")
