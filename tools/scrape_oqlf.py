"""
OQLF Web Scraper

Scrapes terminology from Office québécois de la langue française (OQLF)
Vitrine linguistique / Grand dictionnaire terminologique (GDT).
Uses Selenium for JavaScript rendering.
"""

import os
import time
import re
from typing import List, Dict, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def scrape(search_term: str) -> List[Dict[str, str]]:
    """
    Scrape OQLF Vitrine Linguistique / GDT for terminology.

    Args:
        search_term: The term to search for

    Returns:
        List of dictionaries containing:
        - english_term: The English translation variant
        - description: Definition or explanation
        - domain: Subject domain (if available)
        - source_url: URL to the fiche page
    """
    print(f"Searching OQLF for: '{search_term}'")

    # Configure Chrome options for headless browsing
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

        # Search URL for GDT only (using the tx_solr query parameter)
        encoded_term = quote_plus(search_term)
        # Use tx_solr[q] for search query and filter for GDT only
        search_url = f"https://vitrinelinguistique.oqlf.gouv.qc.ca/resultats-de-recherche?tx_solr%5Bq%5D={encoded_term}&tx_solr%5Bfilter%5D%5B0%5D=type_stringM%3Agdt"

        print(f"Loading: {search_url}")
        driver.get(search_url)

        # Wait for page to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Additional wait for dynamic content
        except TimeoutException:
            print("Warning: Timeout waiting for page load.")
            time.sleep(2)

        # Find GDT fiche links in search results
        results = _find_and_parse_gdt_results(driver, search_term)

        if not results:
            print(f"No GDT results found for '{search_term}'")
            return [{
                'english_term': "[Recherche manuelle]",
                'description': "Aucun resultat trouve. Veuillez rechercher manuellement sur la Vitrine linguistique.",
                'domain': "",
                'source_url': search_url
            }]

        print(f"[OK] Found {len(results)} result(s)")
        return results

    except Exception as e:
        print(f"[ERROR] Error scraping OQLF: {e}")
        return [{
            'english_term': "[Recherche manuelle]",
            'description': f"Impossible d'extraire les resultats. Veuillez rechercher manuellement.",
            'domain': "",
            'source_url': get_manual_search_url(search_term)
        }]

    finally:
        if driver:
            driver.quit()


def _find_and_parse_gdt_results(driver, search_term: str) -> List[Dict[str, str]]:
    """
    Find GDT results in search results page and extract data.

    The search results have articles with:
    - data-title="French term FR • English term EN"
    - data-url="/fiche-gdt/fiche/{id}/{slug}"
    - Description text in the article body
    """
    results = []

    try:
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Find all result articles with GDT fiches
        articles = soup.find_all('article', class_='result')

        gdt_articles = []
        for article in articles:
            url = article.get('data-url', '')
            if '/fiche-gdt/fiche/' in url:
                gdt_articles.append(article)

        print(f"Found {len(gdt_articles)} GDT result(s)")

        # Extract data from each article (limit to first 10)
        for article in gdt_articles[:10]:
            try:
                result = _extract_from_search_result(article)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"Warning: Failed to parse article: {e}")
                continue

    except Exception as e:
        print(f"Warning: Failed to find GDT results: {e}")

    return results


def _extract_from_search_result(article) -> Optional[Dict[str, str]]:
    """
    Extract terminology data directly from a search result article.

    The data-title attribute contains: "French term FR • English term EN"
    """
    english_term = ""
    description = ""
    domain = ""

    # Get the data-title which contains "French FR • English EN"
    data_title = article.get('data-title', '')
    if data_title and ' • ' in data_title:
        # Split by the bullet separator
        parts = data_title.split(' • ')
        if len(parts) >= 2:
            # English part is usually "term EN"
            en_part = parts[1].strip()
            # Remove the " EN" suffix
            if en_part.endswith(' EN'):
                english_term = en_part[:-3].strip()
            else:
                english_term = en_part

    # Get the URL
    url = article.get('data-url', '')
    if url and url.startswith('/'):
        full_url = f"https://vitrinelinguistique.oqlf.gouv.qc.ca{url}"
    else:
        full_url = url

    # Try to extract domain from breadcrumb or category info
    domain_elem = article.find(['span', 'a'], class_=re.compile(r'domain|category|breadcrumb|tag', re.I))
    if domain_elem:
        domain = domain_elem.get_text(strip=True)

    # Also look for domain in any element containing "Domaine"
    if not domain:
        for elem in article.find_all(['span', 'div', 'p']):
            text = elem.get_text(strip=True)
            if 'Domaine' in text or 'domaine' in text:
                # Extract the domain value after the label
                domain_match = re.search(r'[Dd]omaine\s*[:\s]\s*(.+?)(?:\.|$)', text)
                if domain_match:
                    domain = domain_match.group(1).strip()[:100]
                    break

    # Try to get definition from the article text
    # Look for paragraph or description elements
    desc_elem = article.find(['p', 'div'], class_=re.compile(r'result.*desc|snippet|excerpt', re.I))
    if desc_elem:
        # Use separator=' ' to ensure spaces between nested elements
        raw_text = desc_elem.get_text(separator=' ', strip=True)
        # Normalize whitespace (collapse multiple spaces into one)
        description = ' '.join(raw_text.split())

    # If no description found, try to get any text content
    if not description:
        # Get all text from the article, excluding the title
        text_parts = []
        for elem in article.find_all(['p', 'span', 'div']):
            # Use separator=' ' to ensure spaces between nested elements
            raw_text = elem.get_text(separator=' ', strip=True)
            text = ' '.join(raw_text.split())  # Normalize whitespace
            if text and text != data_title and len(text) > 20:
                text_parts.append(text)
        if text_parts:
            description = ' '.join(text_parts[:2])[:500]

    if english_term:
        return {
            'english_term': english_term,
            'description': description or "Voir la fiche GDT pour la definition complete.",
            'domain': domain,
            'source_url': full_url
        }

    return None


