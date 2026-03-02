"""
OQLF Web Scraper

Scrapes terminology from Office québécois de la langue française (OQLF)
Vitrine linguistique / Grand dictionnaire terminologique (GDT).
Uses requests + BeautifulSoup (no Selenium needed - results are in static HTML).
"""

import re
from typing import List, Dict, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


_SESSION = requests.Session()
_SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})


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

    encoded_term = quote_plus(search_term)
    search_url = (
        f"https://vitrinelinguistique.oqlf.gouv.qc.ca/resultats-de-recherche"
        f"?tx_solr%5Bq%5D={encoded_term}"
        f"&tx_solr%5Bfilter%5D%5B0%5D=type_stringM%3Agdt"
    )

    try:
        resp = _SESSION.get(search_url, timeout=15)
        resp.raise_for_status()

        results = _find_and_parse_gdt_results(resp.text, search_term)

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


def _find_and_parse_gdt_results(html: str, search_term: str) -> List[Dict[str, str]]:
    """
    Find GDT results in search results page and extract data.

    The search results have articles with:
    - data-title="French term FR • English term EN"
    - data-url="/fiche-gdt/fiche/{id}/{slug}"
    - Description text in the article body
    """
    results = []

    try:
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
    if data_title and ' \u2022 ' in data_title:
        # Split by the bullet separator
        parts = data_title.split(' \u2022 ')
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


if __name__ == "__main__":
    import sys

    # Test the scraper
    print("Testing OQLF Scraper...")
    print("-" * 50)

    test_terms = ["marketing", "ordinateur"]
    if len(sys.argv) > 1:
        test_terms = [sys.argv[1]]

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
