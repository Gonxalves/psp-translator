# PSP Translator - French to English Translation App

A web-based translation application specifically designed for Personnel Support Programs (PSP) documentation. The app uses Claude AI with custom translation rules, Google Sheets glossary integration, and terminology checking via TERMIUM Plus and OQLF.

## Features

- ✅ **Claude AI Translation**: High-quality French-to-English translation following PSP-specific rules
- 📚 **Google Sheets Glossary**: Dynamic glossary that grows over time
- 🔍 **Terminology Checker**: Look up terms in TERMIUM Plus and OQLF databases
- 📝 **Rule Enforcement**: 11 specific translation rules for formatting, capitalization, and special terms
- 📊 **Action Logging**: Track term-checking activities for analysis
- 🎨 **Formatting Preservation**: Maintains bold, italics, spacing, and Times New Roman 12pt output

## Architecture (WAT Framework)

This project uses the **WAT framework** (Workflows, Agents, Tools):

1. **Workflows** (`workflows/`) - Markdown SOPs defining translation processes
2. **Agents** (Streamlit app) - UI that coordinates between user and tools
3. **Tools** (`tools/`) - Python scripts for API calls, scraping, and Google Sheets integration

## Directory Structure

```
app.py                      # Main Streamlit application
config/
  ├── translation_rules.md  # 11 PSP translation rules
  └── prompt_template.txt   # Claude API prompt template
tools/
  ├── google_sheets_client.py  # Google Sheets authentication
  ├── fetch_glossary.py       # Glossary fetcher with caching
  ├── translate_text.py       # Claude translation engine
  ├── scrape_termium.py       # TERMIUM Plus scraper
  ├── scrape_oqlf.py          # OQLF scraper
  ├── log_action.py           # Action logger
  └── add_to_glossary.py      # Glossary updater
workflows/                  # Workflow documentation
.tmp/                       # Cached data (gitignored)
.env                        # API keys (gitignored)
assets/                     # PSP logo and images
```

## Prerequisites

- Python 3.10 or higher
- Anthropic API key (for Claude)
- Google Cloud project with Sheets API enabled
- Google OAuth credentials (credentials.json)
- Chrome/Chromium (for web scraping)

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in the required values:

```bash
# Anthropic Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Google Sheets
GOOGLE_SHEETS_GLOSSARY_ID=your_spreadsheet_id_here
GOOGLE_SHEETS_ACTION_LOG_ID=your_spreadsheet_id_here

# Optional settings
MAX_TRANSLATION_LENGTH=50000
CACHE_TTL_MINUTES=5
```

### 3. Set Up Google Sheets

#### a. Create/Configure Glossary Sheet

Your Google Sheet "Traduction - Lexique Solange" should have this structure:

| Column A: French Term | Column B: English Term | Column C: Notes/Context |
|-----------------------|------------------------|-------------------------|
| kilomètre | kilometre | Canadian spelling |
| couleur | colour | Canadian spelling |
| ... | ... | ... |

#### b. Create Action Log Tab

Add an "Action Log" tab with this structure:

| Column A: Timestamp | Column B: French Term | Column C: English Term | Column D: Source | Column E: Added to Glossary |
|---------------------|----------------------|------------------------|------------------|----------------------------|
| 2026-02-02 10:30:15 | couleur | colour | TERMIUM | YES |
| ... | ... | ... | ... | ... |

### 4. Set Up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Google Sheets API**
4. Go to **Credentials** → Create Credentials → **OAuth 2.0 Client ID**
5. Choose **Desktop app** as application type
6. Download the credentials file and save as `credentials.json` in project root

On first run, the app will open a browser for OAuth authorization. After authorization, a `token.json` file will be created automatically.

### 5. Add PSP Logo (Optional)

Place your PSP logo as `assets/psp_logo.png`. If not provided, the app will display a Canadian flag emoji instead.

## Running the App Locally

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Deploying to Streamlit Cloud

### Prerequisites

