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
        alignment_json=json.dumps(alignment_data) if alignment_data else 'null',
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

        # Store server-side (not in cookie)
        store_data(french_text=french_text, translated_text=result['translated_text'])

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
            alignment_json=json.dumps(alignment_data) if alignment_data else 'null',
        )

    except Exception as e:
        return f'<div class="alert alert-danger">Translation failed: {html_module.escape(str(e))}</div>'


@app.route('/api/use-translation', methods=['POST'])
@require_auth
def api_use_translation():
    french_term = request.form.get('french_term', '').strip()
    new_english = request.form.get('new_english', '').strip()

    if not french_term or not new_english:
        return jsonify({'success': False, 'message': 'Missing parameters.'}), 400

    translated_text = get_data('translated_text', '')
    french_text = get_data('french_text', '')
    alignment_data = get_data('alignment')

    if not translated_text:
        return jsonify({'success': False, 'message': 'No translation available yet.'})

    # Find current English equivalent
    old_english = find_english_equivalent(french_term, french_text, translated_text, alignment_data)
    if not old_english:
        return jsonify({'success': False, 'message': f"Could not find how '{french_term}' was translated."})

    # Replace in translated text (word-boundary matching)
    pattern = r'(?<!\w)' + re.escape(old_english) + r'(?!\w)'
    new_text, count = re.subn(pattern, new_english, translated_text, flags=re.IGNORECASE)

    if count == 0:
        return jsonify({'success': False, 'message': f"'{old_english}' not found in translation."})

    # Save updated translation
    store_data(translated_text=new_text, alignment=None)

    return jsonify({
        'success': True,
        'message': f"Replaced '{old_english}' with '{new_english}' ({count} occurrence{'s' if count > 1 else ''}).",
        'old_english': old_english,
        'new_english': new_english,
        'count': count,
        'translated_html': markdown_to_html(new_text),
        'french_html': markdown_to_html(french_text),
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


@app.route('/health')
def health():
    return 'ok'


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8501, debug=False)
