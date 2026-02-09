# PSP Translator Setup Guide

This workflow guides you through setting up the PSP Translator app from scratch.

## Objective

Get the PSP Translator running locally with all required integrations (Claude API, Google Sheets, web scraping).

## Prerequisites

- Python 3.10 or higher installed
- Chrome or Chromium browser (for web scraping)
- Internet connection
- Access to Google Cloud Console
- Anthropic account with API access

## Required Inputs

Before starting, gather:
1. Anthropic API key
2. Google Sheets ID for glossary
3. Google Cloud project credentials
4. PSP logo image (optional)

---

## Step 1: Clone/Download Project

If you haven't already, ensure you have the project files on your computer.

```bash
cd "c:\Users\raphd\Desktop\projet claude code\marketing psp traduction"
```

## Step 2: Install Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt
```

**Expected output**: All packages install successfully without errors.

**Troubleshooting**:
- If pip fails, try: `python -m pip install --upgrade pip`
- If specific packages fail, install them individually
- On Windows, pywin32 may require admin rights

## Step 3: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   copy .env.example .env
   ```

2. Open `.env` in a text editor

3. Add your Anthropic API key:
   - Get key from: https://console.anthropic.com/
   - Paste: `ANTHROPIC_API_KEY=sk-ant-your-key-here`

4. Add your Google Sheets ID:
   - Open your glossary sheet in browser
   - Copy the ID from URL: `https://docs.google.com/spreadsheets/d/{THIS_IS_THE_ID}/edit`
   - Paste in both fields:
     ```
     GOOGLE_SHEETS_GLOSSARY_ID=your_sheet_id
     GOOGLE_SHEETS_ACTION_LOG_ID=your_sheet_id
     ```

5. Save the file

**Verification**: Run `python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('API Key set:', bool(os.getenv('ANTHROPIC_API_KEY')))"`

## Step 4: Set Up Google Cloud Project

### 4.1 Create/Configure Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
   - Project name: "PSP Translator" (or your choice)
3. Note the project ID

### 4.2 Enable Google Sheets API

1. In Cloud Console, go to **APIs & Services** → **Library**
2. Search for "Google Sheets API"
3. Click **Enable**

### 4.3 Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. If prompted, configure the consent screen:
   - User Type: **External**
   - App name: "PSP Translator"
   - Add your email as test user
   - Save
4. Back to **Create OAuth client ID**:
   - Application type: **Desktop app**
   - Name: "PSP Translator Desktop"
   - Click **Create**
5. Download the JSON file
6. Rename it to `credentials.json`
7. Move it to project root directory

**Verification**: Check that `credentials.json` exists in your project folder.

## Step 5: Prepare Google Sheets

### 5.1 Set Up Glossary Sheet

Your "Traduction - Lexique Solange" sheet should have:

**Sheet structure:**
```
| Column A          | Column B        | Column C      |
|-------------------|-----------------|---------------|
| French Term       | English Term    | Notes/Context |
| kilomètre         | kilometre       | Canadian spelling |
| couleur           | colour          | Canadian spelling |
| ...               | ...             | ...           |
```

- **Row 1**: Can be headers or first entry (app handles both)
- **Column A**: French terms
- **Column B**: English translations
- **Column C**: Optional notes

### 5.2 Create Action Log Tab

1. In the same spreadsheet, add a new tab
2. Name it: **Action Log**
3. Set up columns:

```
| A: Timestamp        | B: French Term | C: English Term | D: Source | E: Added to Glossary |
|---------------------|----------------|-----------------|-----------|----------------------|
```

- Leave empty (app will populate)
- First row can be headers or empty

**Verification**: Your spreadsheet has two tabs: main sheet (glossary) + "Action Log"

## Step 6: Add PSP Logo (Optional)

1. Get PSP logo image (PNG format recommended)
2. Create assets directory if not exists: `mkdir assets`
3. Save logo as: `assets/psp_logo.png`

**Note**: If no logo provided, app displays 🇨🇦 emoji instead.

## Step 7: Test Google Sheets Connection

Run the Google Sheets client test:

```bash
python tools/google_sheets_client.py
```

**Expected behavior**:
1. Browser opens for Google OAuth
2. You authorize the app
3. Terminal shows: "✓ Authentication successful!"
4. A `token.json` file is created

**Troubleshooting**:
- "credentials.json not found": Move credentials.json to project root
- OAuth screen shows "App not verified": Click "Advanced" → "Go to PSP Translator (unsafe)" (it's safe, it's your app)
- Connection fails: Check Google Sheets API is enabled

## Step 8: Test Glossary Fetcher

```bash
python tools/fetch_glossary.py
```

**Expected output**:
```
Fetching glossary from Google Sheets...
✓ Fetched X terms from Google Sheets
✓ Saved glossary to cache

Glossary loaded successfully!
Total terms: X
Sample terms: ...
```

