"""
Translation Engine using Claude API

Translates French text to English using Claude AI with PSP-specific rules and glossary.
"""

import os
import re
from pathlib import Path
from typing import Dict, Optional, List
from dotenv import load_dotenv
import anthropic

from tools.fetch_glossary import fetch_glossary

# Load environment variables
load_dotenv()

# Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
PROMPT_TEMPLATE_PATH = Path(__file__).parent.parent / 'config' / 'prompt_template.txt'
TRANSLATION_RULES_PATH = Path(__file__).parent.parent / 'config' / 'translation_rules.md'

# Model configuration
MODEL = "claude-sonnet-4-20250514"  # Claude Sonnet 4 (latest)
MAX_TOKENS = 8000
TEMPERATURE = 0.3  # Lower temperature for consistency


def translate(
    french_text: str,
    glossary: Optional[Dict[str, str]] = None,
    rules_path: Optional[str] = None
) -> Dict:
    """
    Translate French text to English using Claude API with PSP rules.

    Args:
        french_text: The French text to translate
        glossary: Optional glossary dictionary. If None, fetches from Google Sheets
        rules_path: Optional path to translation rules file

    Returns:
        Dictionary containing:
        - translated_text: The English translation
        - terms_used: List of glossary terms applied (not implemented yet)
        - cost: Estimated API cost in USD
        - model: Model used
        - input_tokens: Number of input tokens
        - output_tokens: Number of output tokens

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not set
        Exception: If API call fails
    """
    # Check API key
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY not set in .env file. "
            "Please add your Anthropic API key to the .env file."
        )

    # Fetch glossary if not provided
    if glossary is None:
        print("Fetching glossary...")
        glossary = fetch_glossary()

    # Track which glossary terms appear in the French text
    terms_used = []
    if glossary:
        for french_term, english_term in glossary.items():
            # Word boundary matching to avoid false positives
            pattern = r'\b' + re.escape(french_term) + r'\b'
            if re.search(pattern, french_text, re.IGNORECASE):
                terms_used.append({'french': french_term, 'english': english_term})

    # Load prompt template
    prompt = _build_prompt(french_text, glossary, rules_path)

    # Call Claude API
    print(f"Translating with {MODEL}...")
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extract translation
        translated_text = message.content[0].text

        # Calculate cost (approximate)
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens

        # Pricing for Claude 3.5 Sonnet (as of 2024/2025)
        # Input: $3 per million tokens, Output: $15 per million tokens
        cost = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)

        result = {
            'translated_text': translated_text,
            'terms_used': terms_used,
            'glossary_used': len(terms_used) > 0,
            'cost': cost,
            'model': MODEL,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        }

        print("[OK] Translation complete")
        print(f"  Input tokens: {input_tokens}")
        print(f"  Output tokens: {output_tokens}")
        print(f"  Estimated cost: ${cost:.4f}")

        return result

    except Exception as e:
        print(f"[ERROR] Translation failed: {e}")
        raise


def _build_prompt(
    french_text: str,
    glossary: Dict[str, str],
    rules_path: Optional[str] = None
) -> str:
    """
    Build the prompt for Claude by injecting glossary and rules into template.

    Args:
        french_text: The French text to translate
        glossary: Dictionary of French-English term pairs
        rules_path: Optional path to translation rules file

    Returns:
        Complete prompt string ready for Claude API
    """
    # Load prompt template
    if not PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Prompt template not found at {PROMPT_TEMPLATE_PATH}")

    with open(PROMPT_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()

    # Format glossary terms for prompt
    glossary_text = _format_glossary(glossary)

    # Load translation rules (optional, for reference)
    # The rules are already embedded in the prompt template
    # but we could load them dynamically if needed

    # Inject variables into template
    prompt = template.format(
        glossary_terms=glossary_text,
        french_text=french_text
    )

    return prompt


def _format_glossary(glossary: Dict[str, str]) -> str:
    """
    Format glossary dictionary into a readable string for the prompt.

    Args:
        glossary: Dictionary of French-English term pairs

    Returns:
        Formatted string with term pairs
    """
    if not glossary:
        return "No glossary terms available."

    # Format as a list with French → English
    lines = []
    for french, english in glossary.items():
        lines.append(f"- {french} → {english}")

    return "\n".join(lines)


def estimate_cost(text: str, glossary_size: int = 100) -> float:
    """
    Estimate the cost of translating a text based on character count.

    This is a rough estimate based on average token-to-character ratio.

    Args:
        text: The text to estimate
        glossary_size: Approximate number of terms in glossary

    Returns:
        Estimated cost in USD
    """
    # Rough estimate: 1 token ≈ 4 characters for French/English
    # Plus overhead from prompt template and glossary
    text_tokens = len(text) / 4
    glossary_tokens = glossary_size * 10  # Rough estimate for glossary
    template_tokens = 500  # Prompt template overhead

    total_input_tokens = text_tokens + glossary_tokens + template_tokens
    estimated_output_tokens = text_tokens * 1.1  # Slightly longer output

    # Claude 3.5 Sonnet pricing
    cost = (total_input_tokens / 1_000_000 * 3.0) + (estimated_output_tokens / 1_000_000 * 15.0)

    return cost


if __name__ == "__main__":
    # Test the translation engine
    print("Testing Translation Engine...")
    print("-" * 50)

    # Sample French text
    sample_text = """
    **Bienvenue** au Programme de soutien du personnel

    Le *Programme de soutien du personnel* (PSP) offre des services à nos membres.

    Coût: 100$
    Distance: 5 kilomètres

    Ne pas traduire: bouton rouge, Encadré
    """

    try:
        # Estimate cost first
        estimated_cost = estimate_cost(sample_text)
        print(f"Estimated cost: ${estimated_cost:.4f}")
        print()

        # Perform translation
        result = translate(sample_text)

        print("\nTranslated Text:")
        print("-" * 50)
        print(result['translated_text'])
        print("-" * 50)

        print(f"\nActual cost: ${result['cost']:.4f}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
