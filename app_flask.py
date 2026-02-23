"""
PSP Translator - Flask Version (No WebSocket)

Replaces Streamlit with Flask + HTMX for environments that block WebSocket
(e.g., Canadian Forces DWAN network).
"""

import os
import re
import json
import base64
import html as html_module
from io import BytesIO
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_file, jsonify
)
from dotenv import load_dotenv

load_dotenv()

# Import backend tools (unchanged from Streamlit version)
from tools import translate_text, fetch_glossary, scrape_termium, scrape_oqlf, scrape_canada
from tools import log_action, add_to_glossary, parse_word, export_word
from tools import word_alignment

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'psp-translator-secret-key-2024')

# ---------------------------------------------------------------------------
# Server-side session data (avoids cookie size limit of 4KB)
# ---------------------------------------------------------------------------
SESSION_DATA_DIR = Path('.tmp/session_data')
SESSION_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_sid():
    """Get or create a session ID for server-side storage."""
    sid = session.get('_sid')
    if not sid:
        sid = os.urandom(16).hex()
        session['_sid'] = sid
    return sid


def store_data(**kwargs):
    """Store large data server-side (not in cookie)."""
    sid = _get_sid()
    filepath = SESSION_DATA_DIR / f"{sid}.json"
    existing = {}
    if filepath.exists():
        try:
            existing = json.loads(filepath.read_text(encoding='utf-8'))
        except Exception:
            pass
    existing.update(kwargs)
    filepath.write_text(json.dumps(existing, ensure_ascii=False), encoding='utf-8')


def get_data(key, default=None):
    """Retrieve server-side session data."""
    sid = session.get('_sid')
    if not sid:
        return default
    filepath = SESSION_DATA_DIR / f"{sid}.json"
    if not filepath.exists():
        return default
    try:
        data = json.loads(filepath.read_text(encoding='utf-8'))
        return data.get(key, default)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def markdown_to_html(text):
    """Convert markdown-like formatting to HTML."""
    text = html_module.escape(text)
    text = re.sub(r'==(#[A-Fa-f0-9]{6}):(.+?)==', r'<mark style="background-color: \1">\2</mark>', text)
    text = re.sub(r'==(.+?)==', r'<mark>\1</mark>', text)
    text = re.sub(r'::(#[A-Fa-f0-9]{6}):(.+?)::', r'<span style="color: \1">\2</span>', text)
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
    text = re.sub(r'\+\+(.+?)\+\+', r'<u>\1</u>', text)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    text = text.replace('\n', '<br>')
    return text


