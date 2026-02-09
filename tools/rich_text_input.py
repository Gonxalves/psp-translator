"""
Rich Text Input Component for Streamlit

Provides a text input that preserves formatting from Word by converting HTML to markdown.
"""

import streamlit as st
import streamlit.components.v1 as components


def rich_text_area(label, height=400, key=None, placeholder="", value=""):
    """
    Create a rich text area that preserves formatting from Word pastes.

    When users paste from Word, the HTML formatting is automatically converted
    to markdown syntax (bold, italic, spacing) that Claude can preserve during
    translation.

    Args:
        label: Label for the text area
        height: Height of the text area in pixels
        key: Unique key for the component
        placeholder: Placeholder text
        value: Default value

    Returns:
        The text content with markdown formatting
    """

    # Create a unique key for this component
    component_key = key or "rich_text_input"

    # HTML/JavaScript component that handles rich text paste
    html_code = f"""
    <style>
        #editor-container {{
            width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            font-family: monospace;
        }}
        #editor {{
            width: 100%;
            height: {height}px;
            padding: 10px;
            border: none;
            outline: none;
            resize: vertical;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.5;
        }}
        #editor:focus {{
            outline: 2px solid #0066ff;
            outline-offset: -2px;
        }}
        .format-hint {{
            font-size: 11px;
            color: #666;
            padding: 4px 10px;
            background: #f8f9fa;
            border-top: 1px solid #ddd;
        }}
    </style>

    <div id="editor-container">
        <textarea id="editor" placeholder="{placeholder}">{value}</textarea>
        <div class="format-hint">
            💡 Paste from Word preserves <strong>bold</strong> and <em>italic</em> formatting
        </div>
    </div>

    <script>
        const editor = document.getElementById('editor');

        // Convert HTML to Markdown
        function htmlToMarkdown(html) {{
            // Create a temporary div to parse HTML
            const temp = document.createElement('div');
            temp.innerHTML = html;

            // Convert basic formatting
            let markdown = temp.innerHTML;

            // Bold: <b>, <strong> → **text**
            markdown = markdown.replace(/<(b|strong)>(.*?)<\/(b|strong)>/gi, '**$2**');

            // Italic: <i>, <em> → *text*
            markdown = markdown.replace(/<(i|em)>(.*?)<\/(i|em)>/gi, '*$2*');

            // Underline: keep as is or convert to bold
            markdown = markdown.replace(/<u>(.*?)<\/u>/gi, '**$1**');

            // Remove spans but keep content
            markdown = markdown.replace(/<span[^>]*>(.*?)<\/span>/gi, '$1');

            // Paragraphs: <p> → double newline
            markdown = markdown.replace(/<p[^>]*>/gi, '\\n\\n');
            markdown = markdown.replace(/<\/p>/gi, '');

            // Line breaks: <br> → newline
            markdown = markdown.replace(/<br[^>]*>/gi, '\\n');

            // Lists: <ul><li> → - item
            markdown = markdown.replace(/<ul[^>]*>/gi, '');
            markdown = markdown.replace(/<\/ul>/gi, '\\n');
            markdown = markdown.replace(/<li[^>]*>/gi, '- ');
            markdown = markdown.replace(/<\/li>/gi, '\\n');

            // Remove remaining HTML tags
            markdown = markdown.replace(/<[^>]+>/g, '');

            // Decode HTML entities
            const txt = document.createElement('textarea');
            txt.innerHTML = markdown;
            markdown = txt.value;

            // Clean up extra whitespace
            markdown = markdown.replace(/\\n{{3,}}/g, '\\n\\n');
            markdown = markdown.trim();

            return markdown;
        }}

        // Handle paste events
        editor.addEventListener('paste', (e) => {{
            e.preventDefault();

            // Get clipboard data
            const clipboardData = e.clipboardData || window.clipboardData;

            // Try to get HTML first (from Word/rich text editors)
            const htmlData = clipboardData.getData('text/html');

            if (htmlData) {{
                // Convert HTML to markdown
                const markdown = htmlToMarkdown(htmlData);

                // Insert at cursor position
                const start = editor.selectionStart;
                const end = editor.selectionEnd;
                const text = editor.value;

                editor.value = text.substring(0, start) + markdown + text.substring(end);

                // Set cursor position after inserted text
                const newPos = start + markdown.length;
                editor.selectionStart = newPos;
                editor.selectionEnd = newPos;
            }} else {{
                // Fallback to plain text
                const plainText = clipboardData.getData('text/plain');
                document.execCommand('insertText', false, plainText);
            }}

            // Trigger input event to notify Streamlit
            editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }});

        // Send content to Streamlit on every change
        editor.addEventListener('input', () => {{
            // Use Streamlit's setComponentValue to send data back
            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: editor.value
            }}, '*');
        }});

        // Also send initial value
        window.parent.postMessage({{
            type: 'streamlit:setComponentValue',
            value: editor.value
        }}, '*');

        // Set component ready
        window.parent.postMessage({{
            type: 'streamlit:componentReady'
        }}, '*');
    </script>
    """

    # Render the component
    result = components.html(
        html_code,
        height=height + 60,  # Add space for hint
        scrolling=True
    )

    # Store in session state
    if result is not None:
        st.session_state[f"{component_key}_value"] = result

    # Return current value from session state or default
    return st.session_state.get(f"{component_key}_value", value)
