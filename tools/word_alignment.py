"""
Word Alignment Tool using Claude API

Maps French words to their English equivalents after translation.
Used for synchronized highlighting between French and English text.
"""

import os
import re
import json
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import anthropic

# Load environment variables
load_dotenv()

# Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
MODEL = "claude-haiku-4-5-20251001"  # Use Haiku for cost efficiency
MAX_TOKENS = 4000
TEMPERATURE = 0


def generate_alignment(french_text: str, english_text: str) -> Dict:
    """
    Generate word-level alignment mapping between French and English text.

    Args:
        french_text: The original French text
        english_text: The translated English text

    Returns:
        Dictionary containing:
        - fr_words: List of French words
        - en_words: List of English words
        - fr_to_en: Dict mapping French word indices to list of English word indices
        - en_to_fr: Dict mapping English word indices to list of French word indices
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set in .env file.")

    # Extract words from both texts (preserving order)
    fr_words = extract_words(french_text)
    en_words = extract_words(english_text)

    if not fr_words or not en_words:
        return {
            'fr_words': fr_words,
            'en_words': en_words,
            'fr_to_en': {},
            'en_to_fr': {}
        }

    # Build prompt for Claude
    prompt = _build_alignment_prompt(fr_words, en_words)

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

        # Parse response
        response_text = message.content[0].text
        alignment = _parse_alignment_response(response_text, len(fr_words), len(en_words))

        # Calculate cost
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        # Haiku pricing: $0.25 input, $1.25 output per million tokens
        cost = (input_tokens / 1_000_000 * 0.25) + (output_tokens / 1_000_000 * 1.25)

        print(f"[OK] Word alignment complete (cost: ${cost:.4f})")

        return {
            'fr_words': fr_words,
            'en_words': en_words,
            'fr_to_en': alignment['fr_to_en'],
            'en_to_fr': alignment['en_to_fr'],
            'cost': cost
        }

    except Exception as e:
        print(f"[ERROR] Word alignment failed: {e}")
        # Return empty alignment on failure
        return {
            'fr_words': fr_words,
            'en_words': en_words,
            'fr_to_en': {},
            'en_to_fr': {}
        }


def extract_words(text: str) -> List[str]:
    """
    Extract words from text, removing markdown formatting.

    Args:
        text: Text to extract words from

    Returns:
        List of words in order
    """
    # Remove markdown formatting markers
    clean_text = text
    clean_text = re.sub(r'\*\*|\*|__|_|~~|==|\+\+', '', clean_text)
    clean_text = re.sub(r'::#[A-Fa-f0-9]+:|::', '', clean_text)
    clean_text = re.sub(r'==#[A-Fa-f0-9]+:', '', clean_text)

    # Extract words (alphanumeric sequences)
    words = re.findall(r'\b[\w\'-]+\b', clean_text, re.UNICODE)

    return words


def _build_alignment_prompt(fr_words: List[str], en_words: List[str]) -> str:
    """
    Build the prompt for word alignment.

    Args:
        fr_words: List of French words with indices
        en_words: List of English words with indices

    Returns:
        Prompt string
    """
    # Format words with indices
    fr_indexed = [f"{i}:{w}" for i, w in enumerate(fr_words)]
    en_indexed = [f"{i}:{w}" for i, w in enumerate(en_words)]

    prompt = f"""You are a translation alignment expert. Given a French text and its English translation, identify which French words correspond to which English words.

FRENCH WORDS (index:word):
{' | '.join(fr_indexed)}

ENGLISH WORDS (index:word):
{' | '.join(en_indexed)}

TASK: Create a mapping where each French word index maps to the English word index(es) that represent the same meaning.

RULES:
1. One French word may map to multiple English words (e.g., "aujourd'hui" -> "today")
2. Multiple French words may map to one English word (e.g., "ne...pas" -> "not")
3. Some words may not have direct equivalents (articles, restructured sentences)
4. Focus on content words (nouns, verbs, adjectives, adverbs)
5. Skip function words that don't translate directly (le, la, de, etc.) unless they're part of a phrase

OUTPUT FORMAT: Return ONLY a JSON object with this exact structure:
{{
  "alignments": [
    {{"fr": [0], "en": [0, 1]}},
    {{"fr": [1, 2], "en": [2]}},
    ...
  ]
}}

Each alignment object has:
- "fr": list of French word indices that form a unit
- "en": list of corresponding English word indices

Return ONLY the JSON, no explanation."""

    return prompt


def _parse_alignment_response(response: str, num_fr: int, num_en: int) -> Dict:
    """
    Parse Claude's alignment response into fr_to_en and en_to_fr mappings.

    Args:
        response: JSON response from Claude
        num_fr: Number of French words
        num_en: Number of English words

    Returns:
        Dict with fr_to_en and en_to_fr mappings
    """
    fr_to_en = {}
    en_to_fr = {}

    try:
        # Extract JSON from response (handle potential extra text)
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return {'fr_to_en': {}, 'en_to_fr': {}}

        data = json.loads(json_match.group())
        alignments = data.get('alignments', [])

        for alignment in alignments:
            fr_indices = alignment.get('fr', [])
            en_indices = alignment.get('en', [])

            # Validate indices
            fr_indices = [i for i in fr_indices if 0 <= i < num_fr]
            en_indices = [i for i in en_indices if 0 <= i < num_en]

            # Build mappings
            for fr_idx in fr_indices:
                if fr_idx not in fr_to_en:
                    fr_to_en[fr_idx] = []
                fr_to_en[fr_idx].extend(en_indices)

            for en_idx in en_indices:
                if en_idx not in en_to_fr:
                    en_to_fr[en_idx] = []
                en_to_fr[en_idx].extend(fr_indices)

        # Deduplicate
        fr_to_en = {k: list(set(v)) for k, v in fr_to_en.items()}
        en_to_fr = {k: list(set(v)) for k, v in en_to_fr.items()}

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[WARN] Failed to parse alignment response: {e}")

    return {'fr_to_en': fr_to_en, 'en_to_fr': en_to_fr}


def get_english_indices_for_french(alignment: Dict, fr_indices: List[int]) -> List[int]:
    """
    Look up English word indices for given French word indices.

    Args:
        alignment: Alignment dict from generate_alignment()
        fr_indices: List of French word indices that were selected

    Returns:
        List of corresponding English word indices
    """
    fr_to_en = alignment.get('fr_to_en', {})
    en_indices = []

    for fr_idx in fr_indices:
        en_indices.extend(fr_to_en.get(fr_idx, []))

    return list(set(en_indices))


if __name__ == "__main__":
    # Test the alignment
    print("Testing Word Alignment...")
    print("-" * 50)

    fr_text = "Le Programme de soutien du personnel offre des services aux membres."
    en_text = "The Personnel Support Programs offers services to members."

    result = generate_alignment(fr_text, en_text)

    print(f"\nFrench words: {result['fr_words']}")
    print(f"English words: {result['en_words']}")
    print(f"\nFR -> EN mapping: {result['fr_to_en']}")
    print(f"EN -> FR mapping: {result['en_to_fr']}")
