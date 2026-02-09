"""
PSP Translator - French to English Translation App

A Streamlit web application for translating French text to English with PSP-specific
rules, glossary integration, and terminology checking tools.
"""

import os
import streamlit as st
import time
import concurrent.futures
from pathlib import Path
from io import BytesIO

# Import tools
from tools import translate_text, fetch_glossary, scrape_termium, scrape_oqlf, scrape_canada
from tools import log_action, add_to_glossary, parse_word, export_word
from tools import clickable_text, word_alignment

# Page configuration
st.set_page_config(
    page_title="PSP Translator",
    page_icon="🇨🇦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Password protection (only when APP_PASSWORD is set in .env) ---
_app_password = os.environ.get("APP_PASSWORD")
if _app_password:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("PSP Translator")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == _app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Wrong password.")
        st.stop()

# Custom CSS for styling
st.markdown("""
<style>
    .translation-output {
        font-family: 'Times New Roman', Times, serif;
        font-size: 12pt;
        line-height: 1.5;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 5px;
        border: 1px solid #dee2e6;
    }

    .translation-output strong {
        font-weight: bold;
    }

    .translation-output em {
        font-style: italic;
    }

    .translation-output mark {
        background-color: #FFFF00;
        padding: 0 2px;
    }

    .translation-output del {
        text-decoration: line-through;
    }

    .translation-output u {
        text-decoration: underline;
    }

    .stButton>button {
        width: 100%;
    }

    .stats-box {
        padding: 10px;
        background-color: #e9ecef;
        border-radius: 5px;
        margin: 5px 0;
    }

    h1, h2, h3 {
        color: #1f2937;
    }

    .format-hint {
        font-size: 12px;
        color: #666;
        margin-top: -10px;
        margin-bottom: 10px;
        font-style: italic;
    }

    .upload-section {
        padding: 10px;
        background-color: #f0f2f6;
        border-radius: 8px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    if 'translated_text' not in st.session_state:
        st.session_state.translated_text = ""

    if 'french_text' not in st.session_state:
        st.session_state.french_text = ""

    if 'glossary' not in st.session_state:
        st.session_state.glossary = {}
        st.session_state.glossary_loaded = False

    if 'accumulated_results' not in st.session_state:
        st.session_state.accumulated_results = []

    if 'search_executor' not in st.session_state:
        st.session_state.search_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    if 'pending_futures' not in st.session_state:
        st.session_state.pending_futures = []

    if 'translation_history' not in st.session_state:
        st.session_state.translation_history = []

    if 'uploaded_file_name' not in st.session_state:
        st.session_state.uploaded_file_name = None

    if 'selected_term' not in st.session_state:
        st.session_state.selected_term = ""


    if 'last_term_action_ts' not in st.session_state:
        st.session_state.last_term_action_ts = None

    if 'word_alignment' not in st.session_state:
        st.session_state.word_alignment = None

    if 'en_highlight_indices' not in st.session_state:
        st.session_state.en_highlight_indices = []

    if 'fr_highlight_indices' not in st.session_state:
        st.session_state.fr_highlight_indices = []

    if 'replace_mode' not in st.session_state:
        st.session_state.replace_mode = False

    if 'replace_data' not in st.session_state:
        st.session_state.replace_data = None

    # Undo stack: list of dicts with {'text': str, 'old_term': str, 'new_term': str, 'count': int}
    if 'undo_stack' not in st.session_state:
        st.session_state.undo_stack = []

    # Post-replacement highlight: {'new_term': str, 'positions': [(start, end), ...]}
    if 'highlight_change' not in st.session_state:
        st.session_state.highlight_change = None

    if 'last_edit_ts' not in st.session_state:
        st.session_state.last_edit_ts = None


def load_glossary():
    """Load glossary from Excel file with in-memory caching via session_state"""
    import time as _time

    # Initialize load timestamp if not set
    if 'glossary_loaded_at' not in st.session_state:
        st.session_state.glossary_loaded_at = 0

    # Only reload if: first load, or cache expired (every 5 minutes), or manually triggered
    needs_reload = False

    if not st.session_state.glossary_loaded:
        needs_reload = True
    else:
        # Check if in-memory cache expired (use CACHE_TTL_MINUTES from env)
        cache_ttl = int(os.environ.get('CACHE_TTL_MINUTES', '5')) * 60
        if _time.time() - st.session_state.glossary_loaded_at > cache_ttl:
            needs_reload = True

    if needs_reload:
        with st.spinner("Loading glossary from Excel file..."):
            try:
                st.session_state.glossary = fetch_glossary.fetch_glossary(force_refresh=True)
                st.session_state.glossary_loaded = True
                st.session_state.glossary_loaded_at = _time.time()
                return True
            except Exception as e:
                st.error(f"Failed to load glossary: {e}")
                return False
    return True


def copy_to_clipboard_with_formatting(text: str) -> bool:
    """
    Copy text to Windows clipboard with HTML formatting preserved.
    When pasted into Word, formatting (bold, italic, etc.) will be retained.
    On non-Windows platforms, shows a fallback message.
    """
    import sys
    if sys.platform != 'win32':
        st.info("Clipboard copy is not available on the server. Use the Download Word button or select the text and press Ctrl+C.")
        return False
    try:
        import win32clipboard
        import re
        import html as html_module

        # Convert markdown to HTML for clipboard
        html_content = text

        # Escape HTML entities first
        html_content = html_module.escape(html_content)

        # Highlight with color (use mso-highlight for Word compatibility)
        html_content = re.sub(
            r'==(#[A-Fa-f0-9]{6}):(.+?)==',
            r'<span style="background-color: \1; mso-highlight: \1">\2</span>',
            html_content
        )
        # Simple highlight (yellow) - use mso-highlight for Word
        html_content = re.sub(r'==(.+?)==', r'<span style="background-color: yellow; mso-highlight: yellow">\1</span>', html_content)
        # Font color
        html_content = re.sub(
            r'::(#[A-Fa-f0-9]{6}):(.+?)::',
            r'<span style="color: \1">\2</span>',
            html_content
        )
        # Strikethrough (use style for Word compatibility)
        html_content = re.sub(r'~~(.+?)~~', r'<span style="text-decoration: line-through">\1</span>', html_content)
        # Underline (use style for Word compatibility)
        html_content = re.sub(r'\+\+(.+?)\+\+', r'<span style="text-decoration: underline">\1</span>', html_content)
        # Bold and italic
        html_content = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', html_content)
        # Bold
        html_content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html_content)
        # Italic
        html_content = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', html_content)
        # Line breaks
        html_content = html_content.replace('\n', '<br>')

        # Build Windows clipboard HTML format
        html_body = f'<html><body><span style="font-family: Times New Roman; font-size: 12pt;">{html_content}</span></body></html>'

        # Windows HTML clipboard format requires specific headers
        header = (
            "Version:0.9\r\n"
            "StartHTML:{start_html:08d}\r\n"
            "EndHTML:{end_html:08d}\r\n"
            "StartFragment:{start_fragment:08d}\r\n"
            "EndFragment:{end_fragment:08d}\r\n"
        )

        # Calculate positions
        prefix = "<!--StartFragment-->"
        suffix = "<!--EndFragment-->"

        # Build the full HTML with markers
        html_with_markers = f'<html><body><span style="font-family: Times New Roman; font-size: 12pt;">{prefix}{html_content}{suffix}</span></body></html>'

        # Calculate header length (with placeholder values)
        header_length = len(header.format(start_html=0, end_html=0, start_fragment=0, end_fragment=0))

        start_html = header_length
        end_html = header_length + len(html_with_markers.encode('utf-8'))
        start_fragment = header_length + html_with_markers.find(prefix) + len(prefix)
        end_fragment = header_length + html_with_markers.find(suffix)

        # Build final clipboard data
        final_header = header.format(
            start_html=start_html,
            end_html=end_html,
            start_fragment=start_fragment,
            end_fragment=end_fragment
        )

        clipboard_data = final_header + html_with_markers

        # Also prepare plain text (strip markdown)
        plain_text = text
        plain_text = re.sub(r'==(#[A-Fa-f0-9]{6}):(.+?)==', r'\2', plain_text)
        plain_text = re.sub(r'==(.+?)==', r'\1', plain_text)
        plain_text = re.sub(r'::(#[A-Fa-f0-9]{6}):(.+?)::', r'\2', plain_text)
        plain_text = re.sub(r'~~(.+?)~~', r'\1', plain_text)
        plain_text = re.sub(r'\+\+(.+?)\+\+', r'\1', plain_text)
        plain_text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', plain_text)
        plain_text = re.sub(r'\*\*(.+?)\*\*', r'\1', plain_text)
        plain_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', plain_text)

        # Copy to clipboard
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()

            # Set HTML format
            html_format = win32clipboard.RegisterClipboardFormat("HTML Format")
            win32clipboard.SetClipboardData(html_format, clipboard_data.encode('utf-8'))

            # Also set plain text as fallback
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, plain_text)
        finally:
            win32clipboard.CloseClipboard()

        return True

    except ImportError:
        st.error("pywin32 not installed. Run: pip install pywin32")
        return False
    except Exception as e:
        st.error(f"Failed to copy to clipboard: {e}")
        return False


def markdown_to_html(text):
    """
    Convert simple markdown formatting to HTML for display.

    Handles:
    - **bold** → <strong>bold</strong>
    - *italic* → <em>italic</em>
    - ++underline++ → <u>underline</u>
    - ~~strikethrough~~ → <del>strikethrough</del>
    - ==highlighted== → <mark>highlighted</mark>
    - ==#COLOR:text== → <mark style="background-color: #COLOR">text</mark>
    - ::COLOR:text:: → <span style="color: COLOR">text</span>
    - Line breaks and spacing
    """
    import re
    import html

    # Escape HTML first to prevent XSS
    text = html.escape(text)

    # Highlight with color: ==#COLOR:text== → <mark style="background-color: #COLOR">text</mark>
    text = re.sub(
        r'==(#[A-Fa-f0-9]{6}):(.+?)==',
        r'<mark style="background-color: \1">\2</mark>',
        text
    )

    # Simple highlight: ==text== → <mark>text</mark>
    text = re.sub(r'==(.+?)==', r'<mark>\1</mark>', text)

    # Font color: ::COLOR:text:: → <span style="color: COLOR">text</span>
    text = re.sub(
        r'::(#[A-Fa-f0-9]{6}):(.+?)::',
        r'<span style="color: \1">\2</span>',
        text
    )

    # Strikethrough: ~~text~~ → <del>text</del>
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)

    # Underline: ++text++ → <u>text</u>
    text = re.sub(r'\+\+(.+?)\+\+', r'<u>\1</u>', text)

    # Bold and italic: ***text*** → <strong><em>text</em></strong>
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)

    # Bold: **text** → <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Italic: *text* → <em>text</em> (but not **)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)

    # Preserve line breaks
    text = text.replace('\n', '<br>')

    return text


def append_search_results(term, tool, results):
    """Append a completed search to the accumulated results."""
    search_group = {
        'term': term.strip().lower(),
        'term_display': term.strip(),
        'tool': tool,
        'results': results,
        'timestamp': time.time()
    }
    st.session_state.accumulated_results.append(search_group)


def get_results_grouped_by_term():
    """Group accumulated search results by normalized term, preserving insertion order."""
    from collections import OrderedDict

    groups = OrderedDict()
    for search_group in st.session_state.accumulated_results:
        key = search_group['term']
        if key not in groups:
            groups[key] = {
                'display_term': search_group['term_display'],
                'searches': []
            }
        groups[key]['searches'].append(search_group)

    return groups


TOOL_DISPLAY_NAMES = {'termium': 'TERMIUM Plus', 'oqlf': 'OQLF', 'canada': 'Canada.ca'}


def _run_search(tool_key, term):
    """Run a terminology search in a background thread."""
    if tool_key == 'termium':
        return scrape_termium.scrape(term)
    elif tool_key == 'oqlf':
        return scrape_oqlf.scrape(term)
    elif tool_key == 'canada':
        return scrape_canada.scrape(term)
    return []


def submit_search(term, tool_key):
    """Submit a search to the background thread pool."""
    tool_display = TOOL_DISPLAY_NAMES.get(tool_key, tool_key)
    future = st.session_state.search_executor.submit(_run_search, tool_key, term)
    st.session_state.pending_futures.append({
        'future': future,
        'term': term,
        'tool': tool_display,
    })


def find_english_equivalent(french_term):
    """
    Find the current English equivalent of a French term in the translated text.

    Uses a two-step approach:
    1. Try word alignment first (fast, no API cost)
    2. Fall back to Claude AI to intelligently identify the English equivalent
    """
    translated = st.session_state.translated_text
    french_text = st.session_state.french_text
    if not translated or not french_text:
        return None

    # Step 1: Try word alignment
    alignment = st.session_state.word_alignment
    if alignment and alignment.get('fr_to_en'):
        fr_words = alignment.get('fr_words', [])
        en_words = alignment.get('en_words', [])
        fr_to_en = alignment.get('fr_to_en', {})

        search_words = french_term.lower().split()
        if search_words:
            for i in range(len(fr_words) - len(search_words) + 1):
                match = all(
                    fr_words[i + j].lower() == search_words[j]
                    for j in range(len(search_words))
                )
                if match:
                    en_indices = []
                    for j in range(len(search_words)):
                        en_indices.extend(fr_to_en.get(i + j, []))
                    en_indices = sorted(set(en_indices))
                    if en_indices:
                        candidate = ' '.join(
                            en_words[idx] for idx in en_indices if idx < len(en_words)
                        )
                        # Verify the candidate actually appears in the translated text
                        if find_all_occurrences(translated, candidate):
                            return candidate

    # Step 2: Use Claude AI to find the English equivalent
    import os
    import anthropic
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Use a short excerpt of both texts to keep costs low
        fr_excerpt = french_text[:3000]
        en_excerpt = translated[:3000]

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            temperature=0,
            messages=[{
                "role": "user",
                "content": (
                    f"In the French text below, the term \"{french_term}\" appears. "
                    f"What is the EXACT English word or short phrase used to translate "
                    f"this term in the English text below? "
                    f"Reply with ONLY the English word/phrase, nothing else.\n\n"
                    f"FRENCH TEXT:\n{fr_excerpt}\n\n"
                    f"ENGLISH TEXT:\n{en_excerpt}"
                )
            }]
        )

        candidate = message.content[0].text.strip().strip('"').strip("'")

        # Verify the candidate actually appears in the translated text
        if candidate and find_all_occurrences(translated, candidate):
            return candidate

        # If exact match failed, try case-insensitive search with the raw response
        candidate_lower = candidate.lower()
        import re
        pattern = r'(?<!\w)' + re.escape(candidate_lower) + r'(?!\w)'
        match = re.search(pattern, translated, re.IGNORECASE)
        if match:
            # Return the text as it actually appears in the translation
            return match.group(0)

    except Exception as e:
        print(f"[WARN] AI lookup for English equivalent failed: {e}")

    return None


def find_all_occurrences(text, term):
    """
    Find all occurrences of a term in text using word-boundary matching.
    Returns list of (start, end) character positions.
    """
    import re
    # Use word boundaries that work across markdown markers
    pattern = r'(?<!\w)' + re.escape(term) + r'(?!\w)'
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    return [(m.start(), m.end()) for m in matches]


def apply_replacements(text, occurrences, decisions, new_term):
    """
    Apply accepted replacements from end to start to preserve character positions.
    Returns the modified text.
    """
    # Pair occurrences with decisions, filter to accepted ones
    accepted = [
        occ for occ, dec in zip(occurrences, decisions)
        if dec is True
    ]
    # Sort by position descending so we replace from end to start
    accepted.sort(key=lambda x: x[0], reverse=True)

    for start, end in accepted:
        text = text[:start] + new_term + text[end:]

    return text


def _finish_replace_mode(data):
    """Finish the step-by-step replacement mode after all occurrences are processed."""
    old_term = data['old_english']
    new_term = data['new_english']
    steps = data['steps']
    replace_steps = [s for s in steps if s['action'] == 'replace']
    replaced_count = len(replace_steps)

    # Build individual undo entries for each replacement (in reverse order)
    for step in reversed(replace_steps):
        used_term = step.get('used_term', new_term)
        st.session_state.undo_stack.append({
            'text': step['text_before'],
            'old_term': old_term,
            'new_term': used_term,
            'count': 1,
        })

    st.session_state.replace_mode = False
    st.session_state.replace_data = None
    st.session_state.word_alignment = None

    if replaced_count > 0:
        # Collect all unique terms used for highlighting
        used_terms = list(dict.fromkeys(
            s.get('used_term', new_term) for s in replace_steps
        ))
        st.session_state.highlight_change = {
            'new_term': used_terms[0],
            'old_term': old_term,
            'replaced_count': replaced_count,
            'text_before_all': data['text_before_all'],
            'all_new_terms': used_terms,
        }
    else:
        st.toast("No replacements made.")


def main():
    """Main application function"""
    initialize_session_state()

    # Header with logo - use a single markdown block with flexbox for perfect vertical alignment
    logo_path = Path("assets/psp_logo.png")
    if logo_path.exists():
        import base64
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:24px;padding:10px 0 10px 0;">'
            f'<img src="data:image/png;base64,{logo_b64}" style="width:160px;height:auto;">'
            f'<h1 style="margin:0;color:#1f2937;">PSP Translator</h1>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.title("🇨🇦 PSP Translator")

    # Load glossary
    if not load_glossary():
        st.warning("⚠ Running without glossary. Some features may not work correctly.")

    # Display glossary stats
    if st.session_state.glossary_loaded:
        glossary_stats = fetch_glossary.get_glossary_stats()
        if glossary_stats.get('cached'):
            st.info(
                f"📚 Glossary: {glossary_stats['term_count']} terms loaded "
                f"(last updated: {glossary_stats.get('last_updated', 'N/A')})"
            )

    st.divider()

    # Main translation interface
    st.subheader("Translation")

    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown("**French Text**")

        # Word document upload section
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Upload a Word document (.docx)",
            type=['docx'],
            key="word_upload",
            help="Upload a Word document to extract and translate its content. Formatting (bold, italic) will be preserved."
        )

        if uploaded_file is not None:
            # Check if this is a new file
            if st.session_state.uploaded_file_name != uploaded_file.name:
                with st.spinner("Extracting text from Word document..."):
                    try:
                        # Read the file into BytesIO
                        file_bytes = BytesIO(uploaded_file.read())

                        # Parse the Word document
                        extracted_text = parse_word.parse_word_document(file_bytes)

                        # Get document info
                        file_bytes.seek(0)  # Reset for re-reading
                        doc_info = parse_word.get_document_info(file_bytes)

                        # Update session state - must update french_input (the widget key) directly
                        st.session_state.french_input = extracted_text
                        st.session_state.french_text = extracted_text
                        st.session_state.uploaded_file_name = uploaded_file.name

                        st.success(
                            f"✅ Extracted text from '{uploaded_file.name}' "
                            f"({doc_info['word_count']} words, {doc_info['paragraph_count']} paragraphs)"
                        )

                        # Rerun to update the text area with extracted content
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Failed to parse Word document: {e}")

        st.markdown('</div>', unsafe_allow_html=True)

        # Text area with current value from session state
        french_text = st.text_area(
            "Or type/paste French text directly:",
            value=st.session_state.french_text,
            height=300,
            key="french_input",
            placeholder="Entrez le texte francais ici ou uploadez un document Word..."
        )

        # Update session state if user types directly
        if french_text != st.session_state.french_text:
            st.session_state.french_text = french_text

        st.markdown('<p class="format-hint">💡 Formatting: **bold**, *italic*, ++underline++, ~~strikethrough~~, ==highlight==</p>', unsafe_allow_html=True)

    # Translate and Refresh buttons - placed outside left_col to avoid nested-column duplication
    btn_col_a, btn_col_b, btn_spacer = st.columns([1, 0.5, 1.5])
    with btn_col_a:
        translate_button = st.button("🔄 Translate", type="primary", use_container_width=True, key="translate_btn")
    with btn_col_b:
        refresh_clicked = st.button("🔄 Refresh Glossary", use_container_width=True, key="refresh_glossary_btn")

    if refresh_clicked:
        st.session_state.glossary_loaded = False
        load_glossary()
        st.success("Glossary refreshed!")

    with right_col:
        st.markdown("**Translation Status**")
        if translate_button:
            if french_text:
                with st.spinner("Translating... This may take a moment."):
                    try:
                        # Estimate cost first
                        estimated_cost = translate_text.estimate_cost(
                            french_text,
                            len(st.session_state.glossary)
                        )

                        # Translate
                        result = translate_text.translate(
                            french_text=french_text,
                            glossary=st.session_state.glossary,
                            rules_path="config/translation_rules.md"
                        )

                        st.session_state.translated_text = result['translated_text']

                        # Generate word alignment for synchronized highlighting
                        try:
                            alignment = word_alignment.generate_alignment(
                                french_text,
                                result['translated_text']
                            )
                            st.session_state.word_alignment = alignment
                            st.session_state.en_highlight_indices = []
                        except Exception as e:
                            print(f"Warning: Failed to generate word alignment: {e}")
                            st.session_state.word_alignment = None

                        # Log the translation
                        try:
                            log_action.log_translation(
                                glossary_used=result.get('glossary_used', False)
                            )
                        except Exception as e:
                            print(f"Warning: Failed to log translation: {e}")

                        # Add to history
                        st.session_state.translation_history.append({
                            'french': french_text[:50] + "..." if len(french_text) > 50 else french_text,
                            'english': result['translated_text'][:50] + "..." if len(result['translated_text']) > 50 else result['translated_text'],
                            'cost': result['cost']
                        })

                        st.success(
                            f"✅ Translation complete! "
                            f"(Tokens: {result['input_tokens']} in / {result['output_tokens']} out, "
                            f"Cost: ${result['cost']:.4f})"
                        )

                    except Exception as e:
                        st.error(f"❌ Translation failed: {e}")
            else:
                st.warning("⚠ Please enter French text or upload a Word document to translate.")

    # Side-by-side preview boxes
    preview_left, preview_right = st.columns(2)

    with preview_left:
        st.markdown("**Formatted Preview:** *(click words to look up)*")
        if french_text:
            formatted_preview = markdown_to_html(french_text)
            # Render clickable text - click words to get context menu
            # Returns a dict when user selects a tool from the context menu
            term_action = clickable_text.render_clickable(
                html_content=formatted_preview,
                highlight_indices=st.session_state.fr_highlight_indices,
                key="french_preview"
            )

            # Check if user triggered a new terminology lookup
            if term_action and isinstance(term_action, dict):
                action_ts = term_action.get('ts')
                if action_ts and action_ts != st.session_state.last_term_action_ts:
                    st.session_state.last_term_action_ts = action_ts

                    # Submit search to background thread pool immediately
                    term_lookup = term_action.get('term', '')
                    term_tool = term_action.get('tool', '')
                    if term_lookup and term_tool:
                        submit_search(term_lookup, term_tool)
                    st.session_state.selected_term = term_lookup

                    # Update highlights for this term
                    term_indices_str = term_action.get('indices', '')
                    term_indices = []
                    if term_indices_str:
                        try:
                            term_indices = [int(i) for i in term_indices_str.split(',')]
                        except (ValueError, AttributeError):
                            pass
                    st.session_state.fr_highlight_indices = term_indices
                    if st.session_state.word_alignment and term_indices:
                        en_indices = word_alignment.get_english_indices_for_french(
                            st.session_state.word_alignment,
                            term_indices
                        )
                        st.session_state.en_highlight_indices = en_indices
                    else:
                        st.session_state.en_highlight_indices = []
        else:
            st.markdown(
                '<div class="translation-output"></div>',
                unsafe_allow_html=True
            )

    with preview_right:
        st.markdown("**English Translation:**")

        if st.session_state.replace_mode and st.session_state.replace_data:
            # --- REPLACEMENT MODE UI (immediate replacement) ---
            data = st.session_state.replace_data
            current = data['current_idx']
            total = data['total']
            old_term = data['old_english']
            new_term = data['new_english']
            steps = data['steps']
            replaced_so_far = sum(1 for s in steps if s['action'] == 'replace')
            skipped_so_far = sum(1 for s in steps if s['action'] == 'skip')

            # Progress banner
            st.info(
                f"Replacing **'{old_term}'** with **'{new_term}'** "
                f"({current + 1} of {total}) — "
                f"{replaced_so_far} replaced, {skipped_so_far} skipped"
            )
            st.progress(current / total)

            # Find occurrences of old_term still in the text
            # The one to highlight = skipped_so_far (0-indexed among remaining)
            remaining_occurrences = find_all_occurrences(
                st.session_state.translated_text, old_term
            )
            highlight_idx = min(skipped_so_far, len(remaining_occurrences) - 1) if remaining_occurrences else 0

            # Render English text with current occurrence highlighted in orange
            formatted_html = markdown_to_html(st.session_state.translated_text)
            clickable_text.render_replacement_highlight(
                html_content=formatted_html,
                target_term=old_term,
                occurrence_idx=highlight_idx,
                total_occurrences=len(remaining_occurrences),
                key=f"replace_preview_{current}_{len(steps)}"
            )

            # Mini editor: let user modify the replacement term before confirming
            edit_col1, edit_col2 = st.columns([1, 2])
            with edit_col1:
                st.caption(f"**Current:** {old_term}")
            with edit_col2:
                custom_term = st.text_input(
                    "Replace with:",
                    value=new_term,
                    key=f"custom_replace_{current}_{len(steps)}",
                    label_visibility="collapsed",
                    placeholder="Type your correction..."
                )

            # Yes / No / Undo / Cancel buttons
            col_yes, col_no, col_undo_step, col_cancel = st.columns(4)

            # Use the custom term (user may have edited it)
            effective_term = custom_term.strip() if custom_term and custom_term.strip() else new_term

            with col_yes:
                if st.button("Replace", key=f"replace_yes_{current}_{len(steps)}", use_container_width=True, type="primary"):
                    # Save state before replacing
                    steps.append({
                        'action': 'replace',
                        'text_before': st.session_state.translated_text,
                        'used_term': effective_term,
                    })
                    # Replace the highlighted occurrence immediately with the (possibly edited) term
                    if remaining_occurrences and highlight_idx < len(remaining_occurrences):
                        occ = remaining_occurrences[highlight_idx]
                        st.session_state.translated_text = apply_replacements(
                            st.session_state.translated_text,
                            [occ], [True], effective_term
                        )
                    data['current_idx'] += 1
                    st.session_state.word_alignment = None
                    if data['current_idx'] >= total:
                        _finish_replace_mode(data)
                    st.rerun()

            with col_no:
                if st.button("Skip", key=f"replace_no_{current}_{len(steps)}", use_container_width=True):
                    steps.append({
                        'action': 'skip',
                        'text_before': st.session_state.translated_text,
                    })
                    data['current_idx'] += 1
                    if data['current_idx'] >= total:
                        _finish_replace_mode(data)
                    st.rerun()

            with col_undo_step:
                can_undo = len(steps) > 0
                if st.button("Undo", key=f"replace_undo_{current}_{len(steps)}", use_container_width=True, disabled=not can_undo):
                    if steps:
                        last_step = steps.pop()
                        st.session_state.translated_text = last_step['text_before']
                        data['current_idx'] -= 1
                        st.session_state.word_alignment = None
                        st.rerun()

            with col_cancel:
                if st.button("Cancel", key="replace_cancel", use_container_width=True):
                    # Restore original text
                    st.session_state.translated_text = data['text_before_all']
                    st.session_state.replace_mode = False
                    st.session_state.replace_data = None
                    st.session_state.word_alignment = None
                    st.toast("Replacement cancelled — all changes reverted.")
                    st.rerun()

        elif st.session_state.highlight_change and st.session_state.translated_text:
            # --- POST-REPLACEMENT HIGHLIGHT MODE ---
            import re as _re
            change = st.session_state.highlight_change
            replaced_count = change.get('replaced_count', 1)
            # Show all unique replacement terms used
            all_new_terms = change.get('all_new_terms', [change['new_term']])
            terms_display = ", ".join(f"**'{t}'**" for t in all_new_terms)
            st.success(
                f"Replaced **'{change['old_term']}'** with {terms_display} "
                f"({replaced_count} occurrence{'s' if replaced_count > 1 else ''})"
            )

            # Render with all changed terms highlighted in green with zoom animation
            formatted_html = markdown_to_html(st.session_state.translated_text)
            # Highlight each unique term used
            if len(all_new_terms) == 1:
                clickable_text.render_change_highlight(
                    html_content=formatted_html,
                    target_term=all_new_terms[0],
                    key="change_highlight_preview"
                )
            else:
                # For multiple different terms, highlight each one
                # Use render_change_highlight_multi to highlight all of them
                clickable_text.render_change_highlight_multi(
                    html_content=formatted_html,
                    target_terms=all_new_terms,
                    key="change_highlight_preview"
                )

            # --- MINI BEFORE/AFTER EDITOR with individual undo ---
            if st.session_state.undo_stack:
                # Find how many undo entries match this change (same old_term)
                matching_undos = []
                for i in range(len(st.session_state.undo_stack) - 1, -1, -1):
                    entry = st.session_state.undo_stack[i]
                    if entry.get('old_term') == change['old_term']:
                        matching_undos.append(i)
                    else:
                        break  # Stop at first non-matching entry

                with st.expander("Before / After", expanded=True):
                    # Show before/after snippets
                    diff_col1, diff_col2 = st.columns(2)

                    # Use the earliest matching undo for the "before" text
                    earliest_undo = st.session_state.undo_stack[matching_undos[-1]] if matching_undos else st.session_state.undo_stack[-1]

                    with diff_col1:
                        st.markdown("**Before:**")
                        old_text = earliest_undo['text']
                        _pattern = _re.compile(
                            r'(?<!\w)' + _re.escape(change['old_term']) + r'(?!\w)',
                            _re.IGNORECASE
                        )
                        _match = _pattern.search(old_text)
                        if _match:
                            _start = max(0, _match.start() - 80)
                            _end = min(len(old_text), _match.end() + 80)
                            _snippet = old_text[_start:_end]
                            if _start > 0:
                                _snippet = "..." + _snippet
                            if _end < len(old_text):
                                _snippet = _snippet + "..."
                            _snippet_html = _pattern.sub(
                                lambda m: f'<span style="background-color:#FFCDD2;padding:2px 4px;border-radius:3px;font-weight:bold;">{m.group()}</span>',
                                _snippet
                            )
                            st.markdown(f'<div style="font-family:Times New Roman;font-size:12pt;padding:10px;background:#fff;border:1px solid #ddd;border-radius:4px;">{_snippet_html}</div>', unsafe_allow_html=True)
                        else:
                            st.caption("(preview not available)")

                    with diff_col2:
                        st.markdown("**After:**")
                        new_text = st.session_state.translated_text
                        _new_pattern = _re.compile(
                            r'(?<!\w)' + _re.escape(change['new_term']) + r'(?!\w)',
                            _re.IGNORECASE
                        )
                        _new_match = _new_pattern.search(new_text)
                        if _new_match:
                            _start = max(0, _new_match.start() - 80)
                            _end = min(len(new_text), _new_match.end() + 80)
                            _snippet = new_text[_start:_end]
                            if _start > 0:
                                _snippet = "..." + _snippet
                            if _end < len(new_text):
                                _snippet = _snippet + "..."
                            _snippet_html = _new_pattern.sub(
                                lambda m: f'<span style="background-color:#C8E6C9;padding:2px 4px;border-radius:3px;font-weight:bold;">{m.group()}</span>',
                                _snippet
                            )
                            st.markdown(f'<div style="font-family:Times New Roman;font-size:12pt;padding:10px;background:#fff;border:1px solid #ddd;border-radius:4px;">{_snippet_html}</div>', unsafe_allow_html=True)
                        else:
                            st.caption("(preview not available)")

                    st.divider()

                    # Individual undo buttons (one per replacement)
                    if len(matching_undos) > 1:
                        st.markdown(f"**Undo individual replacements** ({len(matching_undos)} changes):")
                        for btn_idx, stack_idx in enumerate(matching_undos):
                            undo_entry = st.session_state.undo_stack[stack_idx]
                            entry_new_term = undo_entry.get('new_term', change['new_term'])
                            # Find a snippet around the occurrence in the before-text
                            _m = _pattern.search(undo_entry['text'])
                            snippet_preview = ""
                            if _m:
                                ctx_start = max(0, _m.start() - 25)
                                ctx_end = min(len(undo_entry['text']), _m.end() + 25)
                                snippet_preview = undo_entry['text'][ctx_start:ctx_end].replace('\n', ' ')
                                if ctx_start > 0:
                                    snippet_preview = "..." + snippet_preview
                                if ctx_end < len(undo_entry['text']):
                                    snippet_preview = snippet_preview + "..."

                            col_label, col_btn = st.columns([3, 1])
                            with col_label:
                                st.caption(f'"{snippet_preview}" -> {entry_new_term}')
                            with col_btn:
                                if st.button("Undo", key=f"undo_individual_{btn_idx}", use_container_width=True):
                                    restored = st.session_state.undo_stack.pop(stack_idx)
                                    st.session_state.translated_text = restored['text']
                                    st.session_state.word_alignment = None
                                    # Remove all undo entries after this one
                                    # (they reference text states that no longer apply)
                                    st.session_state.undo_stack = [
                                        e for i, e in enumerate(st.session_state.undo_stack)
                                        if i < stack_idx
                                    ]
                                    remaining_matches = sum(
                                        1 for e in st.session_state.undo_stack
                                        if e.get('old_term') == change['old_term']
                                    )
                                    if remaining_matches == 0:
                                        st.session_state.highlight_change = None
                                    else:
                                        change['replaced_count'] = remaining_matches
                                    st.toast(f"Reverted: '{restored['new_term']}' back to '{change['old_term']}'")
                                    st.rerun()

                    # Undo All / OK buttons
                    col_undo_all, col_undo_last, col_dismiss = st.columns(3)
                    with col_undo_all:
                        if len(matching_undos) > 1 and change.get('text_before_all'):
                            if st.button("Undo All", key="undo_all_changes", use_container_width=True, type="primary"):
                                st.session_state.translated_text = change['text_before_all']
                                # Remove all matching entries from undo stack
                                st.session_state.undo_stack = [
                                    e for i, e in enumerate(st.session_state.undo_stack)
                                    if i not in matching_undos
                                ]
                                st.session_state.highlight_change = None
                                st.session_state.word_alignment = None
                                st.toast(f"Reverted all {len(matching_undos)} replacements.")
                                st.rerun()
                    with col_undo_last:
                        if st.button("Undo Last", key="undo_last_change", use_container_width=True):
                            undo_entry = st.session_state.undo_stack.pop()
                            st.session_state.translated_text = undo_entry['text']
                            st.session_state.word_alignment = None
                            remaining = sum(
                                1 for e in st.session_state.undo_stack
                                if e.get('old_term') == change['old_term']
                            )
                            if remaining == 0:
                                st.session_state.highlight_change = None
                            else:
                                change['replaced_count'] = remaining
                            st.toast(f"Reverted: '{undo_entry['new_term']}' back to '{undo_entry['old_term']}'")
                            st.rerun()
                    with col_dismiss:
                        if st.button("OK", key="dismiss_highlight", use_container_width=True):
                            st.session_state.highlight_change = None
                            st.rerun()

        elif st.session_state.translated_text:
            # --- NORMAL MODE (editable) ---
            formatted_html = markdown_to_html(st.session_state.translated_text)
            # Render with inline editing support (double-click any word to edit)
            edit_result = clickable_text.render_editable_preview(
                html_content=formatted_html,
                key="english_preview"
            )

            # Process inline edit if user modified a word
            if edit_result and edit_result.get('action') == 'edit':
                edit_ts = edit_result.get('ts')
                if edit_ts != st.session_state.last_edit_ts:
                    st.session_state.last_edit_ts = edit_ts
                    old_word = edit_result['oldText']
                    new_word = edit_result['newText']
                    # Save undo state
                    st.session_state.undo_stack.append({
                        'text': st.session_state.translated_text,
                        'old_term': old_word,
                        'new_term': new_word,
                        'count': 1,
                    })
                    # Replace in translated text (first occurrence)
                    st.session_state.translated_text = st.session_state.translated_text.replace(
                        old_word, new_word, 1
                    )
                    st.session_state.word_alignment = None
                    st.session_state.highlight_change = {
                        'new_term': new_word,
                        'old_term': old_word,
                        'replaced_count': 1,
                    }
                    st.rerun()

            # Undo button (persistent, when there's history)
            if st.session_state.undo_stack:
                last_undo = st.session_state.undo_stack[-1]
                with st.expander(f"Last change: '{last_undo['old_term']}' -> '{last_undo['new_term']}'"):
                    col_undo_hist, col_spacer = st.columns([1, 2])
                    with col_undo_hist:
                        if st.button("Undo last change", key="undo_from_normal", use_container_width=True):
                            undo_entry = st.session_state.undo_stack.pop()
                            st.session_state.translated_text = undo_entry['text']
                            st.session_state.word_alignment = None
                            st.toast(f"Reverted: '{undo_entry['new_term']}' back to '{undo_entry['old_term']}'")
                            st.rerun()

            # Export buttons
            col_copy1, col_copy2, col_copy3 = st.columns([1, 1, 2])
            with col_copy1:
                if st.button("📋 Copy Text", use_container_width=True):
                    if copy_to_clipboard_with_formatting(st.session_state.translated_text):
                        st.success("Copied to clipboard!")
            with col_copy2:
                # Download as Word document
                output_filename = st.session_state.uploaded_file_name if st.session_state.uploaded_file_name else "translation.docx"
                word_file = export_word.export_to_word(
                    french_text=st.session_state.french_text,
                    english_text=st.session_state.translated_text
                )
                st.download_button(
                    label="\U0001f4c4 Download Word",
                    data=word_file,
                    file_name=output_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
        else:
            st.markdown(
                '<div class="translation-output"><em style="color: #888;">Your English translation will appear here after clicking Translate.</em></div>',
                unsafe_allow_html=True
            )

    st.divider()

    # Term-checking interface
    st.subheader("🔍 Terminology Checker")
    st.caption("Look up alternative translations using TERMIUM Plus, OQLF, or Canada.ca databases")

    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])

    with col1:
        # Pre-fill with selected term from clickable text if available
        default_term = st.session_state.get('selected_term', '')
        selected_text = st.text_input(
            "Enter term to check:",
            value=default_term,
            placeholder="Type or paste a term..."
        )

    with col2:
        termium_button = st.button("TERMIUM Plus", use_container_width=True)

    with col3:
        oqlf_button = st.button("OQLF", use_container_width=True)

    with col4:
        canada_button = st.button("Canada.ca", use_container_width=True)

    with col5:
        clear_button = st.button("Clear Results", use_container_width=True)

    # Handle manual term checking (submit to thread pool)
    if termium_button and selected_text:
        submit_search(selected_text, 'termium')
        st.session_state.selected_term = selected_text

    if oqlf_button and selected_text:
        submit_search(selected_text, 'oqlf')
        st.session_state.selected_term = selected_text

    if canada_button and selected_text:
        submit_search(selected_text, 'canada')
        st.session_state.selected_term = selected_text

    if clear_button:
        st.session_state.accumulated_results = []
        st.session_state.pending_futures = []
        st.session_state.selected_term = ""
        st.session_state.en_highlight_indices = []
        st.session_state.fr_highlight_indices = []
        st.rerun()

    # Check for completed background searches
    if st.session_state.pending_futures:
        still_pending = []
        for item in st.session_state.pending_futures:
            if item['future'].done():
                try:
                    results = item['future'].result()
                    append_search_results(item['term'], item['tool'], results)
                except Exception as e:
                    st.error(f"Error searching {item['tool']} for '{item['term']}': {e}")
            else:
                still_pending.append(item)

        st.session_state.pending_futures = still_pending

        if still_pending:
            pending_labels = [f"**{item['term']}** ({item['tool']})" for item in still_pending]
            st.info(f"Searching: {', '.join(pending_labels)}")

    # Display accumulated results grouped by term
    if st.session_state.accumulated_results:
        grouped = get_results_grouped_by_term()

        total_results = sum(len(sg['results']) for sg in st.session_state.accumulated_results)
        total_searches = len(st.session_state.accumulated_results)
        st.success(f"Found {total_results} result(s) across {total_searches} search(es)")

        for term_key, group_data in grouped.items():
            display_term = group_data['display_term']
            searches = group_data['searches']

            st.markdown(f"### {display_term}")

            for search_idx, search_group in enumerate(searches):
                tool_name = search_group['tool']
                results = search_group['results']

                if not results:
                    st.caption(f"_{tool_name}: No results found_")
                    continue

                st.caption(f"**{tool_name}** -- {len(results)} result(s)")

                for result_idx, result in enumerate(results):
                    unique_key = f"{term_key}_{search_idx}_{result_idx}"

                    with st.expander(
                        f"{result['english_term']}",
                        expanded=(search_idx == 0 and result_idx == 0)
                    ):
                        st.write(f"**Description:** {result.get('description', 'No description available')}")

                        if result.get('domain'):
                            st.write(f"**Domain:** {result['domain']}")

                        if result.get('source_url'):
                            st.markdown(f"[View source]({result['source_url']})")

                        # Action buttons
                        col_use, col_add = st.columns(2)

                        with col_use:
                            if st.button("Use this translation", key=f"use_{unique_key}", use_container_width=True):
                                if st.session_state.translated_text:
                                    # Find the English equivalent of the French term using AI
                                    with st.spinner(f"Finding '{display_term}' in translation..."):
                                        old_english = find_english_equivalent(display_term)

                                    if not old_english:
                                        st.warning(f"Could not find how '{display_term}' was translated.")
                                    else:
                                        occurrences = find_all_occurrences(
                                            st.session_state.translated_text, old_english
                                        )

                                        if len(occurrences) == 0:
                                            st.warning(f"'{old_english}' not found in translation.")
                                        elif len(occurrences) == 1:
                                            # Single occurrence: save undo state, replace, and highlight
                                            st.session_state.undo_stack.append({
                                                'text': st.session_state.translated_text,
                                                'old_term': old_english,
                                                'new_term': result['english_term'],
                                                'count': 1,
                                            })
                                            st.session_state.translated_text = apply_replacements(
                                                st.session_state.translated_text,
                                                occurrences, [True], result['english_term']
                                            )
                                            st.session_state.word_alignment = None
                                            st.session_state.highlight_change = {
                                                'new_term': result['english_term'],
                                                'old_term': old_english,
                                                'replaced_count': 1,
                                            }
                                            st.rerun()
                                        else:
                                            # Multiple occurrences: enter step-by-step mode
                                            st.session_state.replace_mode = True
                                            st.session_state.replace_data = {
                                                'french_term': display_term,
                                                'old_english': old_english,
                                                'new_english': result['english_term'],
                                                'total': len(occurrences),
                                                'current_idx': 0,
                                                'steps': [],
                                                'text_before_all': st.session_state.translated_text,
                                            }
                                            st.rerun()
                                else:
                                    st.warning("No translation available yet.")

                        with col_add:
                            if st.button("Add to Glossary", key=f"add_{unique_key}", use_container_width=True):
                                with st.spinner("Adding to glossary..."):
                                    try:
                                        success, message = add_to_glossary.add(
                                            french_term=display_term,
                                            english_term=result['english_term'],
                                            notes=f"Added from {tool_name}"
                                        )

                                        if success:
                                            st.success(message)

                                            log_action.log(
                                                french_term=display_term,
                                                english_term=result['english_term'],
                                                source=tool_name,
                                                added_to_glossary=True
                                            )

                                            st.session_state.glossary = fetch_glossary.fetch_glossary(force_refresh=True)
                                            st.session_state.glossary_loaded = True
                                            st.rerun()
                                        else:
                                            st.warning(message)

                                    except Exception as e:
                                        st.error(f"Failed to add to glossary: {e}")

            st.divider()

    # Sidebar with stats and info
    with st.sidebar:
        st.header("ℹ About")
        st.write("""
        **PSP Translator** helps translate French text to English following
        specific rules and using an approved glossary.

        **Features:**
        - ✅ Claude AI-powered translation
        - 📄 Word document upload support
        - 📚 Excel glossary integration (OneDrive)
        - 🔍 TERMIUM Plus & OQLF terminology lookup
        - 📝 Translation rule enforcement
        - 📊 Action logging for analysis
        """)

        st.divider()

        st.header("📊 Session Stats")

        if st.session_state.translation_history:
            st.metric("Translations", len(st.session_state.translation_history))

            total_cost = sum(item['cost'] for item in st.session_state.translation_history)
            st.metric("Total Cost", f"${total_cost:.4f}")

        if st.session_state.glossary_loaded:
            st.metric("Glossary Terms", len(st.session_state.glossary))

        st.divider()

        st.header("🔗 Quick Links")
        st.markdown("[TERMIUM Plus](https://www.btb.termiumplus.gc.ca/)")
        st.markdown("[OQLF Vitrine](https://vitrinelinguistique.oqlf.gouv.qc.ca/)")

    # Auto-rerun to poll for completed background searches
    # Placed at the end so the full page renders first
    if st.session_state.pending_futures:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
