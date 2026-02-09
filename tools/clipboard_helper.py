"""
Clipboard Helper for Reading Rich Text from Word

Reads HTML content from clipboard and converts to markdown.
"""

import re
from markdownify import markdownify as md


def get_html_from_clipboard():
    """
    Read HTML content from the Windows clipboard.

    Returns:
        tuple: (html_content, error_message) - html_content is str if successful, None otherwise
               error_message is str if there was an error, None otherwise
    """
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            # Try to get HTML format first
            html_format = win32clipboard.RegisterClipboardFormat("HTML Format")

            if win32clipboard.IsClipboardFormatAvailable(html_format):
                data = win32clipboard.GetClipboardData(html_format)

                # Windows clipboard HTML has metadata headers, extract just the HTML part
                if isinstance(data, bytes):
                    data = data.decode('utf-8', errors='ignore')

                # Extract HTML content between fragment markers
                # Windows HTML clipboard format includes metadata headers
                # We want only the actual content between StartFragment and EndFragment
                start_marker = '<!--StartFragment-->'
                end_marker = '<!--EndFragment-->'

                start_idx = data.find(start_marker)
                end_idx = data.find(end_marker)

                if start_idx != -1 and end_idx != -1:
                    # Extract only the fragment content
                    html_content = data[start_idx + len(start_marker):end_idx]
                    return html_content.strip(), None
                elif start_idx != -1:
                    # Has start marker but no end
                    html_content = data[start_idx + len(start_marker):]
                    return html_content.strip(), None
                else:
                    # No markers, try to find body content
                    body_start = data.find('<body')
                    if body_start != -1:
                        body_end = data.find('</body>')
                        if body_end != -1:
                            # Extract body tag and find its content
                            body_tag_end = data.find('>', body_start) + 1
                            html_content = data[body_tag_end:body_end]
                            return html_content.strip(), None

                    # Fallback: return all data
                    return data, None

            # If no HTML format, try plain text and inform user
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return None, "Only plain text found in clipboard. Copy from Word to preserve formatting."
            elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
                return None, "Only plain text found in clipboard. Copy from Word to preserve formatting."
            else:
                return None, "No text found in clipboard. Please copy text from Word first."

        finally:
            win32clipboard.CloseClipboard()

    except ImportError:
        return None, "win32clipboard module not available. Please install pywin32."
    except Exception as e:
        return None, f"Error reading clipboard: {str(e)}"


def html_to_markdown(html_content):
    """
    Convert HTML to markdown format.

    Args:
        html_content: HTML string to convert

    Returns:
        str: Markdown formatted text
    """
    if not html_content:
        return ""

    # Use markdownify library for conversion
    markdown = md(
        html_content,
        heading_style="ATX",
        bullets="-",
        strong_em_symbol="*",
        strip=['style', 'script']
    )

    # Clean up the output
    # Remove excessive blank lines
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)

    # Trim whitespace
    markdown = markdown.strip()

    return markdown


def paste_from_word():
    """
    Read formatted text from clipboard and convert to markdown.

    Returns:
        tuple: (markdown_text, error_message)
               - markdown_text is str if successful, None if failed
               - error_message is str if there was an error, None if successful
    """
    html_content, error = get_html_from_clipboard()

    if error:
        return None, error

    if html_content:
        markdown = html_to_markdown(html_content)
        if markdown:
            return markdown, None
        else:
            return None, "Failed to convert HTML to markdown."

    return None, "No formatted content found in clipboard."


if __name__ == "__main__":
    # Test the clipboard helper
    print("Testing clipboard helper...")
    print("Copy some formatted text from Word, then run this script.")
    print()

    result = paste_from_word()

    if result:
        print("✓ Successfully read formatted text from clipboard!")
        print("\nMarkdown output:")
        print("-" * 50)
        print(result)
        print("-" * 50)
    else:
        print("✗ No HTML content found in clipboard")
        print("Make sure to copy formatted text from Word first.")
