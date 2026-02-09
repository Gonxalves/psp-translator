"""
Clickable Text Component for Streamlit

Renders formatted text with clickable words that show a context menu
for terminology lookup. Uses a proper Streamlit bi-directional component
to communicate selections back to the app.
"""

import streamlit as st
import streamlit.components.v1 as components
import json
from pathlib import Path


# Declare the bi-directional clickable text component
_COMPONENT_DIR = Path(__file__).parent / "clickable_text_component"
_clickable_component = components.declare_component("clickable_text", path=str(_COMPONENT_DIR))


def render_clickable(html_content: str, key: str, highlight_indices: list = None, height: int = 750):
    """
    Render text with clickable words and context menu.

    When user clicks words and selects a tool, the component returns a dict
    with the selected term, tool, and word indices.

    Args:
        html_content: HTML content to display (from markdown_to_html())
        key: Unique key for this component instance
        highlight_indices: List of word indices to highlight initially
        height: Height of the component in pixels

    Returns:
        dict or None: If user selected a tool, returns:
            {'term': str, 'tool': str, 'indices': str, 'ts': int}
            Otherwise returns None.
    """
    result = _clickable_component(
        html_content=html_content,
        highlight_indices=highlight_indices or [],
        key=key,
        height=height,
        default=None
    )
    return result


def render_editable_preview(html_content: str, key: str, highlight_indices: list = None, height: int = 750):
    """
    Render English text with inline editing support.
    Double-click any word to edit it directly in the text.
    Select multiple words (Shift+click) then double-click to edit a phrase.

    Returns:
        dict or None: If user edited a word, returns:
            {'action': 'edit', 'oldText': str, 'newText': str, 'wordIndex': int, 'ts': int}
            Otherwise returns None.
    """
    result = _clickable_component(
        html_content=html_content,
        highlight_indices=highlight_indices or [],
        editable=True,
        key=key,
        height=height,
        default=None
    )
    return result


def render_with_highlights(html_content: str, highlight_indices: list, key: str, height: int = 750):
    """
    Render text with highlighted words (read-only, for English side).

    Args:
        html_content: HTML content to display
        highlight_indices: List of word indices to highlight
        key: Unique key for this component
        height: Height of the component in pixels
    """

    highlight_json = json.dumps(highlight_indices or [])

    html_code = f"""
    <style>
        .highlight-container {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 12pt;
            line-height: 1.6;
            padding: 15px;
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            min-height: 100px;
        }}

        .highlight-word {{
            padding: 1px 2px;
            border-radius: 2px;
        }}

        .highlight-word.synced {{
            background-color: #c8e6c9;
            box-shadow: 0 0 0 1px #4caf50;
        }}
    </style>

    <div id="highlight-{key}" class="highlight-container">
    </div>

    <script>
        (function() {{
            const container = document.getElementById('highlight-{key}');
            const highlightIndices = {highlight_json};

            function wrapWords(html) {{
                const temp = document.createElement('div');
                temp.innerHTML = html;

                let wordIndex = 0;

                function processNode(node) {{
                    if (node.nodeType === Node.TEXT_NODE) {{
                        const text = node.textContent;
                        if (!text.trim()) return node;

                        const parts = text.split(/(\\s+)/);
                        const fragment = document.createDocumentFragment();

                        parts.forEach(part => {{
                            if (/^\\s+$/.test(part)) {{
                                fragment.appendChild(document.createTextNode(part));
                            }} else if (part.length > 0) {{
                                const span = document.createElement('span');
                                span.className = 'highlight-word';
                                if (highlightIndices.includes(wordIndex)) {{
                                    span.classList.add('synced');
                                }}
                                span.textContent = part;
                                fragment.appendChild(span);
                                wordIndex++;
                            }}
                        }});

                        return fragment;
                    }} else if (node.nodeType === Node.ELEMENT_NODE) {{
                        const children = Array.from(node.childNodes);
                        children.forEach(child => {{
                            const processed = processNode(child);
                            if (processed !== child) {{
                                node.replaceChild(processed, child);
                            }}
                        }});
                        return node;
                    }}
                    return node;
                }}

                processNode(temp);
                return temp.innerHTML;
            }}

            const originalHtml = `{html_content.replace('`', '\\`').replace('${', '\\${')}`;
            container.innerHTML = wrapWords(originalHtml);

            // Auto-resize iframe to fit content
            function resizeFrame() {{
                const h = document.documentElement.scrollHeight;
                window.parent.postMessage({{type: 'streamlit:setFrameHeight', height: h}}, '*');
            }}
            resizeFrame();
            new ResizeObserver(resizeFrame).observe(container);
        }})();
    </script>
    """

    components.html(html_code, height=height, scrolling=True)


