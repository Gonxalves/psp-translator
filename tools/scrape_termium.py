"""
TERMIUM Plus Web Scraper

Scrapes terminology from TERMIUM Plus (Government of Canada terminology database).
Uses Selenium for JavaScript rendering.
"""

import os
import time
import re
from typing import List, Dict, Optional
from urllib.parse import quote_plus, unquote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def scrape(search_term: str, language_pair: str = "fr-en") -> List[Dict[str, str]]:
    """
    Scrape TERMIUM Plus for French-to-English term translations.

    Args:
        search_term: The term to search for
        language_pair: Language pair (default: "fr-en" for French to English)

    Returns:
        List of dictionaries containing:
        - english_term: The English translation variant
        - description: Definition or context
        - domain: Subject domain(s)
        - source_url: URL to the results page

    Raises:
        Exception: If scraping fails
    """
    print(f"Searching TERMIUM Plus for: '{search_term}'")

    # Configure Chrome options for headless browsing
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ["CHROME_BIN"]

    driver = None
    try:
        # Initialize Chrome driver
        driver = webdriver.Chrome(options=chrome_options)

        # Construct TERMIUM Plus search URL (French interface)
        encoded_term = quote_plus(search_term)
        url = f"https://www.btb.termiumplus.gc.ca/tpv2alpha/alpha-fra.html?lang=fra&i=1&srchtxt={encoded_term}&index=alt&codom2nd_wet=1#resultrecs"

        print(f"Loading: {url}")
        driver.get(url)

        # Wait for page to load - try multiple possible indicators
        try:
            # Wait for body content to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Additional wait for dynamic content to render
            time.sleep(3)
        except TimeoutException:
            print("Warning: Timeout waiting for page load.")
            time.sleep(2)

        # Parse results
        results = _parse_results(driver)

        if not results:
            print(f"No results found for '{search_term}'")
            return []

        print(f"[OK] Found {len(results)} result(s)")
        return results

    except Exception as e:
        print(f"[ERROR] Error scraping TERMIUM Plus: {e}")
        # Return manual link as fallback
        return [{
            'english_term': f"[Recherche manuelle]",
            'description': f"Impossible d'extraire les résultats. Veuillez rechercher manuellement sur TERMIUM Plus.",
            'domain': "",
            'source_url': f"https://www.btb.termiumplus.gc.ca/tpv2alpha/alpha-fra.html?lang=fra&i=1&srchtxt={quote_plus(search_term)}"
        }]

    finally:
        if driver:
            driver.quit()


def _parse_results(driver) -> List[Dict[str, str]]:
    """
    Parse search results from TERMIUM Plus page using BeautifulSoup.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        List of all English term variants with english_term, description, domain, source_url
    """
    results = []

    try:
        # Get page source and parse with BeautifulSoup
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # TERMIUM organizes results in <section class="panel panel-info recordSet">
        record_sections = soup.find_all('section', class_='recordSet')

        if not record_sections:
            # Fallback to any element with recordSet class
            record_sections = soup.find_all(class_='recordSet')

        for i, section in enumerate(record_sections[:10]):
            try:
                # _extract_termium_record now returns a LIST of variants
                variants = _extract_termium_record(section, driver.current_url)
                for variant in variants:
                    if variant and variant.get('english_term'):
                        results.append(variant)
            except Exception as e:
                print(f"Warning: Failed to parse record {i+1}: {e}")
                continue

    except Exception as e:
        print(f"Warning: Failed to parse results: {e}")

    return results


