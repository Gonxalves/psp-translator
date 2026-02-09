"""
Canada.ca Terminology Scraper

Searches canada.ca for French terms and extracts English equivalents
by navigating to parallel English pages and using Claude AI analysis.
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
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv
import anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')


def scrape(search_term: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    Search canada.ca for a French term and find its English equivalent.

    Args:
        search_term: French term to search for
        max_results: Maximum number of results to return (default: 3)

    Returns:
        List of dictionaries containing:
        - english_term: English equivalent term
        - description: Context from the page
        - domain: Subject domain (empty for Canada.ca)
        - source_url: English page URL (proof URL)
    """
    print(f"Searching Canada.ca for: '{search_term}'")

    chrome_options = _get_chrome_options()
    driver = None
    results = []

    try:
        driver = webdriver.Chrome(options=chrome_options)

        # Step 1: Search for French pages on canada.ca
        french_urls = _search_canada_ca(driver, search_term)

        if not french_urls:
            print(f"No French pages found for '{search_term}'")
            return [{
                'english_term': "[Recherche manuelle]",
                'description': f"Aucun resultat trouve sur canada.ca pour '{search_term}'",
                'domain': "",
                'source_url': get_manual_search_url(search_term)
            }]

        print(f"Found {len(french_urls)} French page(s)")

        # Step 2: Process each French URL
        for i, french_url in enumerate(french_urls[:max_results]):
            print(f"Processing page {i+1}: {french_url}")

            try:
                # Navigate to French page
                driver.get(french_url)
                time.sleep(2)

                # Extract French page content
                french_soup = BeautifulSoup(driver.page_source, 'html.parser')
                french_content = _extract_page_content(french_soup)

                # Verify term appears on page
                if search_term.lower() not in french_content.lower():
                    print(f"  Term not found on page, skipping")
                    continue

                # Find English URL
                english_url = _get_english_url(driver, french_url, french_soup)

                if not english_url:
                    print(f"  No English version found, skipping")
                    continue

                print(f"  English URL: {english_url}")

                # Navigate to English page
                driver.get(english_url)
                time.sleep(2)

                # Extract English page content
                english_soup = BeautifulSoup(driver.page_source, 'html.parser')
                english_content = _extract_page_content(english_soup)

                # Use Claude to find English equivalent
                english_term = _extract_english_term(
                    search_term,
                    french_content,
                    english_content
                )

                if english_term and english_term != "NOT_FOUND":
                    # Get page title for description
                    title_tag = english_soup.find('title')
                    page_title = title_tag.get_text(strip=True) if title_tag else "Canada.ca"

                    results.append({
                        'english_term': english_term,
                        'description': f"Source: {page_title}",
                        'domain': "",
                        'source_url': english_url
                    })
                    print(f"  Found: '{english_term}'")
                else:
                    # Couldn't extract term but page exists
                    results.append({
                        'english_term': "[Voir la page]",
                        'description': f"Terme trouve mais extraction automatique impossible",
                        'domain': "",
                        'source_url': english_url
                    })
                    print(f"  Could not extract term automatically")

            except Exception as e:
                print(f"  Error processing page: {e}")
                continue

        if not results:
            return [{
                'english_term': "[Recherche manuelle]",
                'description': f"Impossible d'extraire les equivalents anglais pour '{search_term}'",
                'domain': "",
                'source_url': get_manual_search_url(search_term)
            }]

        print(f"[OK] Found {len(results)} result(s)")
        return results

    except Exception as e:
        print(f"[ERROR] Error scraping Canada.ca: {e}")
        return [{
            'english_term': "[Erreur]",
            'description': str(e),
            'domain': "",
            'source_url': get_manual_search_url(search_term)
        }]

    finally:
        if driver:
            driver.quit()


def _get_chrome_options() -> Options:
    """Configure Chrome for headless scraping."""
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
    return chrome_options


def _search_canada_ca(driver, search_term: str) -> List[str]:
    """
    Search DuckDuckGo for canada.ca/fr pages containing the term.

    Returns:
        List of canada.ca/fr URLs
    """
    from urllib.parse import unquote

    query = f"site:canada.ca/fr {search_term}"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    print(f"Searching DuckDuckGo: {query}")
    driver.get(url)
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    urls = []

    # DuckDuckGo HTML results are in <a class="result__a"> tags
    result_links = soup.find_all('a', class_='result__a')

    for link in result_links:
        href = link.get('href', '')

        # DuckDuckGo wraps URLs in redirects, extract the actual URL
        if 'uddg=' in href:
            match = re.search(r'uddg=([^&]+)', href)
            if match:
                actual_url = unquote(match.group(1))
                if 'canada.ca/fr' in actual_url:
                    urls.append(actual_url)
        elif href.startswith('http') and 'canada.ca/fr' in href:
            urls.append(href)

    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    return unique_urls[:5]  # Return top 5 URLs