def render_replacement_highlight(html_content: str, target_term: str, occurrence_idx: int, total_occurrences: int, key: str, height: int = 750):
    """
    Render text with a specific occurrence of a term highlighted in orange for replacement.
    Auto-scrolls to the highlighted occurrence.

    Args:
        html_content: HTML content to display (from markdown_to_html())
        target_term: The term to find and highlight (e.g., "program")
        occurrence_idx: Which occurrence to highlight (0-based)
        total_occurrences: Total number of occurrences (for display)
        key: Unique key for this component
        height: Height of the component in pixels
    """

    target_json = json.dumps(target_term.lower())
    target_words = target_term.lower().split()
    target_words_json = json.dumps(target_words)

    html_code = f"""
    <style>
        .replace-container {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 12pt;
            line-height: 1.6;
            padding: 15px;
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            min-height: 100px;
        }}

        .replace-word {{
            padding: 1px 2px;
            border-radius: 2px;
        }}

        .replace-word.target {{
            background-color: #FF9800;
            box-shadow: 0 0 0 2px #E65100;
            color: #000;
            animation: pulse-orange 1.5s ease-in-out infinite;
        }}

        @keyframes pulse-orange {{
            0%, 100% {{ box-shadow: 0 0 0 2px #E65100; }}
            50% {{ box-shadow: 0 0 8px 3px #FF9800; }}
        }}
    </style>

    <div id="replace-{key}" class="replace-container">
    </div>

    <script>
        (function() {{
            const container = document.getElementById('replace-{key}');
            const targetWords = {target_words_json};
            const occurrenceIdx = {occurrence_idx};

            // Strip punctuation from edges for matching
            function cleanWord(w) {{
                return w.replace(/^[^\\w]+/, '').replace(/[^\\w]+$/, '').toLowerCase();
            }}

            function wrapWords(html) {{
                const temp = document.createElement('div');
                temp.innerHTML = html;
                let wordIndex = 0;

                function processNode(node) {{
                    if (node.nodeType === Node.TEXT_NODE) {{
                        const text = node.textContent;
                        if (!text.trim()) return node;

                        const parts = text.split(/(\\s+)/);
                        const fragment = document.createDocumentFragment();

                        parts.forEach(part => {{
                            if (/^\\s+$/.test(part)) {{
                                fragment.appendChild(document.createTextNode(part));
                            }} else if (part.length > 0) {{
                                const span = document.createElement('span');
                                span.className = 'replace-word';
                                span.dataset.wordIndex = wordIndex;
                                span.textContent = part;
                                fragment.appendChild(span);
                                wordIndex++;
                            }}
                        }});

                        return fragment;
                    }} else if (node.nodeType === Node.ELEMENT_NODE) {{
                        const children = Array.from(node.childNodes);
                        children.forEach(child => {{
                            const processed = processNode(child);
                            if (processed !== child) {{
                                node.replaceChild(processed, child);
                            }}
                        }});
                        return node;
                    }}
                    return node;
                }}

                processNode(temp);
                return temp.innerHTML;
            }}

            const originalHtml = `{html_content.replace('`', '\\`').replace('${', '\\${')}`;
            container.innerHTML = wrapWords(originalHtml);

            // Find and highlight the Nth occurrence of the target term
            const allWords = container.querySelectorAll('.replace-word');
            const wordTexts = Array.from(allWords).map(w => cleanWord(w.textContent));
            let matchCount = 0;

            for (let i = 0; i <= wordTexts.length - targetWords.length; i++) {{
                // Check if consecutive words match the target phrase
                let match = true;
                for (let j = 0; j < targetWords.length; j++) {{
                    if (wordTexts[i + j] !== targetWords[j]) {{
                        match = false;
                        break;
                    }}
                }}

                if (match) {{
                    if (matchCount === occurrenceIdx) {{
                        // Highlight this occurrence
                        for (let j = 0; j < targetWords.length; j++) {{
                            allWords[i + j].classList.add('target');
                        }}
                        // Auto-scroll to the first word of the match
                        setTimeout(() => {{
                            allWords[i].scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}, 100);
                        break;
                    }}
                    matchCount++;
                }}
            }}

            // Auto-resize iframe
            function resizeFrame() {{
                const h = document.documentElement.scrollHeight;
                window.parent.postMessage({{type: 'streamlit:setFrameHeight', height: h}}, '*');
            }}
            resizeFrame();
            new ResizeObserver(resizeFrame).observe(container);
        }})();
    </script>
    """

    components.html(html_code, height=height, scrolling=True)


