"""
PSP Translator - Flask Version (No WebSocket)

Replaces Streamlit with Flask + HTMX for environments that block WebSocket
(e.g., Canadian Forces DWAN network).
"""

import os
import re
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

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32).hex())

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
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


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

    return render_template('translator.html',
        glossary_count=len(glossary),
        glossary_stats=stats,
        french_text=session.get('french_text', ''),
        translated_text=session.get('translated_text', ''),
        translated_html=markdown_to_html(session.get('translated_text', '')) if session.get('translated_text') else '',
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

        # Store in session
        session['french_text'] = french_text
        session['translated_text'] = result['translated_text']

        # Log translation
        try:
            log_action.log_translation(glossary_used=result.get('glossary_used', False))
        except Exception:
            pass

        html_output = markdown_to_html(result['translated_text'])

        return render_template('_translation_result.html',
            html_output=html_output,
            raw_text=result['translated_text'],
            cost=result['cost'],
            input_tokens=result['input_tokens'],
            output_tokens=result['output_tokens'],
        )

    except Exception as e:
        return f'<div class="alert alert-danger">Translation failed: {html_module.escape(str(e))}</div>'


@app.route('/api/upload', methods=['POST'])
@require_auth
def api_upload():
    file = request.files.get('file')
    if not file or not file.filename.endswith('.docx'):
        return '<div class="alert alert-warning">Please upload a .docx file.</div>'

    try:
        file_bytes = BytesIO(file.read())
        extracted_text = parse_word.parse_word_document(file_bytes)
        file_bytes.seek(0)
        doc_info = parse_word.get_document_info(file_bytes)

        session['french_text'] = extracted_text

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
    french_text = session.get('french_text', '')
    translated_text = session.get('translated_text', '')

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
