"""
PSP Translator Tools Package

This package contains deterministic execution scripts for the PSP Translator app.
Following the WAT framework, these tools handle:
- Google Sheets integration (glossary, logging)
- Claude API translation
- Web scraping (TERMIUM Plus, OQLF)
- Word document parsing and export
- Caching and data management
"""

__version__ = "1.0.0"

from tools import export_word