def _get_english_url(driver, french_url: str, soup: BeautifulSoup) -> Optional[str]:
    """
    Find the English equivalent URL from a French canada.ca page.

    Strategies:
    1. Look for hreflang="en" link in head
    2. Look for English language toggle link
    3. Simple URL transformation /fr/ -> /en/
    """
    # Strategy 1: Look for hreflang link
    hreflang_link = soup.find('link', attrs={'hreflang': 'en'})
    if hreflang_link and hreflang_link.get('href'):
        href = hreflang_link['href']
        if href.startswith('/'):
            href = 'https://www.canada.ca' + href
        return href

    # Strategy 2: Look for language toggle link
    # Canada.ca typically has a link with "English" text
    english_links = soup.find_all('a', string=re.compile(r'English', re.I))
    for link in english_links:
        href = link.get('href', '')
        if '/en/' in href:
            if href.startswith('/'):
                href = 'https://www.canada.ca' + href
            return href

    # Also try finding by lang attribute
    en_link = soup.find('a', attrs={'lang': 'en'})
    if en_link and en_link.get('href'):
        href = en_link['href']
        if href.startswith('/'):
            href = 'https://www.canada.ca' + href
        if '/en/' in href:
            return href

    # Strategy 3: Simple URL transformation
    if '/fr/' in french_url:
        english_url = french_url.replace('/fr/', '/en/')
        return english_url

    return None


def _extract_page_content(soup: BeautifulSoup) -> str:
    """
    Extract main content from a canada.ca page.

    Focuses on the <main> element and removes navigation/footer.
    """
    # Try to find main content area
    main = soup.find('main') or soup.find('article') or soup.find('div', class_='container')

    if main:
        # Remove script and style elements
        for element in main.find_all(['script', 'style', 'nav', 'footer', 'aside']):
            element.decompose()

        text = main.get_text(separator=' ', strip=True)
    else:
        # Fallback to body
        body = soup.find('body')
        if body:
            for element in body.find_all(['script', 'style', 'nav', 'footer', 'aside', 'header']):
                element.decompose()
            text = body.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)

    return text[:3000]  # Limit to 3000 chars


def _extract_english_term(
    french_term: str,
    french_content: str,
    english_content: str
) -> Optional[str]:
    """
    Use Claude to find the English equivalent of a French term
    by comparing parallel French and English page content.
    """
    if not ANTHROPIC_API_KEY:
        print("Warning: ANTHROPIC_API_KEY not set")
        return None

    prompt = f"""You are a terminology expert. Given a French term and parallel
French/English content from the same canada.ca page, identify the exact
English equivalent term.

FRENCH TERM TO FIND: {french_term}

FRENCH PAGE CONTENT:
{french_content[:2000]}

ENGLISH PAGE CONTENT:
{english_content[:2000]}

INSTRUCTIONS:
1. Find where "{french_term}" appears in the French content
2. Identify the corresponding section in the English content
3. Extract the exact English equivalent term
4. If multiple equivalents exist, choose the most official/formal one

Return ONLY the English term, nothing else. If you cannot find an equivalent,
respond with "NOT_FOUND"."""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            temperature=0,  # Deterministic for terminology
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text.strip()
        return result

    except Exception as e:
        print(f"Error calling Claude API: {e}")
        return None


def get_manual_search_url(search_term: str) -> str:
    """
    Get the manual search URL for canada.ca.
    """
    return f"https://www.canada.ca/fr/sr/srb.html?allq={quote_plus(search_term)}"


if __name__ == "__main__":
    import sys

    # Test the scraper
    print("Testing Canada.ca Scraper...")
    print("-" * 50)

    if len(sys.argv) > 1:
        term = sys.argv[1]
    else:
        term = "assurance-emploi"

    print(f"\nSearching for: {term}")
    print("=" * 50)

    try:
        results = scrape(term)

        if results:
            print(f"\nFound {len(results)} result(s):")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['english_term']}")
                print(f"   Description: {result['description']}")
                if result.get('domain'):
                    print(f"   Domain: {result['domain']}")
                print(f"   Source URL: {result['source_url']}")
        else:
            print("No results found")

        # Show manual search URL
        print(f"\nManual search URL: {get_manual_search_url(term)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