**Troubleshooting**:
- "GOOGLE_SHEETS_GLOSSARY_ID not set": Check .env file
- "No data found": Check sheet structure (columns A, B, C)
- Authentication error: Re-run step 7

## Step 9: Test Translation Engine

Test with sample text:

```bash
python tools/translate_text.py
```

**Expected output**:
```
Testing Translation Engine...
Estimated cost: $0.XXXX
Fetching glossary...
Translating with claude-3-5-sonnet-...
✓ Translation complete
...
```

**Troubleshooting**:
- "ANTHROPIC_API_KEY not set": Check .env file
- API error: Verify API key is valid and has credits
- Rate limit: Wait a moment and try again

## Step 10: Run Streamlit App

Launch the app:

```bash
streamlit run app.py
```

**Expected behavior**:
1. Terminal shows: "You can now view your Streamlit app in your browser"
2. Browser opens to: http://localhost:8501
3. App displays with PSP Translator header
4. Glossary loads (check info banner)

**Verification checklist**:
- [ ] App loads without errors
- [ ] Glossary info shows "X terms loaded"
- [ ] Left panel: French text area visible
- [ ] Right panel: English translation area visible
- [ ] Term checker section at bottom
- [ ] Sidebar shows stats and links

## Step 11: Test Translation Flow

1. Paste sample French text in left panel:
   ```
   **Bienvenue** au Programme de soutien du personnel.

   Le PSP offre des services à nos membres pour 100$.
   ```

2. Click **Translate** button

3. Verify English translation appears in right panel

4. Check that:
   - Bold formatting preserved (**Welcome**)
   - Dollar sign before number ($100)
   - Times New Roman 12pt styling applied

## Step 12: Test Term Checker

1. Type a term in "Term Checker": `couleur`
2. Click **TERMIUM Plus** button
3. Wait for results to load
4. Verify results appear in expandable cards
5. Click **Add to Glossary** on a result
6. Check Google Sheets for new entry

**Note**: Web scrapers may fail if website structure changed. Manual search links provided as fallback.

## Step 13: Verify Action Logging

1. Check your Google Sheets "Action Log" tab
2. Should see entry for the term lookup above
3. Columns should be populated:
   - Timestamp
   - French term
   - English term
   - Source (TERMIUM)
   - Added to Glossary (YES)

---

## Success Criteria

✅ All dependencies installed
✅ Environment variables configured
✅ Google OAuth authenticated
✅ Glossary loads successfully
✅ Translation works with Claude API
✅ Streamlit app runs locally
✅ Term checker returns results
✅ Action logging works
✅ Glossary updates work

## Next Steps

### For Local Use
- Start translating documents
- Build up your glossary over time
- Review action logs weekly for frequently checked terms

### For Web Deployment
- See [README.md](../README.md) section "Deploying to Streamlit Cloud"
- Push code to GitHub
- Deploy via Streamlit Cloud
- Configure secrets in cloud environment

---

## Troubleshooting Common Issues

### App won't start
- Check all dependencies installed: `pip list`
- Verify Python version: `python --version` (should be 3.10+)
- Look for error messages in terminal

### Glossary not loading
- Verify Sheet ID in .env
- Check sheet name matches (default: "Sheet1")
- Re-authenticate: delete token.json and restart

### Translation fails
- Check API key valid
- Verify account has credits
- Check for rate limiting (wait and retry)

### Term checker returns no results
- Scrapers may need updates if websites changed
- Use manual search links provided
- Check selectors in scrape_termium.py / scrape_oqlf.py

### Chrome driver errors
- Install ChromeDriver: `pip install webdriver-manager`
- Ensure Chrome/Chromium installed
- Try headless mode (already configured)

---

## Getting Help

- Review error messages carefully
- Check [README.md](../README.md) for additional documentation
- Review [implementation plan](C:\Users\raphd\.claude\plans\flickering-strolling-key.md)
- Test individual tools using their `if __name__ == "__main__"` blocks

## Maintenance

### Regular Tasks
- **Weekly**: Review action logs for frequently checked terms
- **Monthly**: Test web scrapers (websites may change)
- **As needed**: Update glossary with new approved terms
- **Quarterly**: Rotate API keys for security

### Updating the App
- Pull latest code from repository
- Run: `pip install -r requirements.txt --upgrade`
- Test locally before deploying changes
- Update workflows if processes change

---

## Appendix: File Checklist

Ensure these files exist:

```
✓ app.py
✓ requirements.txt
✓ .env (not .env.example)
✓ credentials.json
✓ config/translation_rules.md
✓ config/prompt_template.txt
✓ tools/google_sheets_client.py
✓ tools/fetch_glossary.py
✓ tools/translate_text.py
✓ tools/scrape_termium.py
✓ tools/scrape_oqlf.py
✓ tools/log_action.py
✓ tools/add_to_glossary.py
```

Generated on first run:
- `token.json` (after OAuth)
- `.tmp/cached_glossary.json` (after first glossary fetch)