def _fetch_and_parse_gdt_fiche(driver, url: str) -> Optional[Dict[str, str]]:
    """
    Fetch and parse a single GDT fiche page.
    """
    try:
        driver.get(url)
        time.sleep(2)  # Wait for page to load

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        return _extract_gdt_fiche_data(soup, url)

    except Exception as e:
        print(f"Warning: Failed to fetch fiche: {e}")
        return None


def _extract_gdt_fiche_data(soup, source_url: str) -> Optional[Dict[str, str]]:
    """
    Extract terminology data from a GDT fiche page.

    Structure:
    - French term in heading
    - English translation under "anglais" section
    - Definition under "Définition" section
    - Domain in breadcrumb/header
    """
    translation = ""
    definition = ""
    usage_notes = ""

    # Get the page text for pattern matching
    page_text = soup.get_text(separator='\n')

    # Find English translation
    # Look for "anglais" section and extract the term
    en_match = re.search(r'anglais[:\s]*\n+.*?Terme\s*:\s*\n*([^\n]+)', page_text, re.IGNORECASE)
    if en_match:
        translation = en_match.group(1).strip()
        # Clean up: remove any markdown-style formatting
        translation = re.sub(r'\*+', '', translation).strip()

    # Alternative: look for English terms in specific HTML patterns
    if not translation:
        # Try finding spans or divs with English content
        for elem in soup.find_all(['h3', 'h4', 'strong', 'b']):
            text = elem.get_text(strip=True).lower()
            if 'anglais' in text:
                # Get the next sibling or parent's next content
                next_elem = elem.find_next(['p', 'span', 'div'])
                if next_elem:
                    translation = next_elem.get_text(strip=True)
                    translation = re.sub(r'\*+', '', translation).strip()
                    break

    # Find definition
    def_match = re.search(r'D[ée]finition\s*:\s*\n*([^\n]+(?:\n[^\n]+)?)', page_text, re.IGNORECASE)
    if def_match:
        definition = def_match.group(1).strip()
        # Limit length
        if len(definition) > 500:
            definition = definition[:500] + "..."

    # Find usage notes
    note_match = re.search(r'Note\s*:\s*\n*([^\n]+(?:\n[^\n]+)?)', page_text, re.IGNORECASE)
    if note_match:
        usage_notes = note_match.group(1).strip()
        if len(usage_notes) > 300:
            usage_notes = usage_notes[:300] + "..."

    # If we found at least a definition, return the result
    if definition or translation:
        return {
            'translation': translation or "[Voir la fiche]",
            'definition': definition or "Voir la fiche pour la definition complete.",
            'usage_notes': usage_notes,
            'source_url': source_url
        }

    return None


def get_manual_search_url(search_term: str) -> str:
    """
    Get the manual search URL for OQLF Vitrine Linguistique (GDT).

    Args:
        search_term: The term to search for

    Returns:
        URL string for manual search
    """
    encoded_term = quote_plus(search_term)
    return f"https://vitrinelinguistique.oqlf.gouv.qc.ca/resultats-de-recherche?tx_solr%5Bq%5D={encoded_term}&tx_solr%5Bfilter%5D%5B0%5D=type_stringM%3Agdt"


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
        # Use GDT-only filter with correct query parameter
        url = f"https://vitrinelinguistique.oqlf.gouv.qc.ca/resultats-de-recherche?tx_solr%5Bq%5D={encoded_term}&tx_solr%5Bfilter%5D%5B0%5D=type_stringM%3Agdt"
        driver.get(url)
        time.sleep(5)
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
        with open(".tmp/oqlf_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML saved to .tmp/oqlf_debug.html ({len(html)} chars)")
        sys.exit(0)

    # Test the scraper
    print("Testing OQLF Scraper...")
    print("-" * 50)

    test_terms = ["marketing", "ordinateur"]

    for term in test_terms:
        print(f"\nSearching for: {term}")
        print("=" * 50)

        try:
            results = scrape(term)

            if results:
                print(f"\nFound {len(results)} result(s):")
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
