"""Quick script to check sheet names in the glossary spreadsheet"""
import os
from dotenv import load_dotenv
from tools.google_sheets_client import get_client

load_dotenv()

sheet_id = os.getenv('GOOGLE_SHEETS_GLOSSARY_ID')
client = get_client()

# Get spreadsheet metadata
spreadsheet = client.service.spreadsheets().get(spreadsheetId=sheet_id).execute()

print("Available sheets in your spreadsheet:")
print("-" * 60)
for sheet in spreadsheet.get('sheets', []):
    properties = sheet['properties']
    print(f"- {properties['title']} (ID: {properties['sheetId']})")