def render_change_highlight(html_content: str, target_term: str, key: str, height: int = 750):
    """
    Render text with all occurrences of a newly-replaced term highlighted in green
    with zoom-in animation and auto-scroll. Used after a replacement is applied
    to show the user exactly what changed.

    Args:
        html_content: HTML content to display (from markdown_to_html())
        target_term: The new term that was just inserted
        key: Unique key for this component
        height: Height of the component in pixels
    """

    target_words = target_term.lower().split()
    target_words_json = json.dumps(target_words)

    html_code = f"""
    <style>
        .change-container {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 12pt;
            line-height: 1.6;
            padding: 15px;
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            min-height: 100px;
        }}

        .change-word {{
            padding: 1px 2px;
            border-radius: 2px;
            transition: all 0.3s ease;
        }}

        .change-word.changed {{
            background-color: #A5D6A7;
            box-shadow: 0 0 0 2px #2E7D32;
            color: #000;
            font-weight: bold;
            animation: zoom-pulse 2s ease-in-out;
            position: relative;
            z-index: 1;
        }}

        @keyframes zoom-pulse {{
            0% {{ transform: scale(1); box-shadow: 0 0 0 2px #2E7D32; }}
            15% {{ transform: scale(1.35); box-shadow: 0 0 12px 4px #66BB6A; }}
            40% {{ transform: scale(1.2); box-shadow: 0 0 8px 3px #66BB6A; }}
            70% {{ transform: scale(1.1); box-shadow: 0 0 4px 2px #43A047; }}
            100% {{ transform: scale(1); box-shadow: 0 0 0 2px #2E7D32; }}
        }}
    </style>

    <div id="change-{key}" class="change-container">
    </div>

    <script>
        (function() {{
            const container = document.getElementById('change-{key}');
            const targetWords = {target_words_json};

            function cleanWord(w) {{
                return w.replace(/^[^\\w]+/, '').replace(/[^\\w]+$/, '').toLowerCase();
            }}

            function wrapWords(html) {{
                const temp = document.createElement('div');
                temp.innerHTML = html;
                let wordIndex = 0;

                function processNode(node) {{
                    if (node.nodeType === Node.TEXT_NODE) {{
                        const text = node.textContent;
                        if (!text.trim()) return node;

                        const parts = text.split(/(\\s+)/);
                        const fragment = document.createDocumentFragment();

                        parts.forEach(part => {{
                            if (/^\\s+$/.test(part)) {{
                                fragment.appendChild(document.createTextNode(part));
                            }} else if (part.length > 0) {{
                                const span = document.createElement('span');
                                span.className = 'change-word';
                                span.dataset.wordIndex = wordIndex;
                                span.textContent = part;
                                fragment.appendChild(span);
                                wordIndex++;
                            }}
                        }});

                        return fragment;
                    }} else if (node.nodeType === Node.ELEMENT_NODE) {{
                        const children = Array.from(node.childNodes);
                        children.forEach(child => {{
                            const processed = processNode(child);
                            if (processed !== child) {{
                                node.replaceChild(processed, child);
                            }}
                        }});
                        return node;
                    }}
                    return node;
                }}

                processNode(temp);
                return temp.innerHTML;
            }}

            const originalHtml = `{html_content.replace('`', '\\`').replace('${', '\\${')}`;
            container.innerHTML = wrapWords(originalHtml);

            // Find ALL occurrences of the target term and highlight them
            const allWords = container.querySelectorAll('.change-word');
            const wordTexts = Array.from(allWords).map(w => cleanWord(w.textContent));
            let firstMatch = null;

            for (let i = 0; i <= wordTexts.length - targetWords.length; i++) {{
                let match = true;
                for (let j = 0; j < targetWords.length; j++) {{
                    if (wordTexts[i + j] !== targetWords[j]) {{
                        match = false;
                        break;
                    }}
                }}

                if (match) {{
                    for (let j = 0; j < targetWords.length; j++) {{
                        allWords[i + j].classList.add('changed');
                    }}
                    if (!firstMatch) firstMatch = allWords[i];
                }}
            }}

            // Auto-scroll to the first highlighted match
            if (firstMatch) {{
                setTimeout(() => {{
                    firstMatch.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}, 200);
            }}

            // Auto-resize iframe
            function resizeFrame() {{
                const h = document.documentElement.scrollHeight;
                window.parent.postMessage({{type: 'streamlit:setFrameHeight', height: h}}, '*');
            }}
            resizeFrame();
            new ResizeObserver(resizeFrame).observe(container);
        }})();
    </script>
    """

    components.html(html_code, height=height, scrolling=True)