- GitHub repository with your code
- Streamlit Cloud account (free at [streamlit.io/cloud](https://streamlit.io/cloud))

### Steps

1. Push your code to GitHub (ensure `.env` and `credentials.json` are gitignored)

2. Go to [Streamlit Cloud](https://streamlit.io/cloud) and click "New app"

3. Select your repository and branch

4. Set main file as `app.py`

5. Configure secrets in **Settings** → **Secrets**:

```toml
ANTHROPIC_API_KEY = "your_key_here"
GOOGLE_SHEETS_GLOSSARY_ID = "your_sheet_id"
GOOGLE_SHEETS_ACTION_LOG_ID = "your_sheet_id"

# Paste your entire credentials.json content here as TOML
[google_sheets_credentials]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@project.iam.gserviceaccount.com"
# ... rest of credentials.json fields
```

6. Deploy and test your live app

## Usage Guide

### Translating Text

1. Paste or type French text in the left panel
2. Click **Translate** button
3. English translation appears in the right panel (Times New Roman 12pt)
4. Glossary terms are automatically applied
5. Translation follows all 11 PSP-specific rules

### Checking Terminology

1. Type or paste a term in the "Term Checker" input
2. Click **TERMIUM Plus** or **OQLF** to search
3. Browse results in expandable cards
4. Click **Use this translation** to replace in your text
5. Click **Add to Glossary** to save the term for future use

### Managing Glossary

- Glossary loads automatically from Google Sheets
- Click **Refresh Glossary** to reload after updates
- New terms added via app are automatically synced
- Action Log tracks all term lookups for analysis

## Translation Rules

The app enforces these 11 rules:

1. Use glossary terms first (preserve original capitalization)
2. Preserve bold and italics
3. Format in Times New Roman 12pt with exact spacing
4. Titles/subheadings: capitalize only first word (unless proper nouns)
5. No italics for quotations
6. No space before colons
7. Dollar sign before numbers ($100)
8. Don't translate: "bouton rouge", "Encadré", regiment names, .jpg filenames
9. Preserve hyphens in city names
10. Canadian spellings: kilometre, colour, rigour, tuque
11. Maintain technical accuracy for PSP/military terminology

See [config/translation_rules.md](config/translation_rules.md) for complete details.

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
- Ensure `.env` file exists with your API key
- Restart the Streamlit app

### "GOOGLE_SHEETS_GLOSSARY_ID not set"
- Add your Google Sheets ID to `.env`
- Get the ID from your sheet URL: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`

### OAuth authentication fails
- Delete `token.json` and try again
- Ensure `credentials.json` is in the project root
- Check that Google Sheets API is enabled in your Cloud project

### Web scrapers return no results
- TERMIUM Plus and OQLF scrapers may need updates if websites change structure
- Use manual search links provided as fallback
- Check selectors in `tools/scrape_termium.py` and `tools/scrape_oqlf.py`

### Chrome driver issues
- Install ChromeDriver: `pip install webdriver-manager`
- Ensure Chrome/Chromium is installed on your system

## Cost Estimation

**Claude API (Sonnet 3.5)**:
- ~$0.03 per typical translation (1000 words)
- 1000 translations/month ≈ $30

**Google Sheets API**: Free (within quota limits)

**Streamlit Cloud**: Free tier available

## Support & Documentation

- [Implementation Plan](C:\Users\raphd\.claude\plans\flickering-strolling-key.md)
- [Translation Rules](config/translation_rules.md)
- [WAT Framework Instructions](CLAUDE.md)
- [Anthropic API Docs](https://docs.anthropic.com/)
- [TERMIUM Plus](https://www.btb.termiumplus.gc.ca/)
- [OQLF Vitrine](https://vitrinelinguistique.oqlf.gouv.qc.ca/)

## Contributing

This project follows the WAT framework principles:
- Tools should be deterministic and testable
- Workflows should be documented in markdown
- The agent (app) coordinates between UI and tools
- Keep improving through the self-improvement loop

## License

Internal use for Personnel Support Programs (PSP) translation.
