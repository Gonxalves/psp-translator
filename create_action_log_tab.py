"""
Create Action Log Tab in Google Sheets

This script automatically creates the Action Log tab with proper headers and formatting.
"""

import os
from dotenv import load_dotenv
from tools.google_sheets_client import get_client

# Load environment variables
load_dotenv()


def create_action_log_tab():
    """Create the Action Log tab with headers and formatting."""

    sheet_id = os.getenv('GOOGLE_SHEETS_ACTION_LOG_ID')
    if not sheet_id:
        print("✗ GOOGLE_SHEETS_ACTION_LOG_ID not set in .env file")
        return False

    print("Creating Action Log tab in Google Sheets...")
    print("-" * 60)
    print(f"Sheet ID: {sheet_id}")
    print()

    try:
        # Get the client
        client = get_client()
        print("[OK] Authenticated with Google Sheets")

        # First, check if the Action Log tab already exists
        try:
            existing = client.read_sheet(sheet_id, 'Action Log!A1:A1')
            print("! Action Log tab already exists")
            print("  Checking if headers need to be added...")

            # Check if headers exist
            headers = client.read_sheet(sheet_id, 'Action Log!A1:E1')
            if headers and len(headers) > 0:
                print("  Headers already exist:")
                print(f"  {headers[0]}")
                print("\n[OK] Action Log tab is already set up!")
                return True
            else:
                print("  No headers found, adding them now...")

        except Exception as e:
            # Tab doesn't exist, we need to create it
            error_msg = str(e)
            if "Unable to parse range" in error_msg or "not found" in error_msg.lower():
                print("Creating new Action Log tab...")

                # Create the new sheet using batchUpdate
                request_body = {
                    'requests': [
                        {
                            'addSheet': {
                                'properties': {
                                    'title': 'Action Log',
                                    'gridProperties': {
                                        'rowCount': 1000,
                                        'columnCount': 5,
                                        'frozenRowCount': 1
                                    }
                                }
                            }
                        }
                    ]
                }

                result = client.service.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body=request_body
                ).execute()

                print("[OK] Action Log tab created")
            else:
                raise e

        # Add headers
        print("\nAdding headers to Action Log...")
        headers = [['Timestamp', 'French Term', 'English Term', 'Source', 'Added to Glossary']]

        client.service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range='Action Log!A1:E1',
            valueInputOption='USER_ENTERED',
            body={'values': headers}
        ).execute()

        print("[OK] Headers added")

        # Format the headers (bold, background color)
        print("\nFormatting headers...")

        # Get the sheet ID for the Action Log tab
        sheet_metadata = client.service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        action_log_sheet_id = None

        for sheet in sheet_metadata.get('sheets', []):
            if sheet['properties']['title'] == 'Action Log':
                action_log_sheet_id = sheet['properties']['sheetId']
                break

        if action_log_sheet_id is not None:
            format_request = {
                'requests': [
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': action_log_sheet_id,
                                'startRowIndex': 0,
                                'endRowIndex': 1,
                                'startColumnIndex': 0,
                                'endColumnIndex': 5
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {
                                        'red': 0.9,
                                        'green': 0.9,
                                        'blue': 0.9
                                    },
                                    'textFormat': {
                                        'bold': True,
                                        'fontSize': 10
                                    }
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                        }
                    },
                    {
                        'updateSheetProperties': {
                            'properties': {
                                'sheetId': action_log_sheet_id,
                                'gridProperties': {
                                    'frozenRowCount': 1
                                }
                            },
                            'fields': 'gridProperties.frozenRowCount'
                        }
                    }
                ]
            }

            client.service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body=format_request
            ).execute()

            print("[OK] Headers formatted (bold, gray background, frozen)")

        print("\n" + "=" * 60)
        print("[SUCCESS] ACTION LOG TAB CREATED!")
        print("=" * 60)
        print(f"\nView your Action Log:")
        print(f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
        print("\nThe tab is ready to log all your translation activities.")

        return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_action_log_tab()

    if success:
        print("\nNext step: Run 'python setup_action_log.py' to verify and test the setup.")
    else:
        print("\nSetup failed. Please check the error messages above.")