def _extract_termium_record(section, source_url: str) -> List[Dict[str, str]]:
    """
    Extract ALL English term variants from a TERMIUM record section.

    The HTML structure has:
    - English terms in <span lang="en">...</span>
    - Definitions after <abbr title="Definition">DEF</abbr>
    - Domains in sections with "Domaine(s)" headers

    Returns:
        List of dictionaries, one per English term variant found
    """
    variants = []
    description = ""
    domain = ""

    # Find ALL English terms - look for span with lang="en"
    en_terms = section.find_all('span', attrs={'lang': 'en'})

    # Find definition - look for DEF abbreviation and get following paragraph
    def_abbrs = section.find_all('abbr', string='DEF')
    if not def_abbrs:
        # Try finding by title attribute
        def_abbrs = section.find_all('abbr', attrs={'title': re.compile(r'finition', re.I)})

    if def_abbrs:
        for abbr in def_abbrs:
            # The definition text is usually in the same h5 parent or following p
            parent_h5 = abbr.find_parent('h5')
            if parent_h5:
                # Get the next sibling which should be the definition paragraph
                next_elem = parent_h5.find_next_sibling()
                if next_elem and next_elem.name == 'p':
                    # Use separator to ensure proper spacing between nested elements
                    raw_text = next_elem.get_text(separator=' ', strip=True)
                    def_text = ' '.join(raw_text.split())  # Normalize whitespace
                    # Clean up: remove trailing fiche references
                    def_text = _clean_description(def_text)
                    if def_text and len(def_text) > 10:
                        description = def_text[:500]
                        break

    # If no DEF found, try OBS (Observation) abbreviation
    if not description:
        obs_abbrs = section.find_all('abbr', string='OBS')
        if not obs_abbrs:
            obs_abbrs = section.find_all('abbr', attrs={'title': re.compile(r'observation', re.I)})

        for abbr in obs_abbrs:
            parent_h5 = abbr.find_parent('h5')
            if parent_h5:
                next_elem = parent_h5.find_next_sibling()
                if next_elem and next_elem.name == 'p':
                    # Use separator to ensure proper spacing
                    raw_text = next_elem.get_text(separator=' ', strip=True)
                    obs_text = ' '.join(raw_text.split())  # Normalize whitespace
                    obs_text = _clean_description(obs_text)
                    if obs_text and len(obs_text) > 10:
                        description = obs_text[:500]
                        break

    # If still no description, look for any meaningful paragraph in the section
    if not description:
        paragraphs = section.find_all('p')
        for p in paragraphs:
            # Use separator to ensure proper spacing
            raw_text = p.get_text(separator=' ', strip=True)
            text = ' '.join(raw_text.split())  # Normalize whitespace
            # Skip short texts - be less restrictive (don't skip 'fiche' entirely)
            if len(text) > 30 and not any(skip in text.lower() for skip in ['conserver', 'record number']):
                text = _clean_description(text)
                if text and len(text) > 10:
                    description = text[:500]
                    break

    # Find domain - look for h5 containing "Domaine" or "Subject" (remove class filter)
    domain_headers = section.find_all('h5')
    for h5 in domain_headers:
        h5_text = h5.get_text(strip=True)
        if 'Domaine' in h5_text or 'Subject' in h5_text:
            # Domain list is in the next ul (not necessarily a sibling)
            domain_list = h5.find_next('ul')
            if domain_list:
                domains = [li.get_text(strip=True) for li in domain_list.find_all('li')]
                domain = ', '.join(domains[:3])  # Limit to 3 domains
                break

    # Create a variant entry for EACH English term found
    seen_terms = set()  # Avoid duplicates
    for en_term_elem in en_terms:
        raw_term = en_term_elem.get_text(strip=True)
        # Decode URL-encoded characters (e.g., %20 -> space)
        english_term = unquote(raw_term)

        # Skip empty terms or duplicates
        if not english_term or english_term.lower() in seen_terms:
            continue
        seen_terms.add(english_term.lower())

        variants.append({
            'english_term': english_term,
            'description': description or "Voir TERMIUM Plus pour la definition complete",
            'domain': domain,
            'source_url': source_url
        })

    return variants


def _clean_description(text: str) -> str:
    """Remove trailing fiche metadata from description text."""
    # Remove patterns like "2, fiche 2, Français, -couleur" or "1, fiche 10, Anglais, - colour" at the end
    # Handle various spacing patterns around the hyphen and term
    cleaned = re.sub(r'\s*\d+,\s*fiche\s*\d+,\s*(?:Fran.ais|Anglais|Espagnol|Portugais),?\s*-?\s*\S*\s*$', '', text, flags=re.IGNORECASE)
    # Also remove any "Record number:" prefixes that might appear
    cleaned = re.sub(r'^Record number:\s*\d+,\s*Textual support number:\s*\d+\s*', '', cleaned)
    # Remove trailing punctuation that may be left over
    cleaned = re.sub(r'\s*[,;]\s*$', '', cleaned)
    return cleaned.strip()


def get_manual_search_url(search_term: str) -> str:
    """
    Get the manual search URL for TERMIUM Plus (French interface).

    Args:
        search_term: The term to search for

    Returns:
        URL string for manual search
    """
    encoded_term = quote_plus(search_term)
    return f"https://www.btb.termiumplus.gc.ca/tpv2alpha/alpha-fra.html?lang=fra&i=1&srchtxt={encoded_term}"


def debug_fetch_html(search_term: str) -> str:
    """Fetch and return the raw HTML for debugging purposes."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ["CHROME_BIN"]

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        encoded_term = quote_plus(search_term)
        url = f"https://www.btb.termiumplus.gc.ca/tpv2alpha/alpha-fra.html?lang=fra&i=1&srchtxt={encoded_term}&index=alt&codom2nd_wet=1#resultrecs"
        driver.get(url)
        time.sleep(3)
        return driver.page_source
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    import sys

    # Check for debug mode
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        term = sys.argv[2] if len(sys.argv) > 2 else "marketing"
        print(f"Fetching HTML for: {term}")
        html = debug_fetch_html(term)
        # Save to file for analysis
        with open(".tmp/termium_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML saved to .tmp/termium_debug.html ({len(html)} chars)")
        sys.exit(0)

    # Test the scraper
    print("Testing TERMIUM Plus Scraper...")
    print("-" * 50)

    test_terms = ["couleur", "rigueur"]

    for term in test_terms:
        print(f"\nSearching for: {term}")
        print("=" * 50)

        try:
            results = scrape(term)

            if results:
                print(f"\nFound {len(results)} English variant(s):")
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. {result['english_term']}")
                    print(f"   Description: {result['description'][:100]}...")
                    if result['domain']:
                        print(f"   Domain: {result['domain']}")
                    print(f"   URL: {result['source_url']}")
            else:
                print("No results found")

            # Show manual search URL
            print(f"\nManual search URL: {get_manual_search_url(term)}")

        except Exception as e:
            print(f"Error: {e}")

        print()