def render_change_highlight_multi(html_content: str, target_terms: list, key: str, height: int = 750):
    """
    Render text highlighting multiple different replacement terms in green.
    Used when the user manually edited different occurrences to different values.
    """

    all_targets = [term.lower().split() for term in target_terms]
    all_targets_json = json.dumps(all_targets)

    html_code = f"""
    <style>
        .mchange-container {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 12pt;
            line-height: 1.6;
            padding: 15px;
            background-color: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            min-height: 100px;
        }}
        .mchange-word {{
            padding: 1px 2px;
            border-radius: 2px;
            transition: all 0.3s ease;
        }}
        .mchange-word.changed {{
            background-color: #A5D6A7;
            box-shadow: 0 0 0 2px #2E7D32;
            color: #000;
            font-weight: bold;
            animation: mzoom-pulse 2s ease-in-out;
            position: relative;
            z-index: 1;
        }}
        @keyframes mzoom-pulse {{
            0% {{ transform: scale(1); box-shadow: 0 0 0 2px #2E7D32; }}
            15% {{ transform: scale(1.35); box-shadow: 0 0 12px 4px #66BB6A; }}
            40% {{ transform: scale(1.2); box-shadow: 0 0 8px 3px #66BB6A; }}
            70% {{ transform: scale(1.1); box-shadow: 0 0 4px 2px #43A047; }}
            100% {{ transform: scale(1); box-shadow: 0 0 0 2px #2E7D32; }}
        }}
    </style>
    <div id="mchange-{key}" class="mchange-container"></div>
    <script>
        (function() {{
            const container = document.getElementById('mchange-{key}');
            const allTargets = {all_targets_json};

            function cleanWord(w) {{
                return w.replace(/^[^\\w]+/, '').replace(/[^\\w]+$/, '').toLowerCase();
            }}

            function wrapWords(html) {{
                const temp = document.createElement('div');
                temp.innerHTML = html;
                let wordIndex = 0;
                function processNode(node) {{
                    if (node.nodeType === Node.TEXT_NODE) {{
                        const text = node.textContent;
                        if (!text.trim()) return node;
                        const parts = text.split(/(\\s+)/);
                        const fragment = document.createDocumentFragment();
                        parts.forEach(part => {{
                            if (/^\\s+$/.test(part)) {{
                                fragment.appendChild(document.createTextNode(part));
                            }} else if (part.length > 0) {{
                                const span = document.createElement('span');
                                span.className = 'mchange-word';
                                span.dataset.wordIndex = wordIndex;
                                span.textContent = part;
                                fragment.appendChild(span);
                                wordIndex++;
                            }}
                        }});
                        return fragment;
                    }} else if (node.nodeType === Node.ELEMENT_NODE) {{
                        const children = Array.from(node.childNodes);
                        children.forEach(child => {{
                            const processed = processNode(child);
                            if (processed !== child) {{
                                node.replaceChild(processed, child);
                            }}
                        }});
                        return node;
                    }}
                    return node;
                }}
                processNode(temp);
                return temp.innerHTML;
            }}

            const originalHtml = `{html_content.replace('`', '\\`').replace('${', '\\${')}`;
            container.innerHTML = wrapWords(originalHtml);

            const allWords = container.querySelectorAll('.mchange-word');
            const wordTexts = Array.from(allWords).map(w => cleanWord(w.textContent));
            let firstMatch = null;

            for (const targetWords of allTargets) {{
                for (let i = 0; i <= wordTexts.length - targetWords.length; i++) {{
                    let match = true;
                    for (let j = 0; j < targetWords.length; j++) {{
                        if (wordTexts[i + j] !== targetWords[j]) {{
                            match = false;
                            break;
                        }}
                    }}
                    if (match) {{
                        for (let j = 0; j < targetWords.length; j++) {{
                            allWords[i + j].classList.add('changed');
                        }}
                        if (!firstMatch) firstMatch = allWords[i];
                    }}
                }}
            }}

            if (firstMatch) {{
                setTimeout(() => {{
                    firstMatch.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}, 200);
            }}

            function resizeFrame() {{
                const h = document.documentElement.scrollHeight;
                window.parent.postMessage({{type: 'streamlit:setFrameHeight', height: h}}, '*');
            }}
            resizeFrame();
            new ResizeObserver(resizeFrame).observe(container);
        }})();
    </script>
    """

    components.html(html_code, height=height, scrolling=True)
