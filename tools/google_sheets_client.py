"""
Google Sheets Client

Handles authentication and CRUD operations for Google Sheets.
Used for glossary retrieval, action logging, and glossary updates.
"""

import os
import pickle
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete token.json
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class GoogleSheetsClient:
    """
    Google Sheets API client with authentication and basic operations.
    """

    def __init__(self):
        """Initialize the Google Sheets client with authentication."""
        self.creds = None
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """
        Authenticate with Google Sheets API using OAuth 2.0.

        Uses credentials.json for OAuth flow and stores token in token.json.
        Token is automatically refreshed when expired.
        """
        project_root = Path(__file__).parent.parent
        token_path = project_root / 'token.json'
        credentials_path = project_root / 'credentials.json'

        # Load existing token if available
        if token_path.exists():
            self.creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        # If no valid credentials, authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                # Refresh expired token
                self.creds.refresh(Request())
            else:
                # Run OAuth flow
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"credentials.json not found at {credentials_path}. "
                        "Please download it from Google Cloud Console."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            # Save the credentials for next run
            with open(token_path, 'w') as token:
                token.write(self.creds.to_json())

        # Build the service
        self.service = build('sheets', 'v4', credentials=self.creds)

    def read_sheet(self, sheet_id: str, range_name: str) -> List[List[str]]:
        """
        Read data from a Google Sheet.

        Args:
            sheet_id: The ID of the spreadsheet
            range_name: The A1 notation of the range to retrieve (e.g., 'Sheet1!A1:C100')

        Returns:
            List of rows, where each row is a list of cell values

        Raises:
            HttpError: If the API request fails
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])
            return values

        except HttpError as error:
            print(f"Error reading sheet: {error}")
            raise

    def append_row(self, sheet_id: str, range_name: str, values: List[List[str]]) -> dict:
        """
        Append rows to a Google Sheet.

        Args:
            sheet_id: The ID of the spreadsheet
            range_name: The A1 notation of the range to append to (e.g., 'Sheet1!A:E')
            values: List of rows to append, where each row is a list of cell values

        Returns:
            Dictionary containing the API response with update details

        Raises:
            HttpError: If the API request fails
        """
        try:
            body = {
                'values': values
            }

            result = self.service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            return result

        except HttpError as error:
            print(f"Error appending row: {error}")
            raise

    def update_cell(self, sheet_id: str, range_name: str, value: str) -> dict:
        """
        Update a specific cell in a Google Sheet.

        Args:
            sheet_id: The ID of the spreadsheet
            range_name: The A1 notation of the cell to update (e.g., 'Sheet1!A1')
            value: The new value for the cell

        Returns:
            Dictionary containing the API response with update details

        Raises:
            HttpError: If the API request fails
        """
        try:
            body = {
                'values': [[value]]
            }

            result = self.service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            return result

        except HttpError as error:
            print(f"Error updating cell: {error}")
            raise

    def batch_update(self, sheet_id: str, updates: List[dict]) -> dict:
        """
        Perform multiple update operations in a single API call.

        Args:
            sheet_id: The ID of the spreadsheet
            updates: List of update dictionaries, each containing 'range' and 'values'

        Returns:
            Dictionary containing the API response with update details

        Raises:
            HttpError: If the API request fails
        """
        try:
            data = []
            for update in updates:
                data.append({
                    'range': update['range'],
                    'values': update['values']
                })

            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': data
            }

            result = self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body=body
            ).execute()

            return result

        except HttpError as error:
            print(f"Error in batch update: {error}")
            raise


# Singleton instance for reuse across the application
_client_instance = None


def get_client() -> GoogleSheetsClient:
    """
    Get or create a singleton instance of the Google Sheets client.

    Returns:
        GoogleSheetsClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = GoogleSheetsClient()
    return _client_instance


if __name__ == "__main__":
    # Test the client
    print("Testing Google Sheets Client...")
    try:
        client = get_client()
        print("[OK] Authentication successful!")
        print("[OK] Google Sheets client ready to use")
    except Exception as e:
        print(f"[ERROR] Authentication failed: {e}")