def require_auth(f):
    """Decorator to require authentication."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        app_password = os.environ.get('APP_PASSWORD')
        if app_password and not session.get('authenticated'):
            # API endpoints: never redirect, return proper errors
            if request.path.startswith('/api/'):
                if request.headers.get('HX-Request'):
                    return '<div class="alert alert-warning">Session expired. Please <a href="/" target="_top">log in again</a>.</div>', 401
                return jsonify({'error': 'Session expired. Please refresh the page and log in again.'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def find_all_occurrences(text, term):
    """Find all occurrences of a term using word-boundary matching.
    Returns list of (start, end) character positions."""
    pattern = r'(?<!\w)' + re.escape(term) + r'(?!\w)'
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    return [(m.start(), m.end()) for m in matches]


def _get_undo_info():
    """Get undo state for the client."""
    undo_stack = get_data('undo_stack', [])
    if not undo_stack:
        return {'has_undo': False}
    last = undo_stack[-1]
    return {
        'has_undo': True,
        'old_term': last.get('old_term', ''),
        'new_term': last.get('new_term', ''),
        'count': len(undo_stack),
    }


def _get_stats():
    """Get session stats."""
    return {
        'translation_count': get_data('translation_count', 0),
        'total_cost': get_data('total_cost', 0.0),
    }


def _generate_diff_html(old_text, new_text, old_term, new_term):
    """Generate before/after diff HTML snippet."""
    # Before snippet
    pattern_old = re.compile(r'(?<!\w)' + re.escape(old_term) + r'(?!\w)', re.IGNORECASE)
    m_old = pattern_old.search(old_text)
    before_snippet = ''
    if m_old:
        s = max(0, m_old.start() - 80)
        e = min(len(old_text), m_old.end() + 80)
        snippet = old_text[s:e]
        if s > 0: snippet = '...' + snippet
        if e < len(old_text): snippet = snippet + '...'
        before_snippet = pattern_old.sub(
            lambda m: f'<span class="diff-old">{html_module.escape(m.group())}</span>',
            html_module.escape(snippet)
        )

    # After snippet
    pattern_new = re.compile(r'(?<!\w)' + re.escape(new_term) + r'(?!\w)', re.IGNORECASE)
    m_new = pattern_new.search(new_text)
    after_snippet = ''
    if m_new:
        s = max(0, m_new.start() - 80)
        e = min(len(new_text), m_new.end() + 80)
        snippet = new_text[s:e]
        if s > 0: snippet = '...' + snippet
        if e < len(new_text): snippet = snippet + '...'
        after_snippet = pattern_new.sub(
            lambda m: f'<span class="diff-new">{html_module.escape(m.group())}</span>',
            html_module.escape(snippet)
        )

    return (
        '<details class="diff-viewer" open>'
        '<summary class="diff-viewer-header">Before / After</summary>'
        '<div class="diff-viewer-body">'
        '<div class="diff-col"><div class="diff-label">Before:</div>'
        f'<div class="diff-snippet">{before_snippet or "(preview not available)"}</div></div>'
        '<div class="diff-col"><div class="diff-label">After:</div>'
        f'<div class="diff-snippet">{after_snippet or "(preview not available)"}</div></div>'
        '</div></details>'
    )


def find_english_equivalent(french_term, french_text, translated_text, alignment_data):
    """Find the current English equivalent of a French term in the translated text.
    Uses word alignment first (fast), then falls back to Claude AI."""
    if not translated_text or not french_text:
        return None

    # Step 1: Try word alignment (fast, no API cost)
    if alignment_data and alignment_data.get('fr_to_en'):
        fr_words = alignment_data.get('fr_words', [])
        en_words = alignment_data.get('en_words', [])
        fr_to_en = alignment_data.get('fr_to_en', {})

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
                        en_indices.extend(fr_to_en.get(str(i + j), []))
                    en_indices = sorted(set(en_indices))
                    if en_indices:
                        candidate = ' '.join(en_words[idx] for idx in en_indices if idx < len(en_words))
                        pattern = r'(?<!\w)' + re.escape(candidate) + r'(?!\w)'
                        if re.search(pattern, translated_text, re.IGNORECASE):
                            return candidate

    # Step 2: Use Claude AI as fallback
    import anthropic
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        fr_excerpt = french_text[:3000]
        en_excerpt = translated_text[:3000]

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
        if candidate:
            pattern = r'(?<!\w)' + re.escape(candidate) + r'(?!\w)'
            m = re.search(pattern, translated_text, re.IGNORECASE)
            if m:
                return m.group(0)

    except Exception as e:
        print(f"[WARN] AI lookup for English equivalent failed: {e}")

    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    app_password = os.environ.get('APP_PASSWORD')
    if app_password and not session.get('authenticated'):
        return redirect(url_for('login_page'))
    return redirect(url_for('translate_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == os.environ.get('APP_PASSWORD', ''):
            session['authenticated'] = True
            return redirect(url_for('translate_page'))
        return render_template('login.html', error="Wrong password.")
    return render_template('login.html')


@app.route('/translate')
@require_auth
def translate_page():
    # Load glossary
    try:
        glossary = fetch_glossary.fetch_glossary()
        stats = fetch_glossary.get_glossary_stats()
    except Exception:
        glossary = {}
        stats = {'term_count': 0}

    # Load logo as base64
    logo_b64 = ''
    logo_path = Path('assets/psp_logo.png')
    if logo_path.exists():
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

    french_text = get_data('french_text', '')
    translated_text = get_data('translated_text', '')
    alignment_data = get_data('alignment')

    return render_template('translator.html',
        glossary_count=len(glossary),
        glossary_stats=stats,
        logo_b64=logo_b64,
        french_text=french_text,
        translated_text=translated_text,
        french_html=markdown_to_html(french_text) if french_text else '',
        translated_html=markdown_to_html(translated_text) if translated_text else '',
        undo_info=_get_undo_info(),
        stats=_get_stats(),
    )


# --- HTMX API endpoints (return HTML partials) ---

@app.route('/api/translate', methods=['POST'])
@require_auth
def api_translate():
    french_text = request.form.get('french_text', '').strip()
    if not french_text:
        return '<div class="alert alert-warning">Please enter French text to translate.</div>'

    try:
        glossary = fetch_glossary.fetch_glossary()
        result = translate_text.translate(
            french_text=french_text,
            glossary=glossary,
            rules_path="config/translation_rules.md"
        )

        # Store server-side (not in cookie) + reset undo stack for new translation
        translation_count = get_data('translation_count', 0) + 1
        total_cost = get_data('total_cost', 0.0) + result['cost']
        store_data(
            french_text=french_text,
            translated_text=result['translated_text'],
            undo_stack=[],
            replace_data=None,
            translation_count=translation_count,
            total_cost=total_cost,
        )

        # Generate word alignment
        alignment_data = None
        try:
            alignment = word_alignment.generate_alignment(french_text, result['translated_text'])
            if alignment:
                alignment_data = {
                    'fr_words': alignment.get('fr_words', []),
                    'en_words': alignment.get('en_words', []),
                    'fr_to_en': {str(k): v for k, v in alignment.get('fr_to_en', {}).items()},
                    'en_to_fr': {str(k): v for k, v in alignment.get('en_to_fr', {}).items()},
                }
                store_data(alignment=alignment_data)
        except Exception as e:
            print(f"Warning: Word alignment failed: {e}")

        # Log translation
        try:
            log_action.log_translation(glossary_used=result.get('glossary_used', False))
        except Exception:
            pass

        html_output = markdown_to_html(result['translated_text'])
        french_html = markdown_to_html(french_text)

        return render_template('_translation_result.html',
            html_output=html_output,
            french_html=french_html,
            raw_text=result['translated_text'],
            cost=result['cost'],
            input_tokens=result['input_tokens'],
            output_tokens=result['output_tokens'],
            stats=_get_stats(),
        )

    except Exception as e:
        return f'<div class="alert alert-danger">Translation failed: {html_module.escape(str(e))}</div>'


@app.route('/api/find-equivalent', methods=['POST'])
@require_auth
def api_find_equivalent():
    """Find the English equivalent of a French term WITHOUT replacing it."""
    french_term = request.form.get('french_term', '').strip()
    if not french_term:
        return jsonify({'success': False, 'message': 'Missing French term.'}), 400

    translated_text = get_data('translated_text', '')
    french_text = get_data('french_text', '')
    alignment_data = get_data('alignment')

    if not translated_text:
        return jsonify({'success': False, 'message': 'No translation available yet.'})

    old_english = find_english_equivalent(french_term, french_text, translated_text, alignment_data)
    if not old_english:
        return jsonify({'success': False, 'message': f"Could not find how '{french_term}' was translated."})

    # Count occurrences
    pattern = r'(?<!\w)' + re.escape(old_english) + r'(?!\w)'
    count = len(re.findall(pattern, translated_text, re.IGNORECASE))

    return jsonify({
        'success': True,
        'old_english': old_english,
        'count': count,
    })


@app.route('/api/use-translation', methods=['POST'])
@require_auth
def api_use_translation():
    french_term = request.form.get('french_term', '').strip()
    new_english = request.form.get('new_english', '').strip()
    old_english = request.form.get('old_english', '').strip()

    if not french_term or not new_english:
        return jsonify({'success': False, 'message': 'Missing parameters.'}), 400

    translated_text = get_data('translated_text', '')
    french_text = get_data('french_text', '')
    alignment_data = get_data('alignment')

    if not translated_text:
        return jsonify({'success': False, 'message': 'No translation available yet.'})

    # Use provided old_english or find it (fallback)
    if not old_english:
        old_english = find_english_equivalent(french_term, french_text, translated_text, alignment_data)
    if not old_english:
        return jsonify({'success': False, 'message': f"Could not find how '{french_term}' was translated."})

    # Replace in translated text (word-boundary matching)
    pattern = r'(?<!\w)' + re.escape(old_english) + r'(?!\w)'
    new_text, count = re.subn(pattern, new_english, translated_text, flags=re.IGNORECASE)

    if count == 0:
        return jsonify({'success': False, 'message': f"'{old_english}' not found in translation."})

    # Push to undo stack
    undo_stack = get_data('undo_stack', [])
    undo_stack.append({
        'text': translated_text,
        'old_term': old_english,
        'new_term': new_english,
        'count': count,
    })

    # Save updated translation + undo stack
    store_data(translated_text=new_text, alignment=None, undo_stack=undo_stack)

    # Generate diff HTML
    diff_html = _generate_diff_html(translated_text, new_text, old_english, new_english)

    return jsonify({
        'success': True,
        'message': f"Replaced '{old_english}' with '{new_english}' ({count} occurrence{'s' if count > 1 else ''}).",
        'old_english': old_english,
        'new_english': new_english,
        'count': count,
        'translated_html': markdown_to_html(new_text),
        'french_html': markdown_to_html(french_text),
        'undo_info': _get_undo_info(),
        'diff_html': diff_html,
    })


def _simple_replace(french_term, old_english, new_english, translated_text, french_text):
    """Fallback: simple regex replacement without AI context adaptation."""
    pattern = re.compile(r'(?<!\w)' + re.escape(old_english) + r'(?!\w)', re.IGNORECASE)

    applied_changes = []

    def do_replace(m):
        matched = m.group(0)
        replacement = new_english
        # Match capitalization
        if matched[0].isupper() and not new_english[0].isupper():
            replacement = new_english[0].upper() + new_english[1:]
        applied_changes.append({'old': matched, 'new': replacement})
        return replacement

    new_text = pattern.sub(do_replace, translated_text)

    if not applied_changes:
        return jsonify({'success': False, 'message': f"'{old_english}' not found in translation."})

    undo_stack = get_data('undo_stack', [])
    undo_stack.append({
        'text': translated_text,
        'old_term': old_english,
        'new_term': new_english,
        'count': len(applied_changes),
    })
    store_data(translated_text=new_text, alignment=None, undo_stack=undo_stack)

    new_terms = list(dict.fromkeys(c['new'] for c in applied_changes))

    return jsonify({
        'success': True,
        'old_english': old_english,
        'new_english': new_english,
        'changes': applied_changes,
        'count': len(applied_changes),
        'new_terms': new_terms,
        'translated_html': markdown_to_html(new_text),
        'french_html': markdown_to_html(french_text),
        'undo_info': _get_undo_info(),
    })


@app.route('/api/smart-replace', methods=['POST'])
@require_auth
def api_smart_replace():
    """Use Claude AI to intelligently replace a term, adapting each occurrence
    to its grammatical context (plural, capitalization, verb forms, etc.)."""
    french_term = request.form.get('french_term', '').strip()
    new_english = request.form.get('new_english', '').strip()

    if not french_term or not new_english:
        return jsonify({'success': False, 'message': 'Missing parameters.'}), 400

    translated_text = get_data('translated_text', '')
    french_text = get_data('french_text', '')
    alignment_data = get_data('alignment')

    if not translated_text:
        return jsonify({'success': False, 'message': 'No translation available yet.'})

    # Step 1: Find the current English equivalent of the French term
    old_english = find_english_equivalent(french_term, french_text, translated_text, alignment_data)
    if not old_english:
        return jsonify({'success': False, 'message': f"Could not find how '{french_term}' was translated."})

    # Step 2: Use Claude AI to find all occurrences and adapt replacements
    import anthropic
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return _simple_replace(french_term, old_english, new_english, translated_text, french_text)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            temperature=0,
            messages=[{
                "role": "user",
                "content": (
                    f'In the English text below, the word "{old_english}" translates the French '
                    f'term "{french_term}". I need to replace ALL occurrences of "{old_english}" '
                    f'(and any grammatical variants: plural, possessive, capitalized, -ing, -ed, '
                    f'-er, -tion forms, etc.) with the appropriate form of "{new_english}".\n\n'
                    f'For each occurrence found, provide:\n'
                    f'- "find": the EXACT text as it appears in the document\n'
                    f'- "replace": the grammatically correct replacement using "{new_english}"\n'
                    f'- "context": ~8 words surrounding the occurrence for reference\n\n'
                    f'Rules:\n'
                    f'- Match capitalization (if original starts uppercase, replacement should too)\n'
                    f'- Match number (singular/plural)\n'
                    f'- Match verb tense if applicable\n'
                    f'- Ensure the replacement reads naturally in context\n'
                    f'- Only include forms semantically related to "{old_english}" as a '
                    f'translation of "{french_term}" (don\'t match unrelated homonyms)\n\n'
                    f'Reply with ONLY a valid JSON array:\n'
                    f'[{{"find": "exact text", "replace": "adapted replacement", '
                    f'"context": "surrounding words"}}]\n\n'
                    f'If nothing found, return: []\n\n'
                    f'ENGLISH TEXT:\n{translated_text}'
                )
            }]
        )

        response_text = message.content[0].text.strip()
        # Handle potential markdown code block wrapping
        if response_text.startswith('```'):
            response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
            response_text = re.sub(r'\n?```\s*$', '', response_text)

        pairs = json.loads(response_text)

        if not pairs:
            return jsonify({'success': False, 'message': f"No occurrences of '{old_english}' found in translation."})

        # Step 3: Verify each "find" actually exists in the text
        verified_pairs = []
        for pair in pairs:
            find_text = pair.get('find', '')
            if not find_text:
                continue
            pattern = r'(?<!\w)' + re.escape(find_text) + r'(?!\w)'
            if re.search(pattern, translated_text, re.IGNORECASE):
                verified_pairs.append(pair)

        if not verified_pairs:
            return _simple_replace(french_term, old_english, new_english, translated_text, french_text)

        # Step 4: Branch based on count
        if len(verified_pairs) == 1:
            # Single occurrence: apply directly
            pair = verified_pairs[0]
            pattern = re.compile(r'(?<!\w)' + re.escape(pair['find']) + r'(?!\w)', re.IGNORECASE)
            applied_changes = []

            def do_single(m):
                applied_changes.append({'old': m.group(0), 'new': pair['replace']})
                return pair['replace']

            new_text = pattern.sub(do_single, translated_text, count=1)

            if not applied_changes:
                return jsonify({'success': False, 'message': 'Replacement failed.'})

            undo_stack = get_data('undo_stack', [])
            undo_stack.append({
                'text': translated_text,
                'old_term': old_english,
                'new_term': new_english,
                'count': 1,
            })
            store_data(translated_text=new_text, alignment=None, undo_stack=undo_stack)

            return jsonify({
                'success': True,
                'mode': 'direct',
                'old_english': old_english,
                'new_english': new_english,
                'changes': applied_changes,
                'count': 1,
                'new_terms': [pair['replace']],
                'translated_html': markdown_to_html(new_text),
                'french_html': markdown_to_html(french_text),
                'undo_info': _get_undo_info(),
            })
        else:
            # Multiple occurrences: step-by-step mode
            # Store the plan in session, don't apply yet
            smart_replace_data = {
                'french_term': french_term,
                'old_english': old_english,
                'new_english': new_english,
                'occurrences': verified_pairs,
                'current_idx': 0,
                'steps': [],
                'text_before_all': translated_text,
            }
            store_data(smart_replace_data=smart_replace_data)

            return jsonify({
                'success': True,
                'mode': 'step_by_step',
                'old_english': old_english,
                'new_english': new_english,
                'total': len(verified_pairs),
                'occurrences': [
                    {'find': p['find'], 'replace': p['replace'], 'context': p.get('context', '')}
                    for p in verified_pairs
                ],
            })

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[WARN] Smart replace JSON parse failed: {e}")
        return _simple_replace(french_term, old_english, new_english, translated_text, french_text)
    except Exception as e:
        print(f"[WARN] Smart replace failed: {e}")
        return _simple_replace(french_term, old_english, new_english, translated_text, french_text)


@app.route('/api/smart-replace-step', methods=['POST'])
@require_auth
def api_smart_replace_step():
    """Process one step of the smart replacement (accept/skip/undo)."""
    action = request.form.get('action', '').strip()

    srd = get_data('smart_replace_data')
    if not srd:
        return jsonify({'success': False, 'message': 'No smart replacement in progress.'})

    translated_text = get_data('translated_text', '')
    french_text = get_data('french_text', '')
    occurrences = srd['occurrences']
    steps = srd['steps']
    current_idx = srd['current_idx']
    total = len(occurrences)

    if action == 'undo':
        if not steps:
            return jsonify({'success': False, 'message': 'Nothing to undo.'})
        last_step = steps.pop()
        if last_step['action'] == 'accept':
            translated_text = last_step['text_before']
            store_data(translated_text=translated_text, alignment=None)
        srd['current_idx'] -= 1
        srd['steps'] = steps
        store_data(smart_replace_data=srd)

        # Return info for next UI render
        new_idx = srd['current_idx']
        occ = occurrences[new_idx] if new_idx < total else None
        return jsonify({
            'success': True,
            'action': 'undo',
            'current_idx': new_idx,
            'total': total,
            'occurrence': occ,
            'translated_html': markdown_to_html(translated_text),
        })

    if action == 'accept':
        if current_idx >= total:
            return jsonify({'success': False, 'message': 'All occurrences already processed.'})

        occ = occurrences[current_idx]
        find_text = occ['find']
        replace_text = request.form.get('replace_text', '').strip() or occ['replace']

        # Find and replace this specific occurrence
        pattern = re.compile(r'(?<!\w)' + re.escape(find_text) + r'(?!\w)', re.IGNORECASE)
        # Count how many previous accepts targeted this same find_text (to skip already-replaced ones)
        skip_count = sum(1 for s in steps if s['action'] == 'skip' and s.get('find_text', '').lower() == find_text.lower())

        match_positions = list(pattern.finditer(translated_text))
        target_idx = skip_count  # The Nth remaining match
        if target_idx < len(match_positions):
            m = match_positions[target_idx]
            text_before = translated_text
            translated_text = translated_text[:m.start()] + replace_text + translated_text[m.end():]

            steps.append({
                'action': 'accept',
                'find_text': find_text,
                'replace_text': replace_text,
                'text_before': text_before,
            })
            store_data(translated_text=translated_text, alignment=None)
        else:
            # Fallback: just do first match
            text_before = translated_text
            translated_text = pattern.sub(replace_text, translated_text, count=1)
            steps.append({
                'action': 'accept',
                'find_text': find_text,
                'replace_text': replace_text,
                'text_before': text_before,
            })
            store_data(translated_text=translated_text, alignment=None)

        srd['current_idx'] = current_idx + 1
        srd['steps'] = steps
        store_data(smart_replace_data=srd)

    elif action == 'skip':
        if current_idx >= total:
            return jsonify({'success': False, 'message': 'All occurrences already processed.'})

        occ = occurrences[current_idx]
        steps.append({
            'action': 'skip',
            'find_text': occ['find'],
        })
        srd['current_idx'] = current_idx + 1
        srd['steps'] = steps
        store_data(smart_replace_data=srd)

    # Check if finished
    new_idx = srd['current_idx']
    finished = new_idx >= total

    response = {
        'success': True,
        'action': action,
        'current_idx': new_idx,
        'total': total,
        'translated_html': markdown_to_html(translated_text),
        'finished': finished,
    }

    if not finished:
        response['occurrence'] = occurrences[new_idx]

    if finished:
        # Collect results
        accepted = [s for s in steps if s['action'] == 'accept']
        accepted_count = len(accepted)

        if accepted_count > 0:
            # Push a single undo entry for all accepted changes
            undo_stack = get_data('undo_stack', [])
            undo_stack.append({
                'text': srd['text_before_all'],
                'old_term': srd['old_english'],
                'new_term': srd['new_english'],
                'count': accepted_count,
            })
            store_data(undo_stack=undo_stack)

        # Collect applied changes for the changes log
        applied_changes = [
            {'old': s['find_text'], 'new': s['replace_text']}
            for s in accepted
        ]
        new_terms = list(dict.fromkeys(s['replace_text'] for s in accepted))

        response['accepted_count'] = accepted_count
        response['skipped_count'] = len([s for s in steps if s['action'] == 'skip'])
        response['changes'] = applied_changes
        response['new_terms'] = new_terms
        response['old_english'] = srd['old_english']
        response['new_english'] = srd['new_english']
        response['french_term'] = srd['french_term']
        response['undo_info'] = _get_undo_info()

        # Clear smart replace data
        store_data(smart_replace_data=None)

    return jsonify(response)


@app.route('/api/smart-replace-cancel', methods=['POST'])
@require_auth
def api_smart_replace_cancel():
    """Cancel smart step-by-step replacement, revert all changes."""
    srd = get_data('smart_replace_data')
    if not srd:
        return jsonify({'success': False, 'message': 'No smart replacement in progress.'})

    original_text = srd['text_before_all']
    french_text = get_data('french_text', '')
    store_data(translated_text=original_text, smart_replace_data=None, alignment=None)

    return jsonify({
        'success': True,
        'translated_html': markdown_to_html(original_text),
    })


@app.route('/api/upload', methods=['POST'])
@require_auth
def api_upload():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'No file uploaded.'}), 400
    if not file.filename.lower().endswith('.docx'):
        return jsonify({'error': 'Please upload a .docx file.'}), 400

    try:
        file_bytes = BytesIO(file.read())
        extracted_text = parse_word.parse_word_document(file_bytes)
        file_bytes.seek(0)
        doc_info = parse_word.get_document_info(file_bytes)

        # Store server-side (not in cookie)
        store_data(french_text=extracted_text)

        return jsonify({
            'text': extracted_text,
            'words': doc_info['word_count'],
            'paragraphs': doc_info['paragraph_count'],
            'filename': file.filename,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/search', methods=['POST'])
@require_auth
def api_search():
    term = request.form.get('term', '').strip()
    tool = request.form.get('tool', '')

    if not term:
        return '<div class="alert alert-warning">Please enter a term.</div>'

    try:
        if tool == 'termium':
            results = scrape_termium.scrape(term)
            tool_name = 'TERMIUM Plus'
        elif tool == 'oqlf':
            results = scrape_oqlf.scrape(term)
            tool_name = 'OQLF'
        elif tool == 'canada':
            results = scrape_canada.scrape(term)
            tool_name = 'Canada.ca'
        else:
            return '<div class="alert alert-warning">Unknown tool.</div>'

        return render_template('_search_results.html',
            term=term,
            tool_name=tool_name,
            results=results,
        )

    except Exception as e:
        return f'<div class="alert alert-danger">Search failed: {html_module.escape(str(e))}</div>'


@app.route('/api/glossary/add', methods=['POST'])
@require_auth
def api_glossary_add():
    french_term = request.form.get('french_term', '').strip()
    english_term = request.form.get('english_term', '').strip()
    notes = request.form.get('notes', '').strip()

    if not french_term or not english_term:
        return '<div class="alert alert-warning">Both terms are required.</div>'

    try:
        success, message = add_to_glossary.add(
            french_term=french_term,
            english_term=english_term,
            notes=notes,
        )
        if success:
            return f'<div class="alert alert-success">{html_module.escape(message)}</div>'
        else:
            return f'<div class="alert alert-warning">{html_module.escape(message)}</div>'
    except Exception as e:
        return f'<div class="alert alert-danger">Error: {html_module.escape(str(e))}</div>'


@app.route('/api/stats', methods=['GET'])
@require_auth
def api_stats():
    stats = _get_stats()
    glossary = fetch_glossary.fetch_glossary()
    return jsonify({
        'translation_count': stats['translation_count'],
        'total_cost': stats['total_cost'],
        'glossary_count': len(glossary),
    })


@app.route('/api/glossary/refresh', methods=['POST'])
@require_auth
def api_glossary_refresh():
    try:
        glossary = fetch_glossary.fetch_glossary(force_refresh=True)
        return f'<div class="alert alert-success">Glossary refreshed: {len(glossary)} terms loaded.</div>'
    except Exception as e:
        return f'<div class="alert alert-danger">Refresh failed: {html_module.escape(str(e))}</div>'


@app.route('/api/download', methods=['GET'])
@require_auth
def api_download():
    french_text = get_data('french_text', '')
    translated_text = get_data('translated_text', '')

    if not translated_text:
        return redirect(url_for('translate_page'))

    word_file = export_word.export_to_word(
        french_text=french_text,
        english_text=translated_text,
    )

    return send_file(
        BytesIO(word_file) if isinstance(word_file, bytes) else word_file,
        as_attachment=True,
        download_name='translation.docx',
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )


@app.route('/api/edit-word', methods=['POST'])
@require_auth
def api_edit_word():
    """Persist inline word edit (double-click) and push to undo stack."""
    old_text = request.form.get('old_text', '').strip()
    new_text = request.form.get('new_text', '').strip()

    if not old_text or not new_text or old_text == new_text:
        return jsonify({'success': False, 'message': 'No change to apply.'})

    translated_text = get_data('translated_text', '')
    if not translated_text:
        return jsonify({'success': False, 'message': 'No translation available.'})

    # Push undo
    undo_stack = get_data('undo_stack', [])
    undo_stack.append({
        'text': translated_text,
        'old_term': old_text,
        'new_term': new_text,
        'count': 1,
    })

    # Replace first occurrence
    updated = translated_text.replace(old_text, new_text, 1)
    store_data(translated_text=updated, alignment=None, undo_stack=undo_stack)

    return jsonify({
        'success': True,
        'translated_html': markdown_to_html(updated),
        'undo_info': _get_undo_info(),
    })


@app.route('/api/undo', methods=['POST'])
@require_auth
def api_undo():
    """Pop the last change from undo stack and restore previous text."""
    undo_stack = get_data('undo_stack', [])
    if not undo_stack:
        return jsonify({'success': False, 'message': 'Nothing to undo.'})

    entry = undo_stack.pop()
    store_data(translated_text=entry['text'], alignment=None, undo_stack=undo_stack)

    return jsonify({
        'success': True,
        'translated_html': markdown_to_html(entry['text']),
        'undo_info': _get_undo_info(),
        'reverted_old': entry.get('old_term', ''),
        'reverted_new': entry.get('new_term', ''),
    })


@app.route('/api/replace-init', methods=['POST'])
@require_auth
def api_replace_init():
    """Initialize step-by-step replacement mode."""
    french_term = request.form.get('french_term', '').strip()
    old_english = request.form.get('old_english', '').strip()
    new_english = request.form.get('new_english', '').strip()

    if not old_english or not new_english:
        return jsonify({'success': False, 'message': 'Missing parameters.'})

    translated_text = get_data('translated_text', '')
    occurrences = find_all_occurrences(translated_text, old_english)

    if not occurrences:
        return jsonify({'success': False, 'message': f"'{old_english}' not found in translation."})

    # Store replacement state server-side
    replace_data = {
        'french_term': french_term,
        'old_english': old_english,
        'new_english': new_english,
        'total': len(occurrences),
        'current_idx': 0,
        'steps': [],
        'text_before_all': translated_text,
    }
    store_data(replace_data=replace_data)

    return jsonify({
        'success': True,
        'total': len(occurrences),
        'old_english': old_english,
        'new_english': new_english,
    })


@app.route('/api/replace-step', methods=['POST'])
@require_auth
def api_replace_step():
    """Process one step of the replacement (replace/skip/undo)."""
    action = request.form.get('action', '').strip()
    effective_term = request.form.get('effective_term', '').strip()

    replace_data = get_data('replace_data')
    if not replace_data:
        return jsonify({'success': False, 'message': 'No replacement in progress.'})

    translated_text = get_data('translated_text', '')
    old_english = replace_data['old_english']
    new_english = replace_data['new_english']
    steps = replace_data['steps']
    total = replace_data['total']

    if action == 'undo':
        if not steps:
            return jsonify({'success': False, 'message': 'Nothing to undo.'})
        last_step = steps.pop()
        translated_text = last_step['text_before']
        replace_data['current_idx'] -= 1
        store_data(translated_text=translated_text, replace_data=replace_data, alignment=None)

        return jsonify({
            'success': True,
            'translated_html': markdown_to_html(translated_text),
            'undone_action': last_step['action'],
        })

    if action == 'replace':
        term_to_use = effective_term or new_english
        # Find remaining occurrences and replace the first one
        skipped = sum(1 for s in steps if s['action'] == 'skip')
        occurrences = find_all_occurrences(translated_text, old_english)
        idx = min(skipped, len(occurrences) - 1) if occurrences else 0

        steps.append({
            'action': 'replace',
            'text_before': translated_text,
            'used_term': term_to_use,
        })

        if occurrences and idx < len(occurrences):
            start, end = occurrences[idx]
            translated_text = translated_text[:start] + term_to_use + translated_text[end:]

        replace_data['current_idx'] += 1
        store_data(translated_text=translated_text, replace_data=replace_data, alignment=None)

    elif action == 'skip':
        steps.append({
            'action': 'skip',
            'text_before': translated_text,
        })
        replace_data['current_idx'] += 1
        store_data(replace_data=replace_data)

    # Check if we're done
    finished = replace_data['current_idx'] >= total

    response = {
        'success': True,
        'translated_html': markdown_to_html(translated_text),
        'finished': finished,
    }

    if finished:
        # Finish replacement mode
        replace_steps = [s for s in steps if s['action'] == 'replace']
        replaced_count = len(replace_steps)

        # Push undo entries
        undo_stack = get_data('undo_stack', [])
        for step in reversed(replace_steps):
            used_term = step.get('used_term', new_english)
            undo_stack.append({
                'text': step['text_before'],
                'old_term': old_english,
                'new_term': used_term,
                'count': 1,
            })
        store_data(undo_stack=undo_stack, replace_data=None)

        # Collect unique terms used
        used_terms = list(dict.fromkeys(
            s.get('used_term', new_english) for s in replace_steps
        ))

        response['replaced_count'] = replaced_count
        response['message'] = f"Replaced {replaced_count} of {total} occurrences of '{old_english}'."
        response['new_terms'] = used_terms
        response['undo_info'] = _get_undo_info()

        # Generate diff
        if replaced_count > 0:
            response['diff_html'] = _generate_diff_html(
                replace_data['text_before_all'], translated_text,
                old_english, used_terms[0]
            )

    return jsonify(response)


@app.route('/api/replace-cancel', methods=['POST'])
@require_auth
def api_replace_cancel():
    """Cancel step-by-step replacement and restore original text."""
    replace_data = get_data('replace_data')
    if not replace_data:
        return jsonify({'success': False, 'message': 'No replacement in progress.'})

    original_text = replace_data['text_before_all']
    store_data(translated_text=original_text, replace_data=None, alignment=None)

    return jsonify({
        'success': True,
        'translated_html': markdown_to_html(original_text),
    })


@app.route('/health')
def health():
    return 'ok'


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8501, debug=False)
