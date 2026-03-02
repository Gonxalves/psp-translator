/* ============================================================
   PSP Translator - JavaScript (all client-side logic)
   ============================================================ */

// ==========================================
// Client-side markdown to HTML
// ==========================================
function markdownToHtml(text) {
    text = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    text = text.replace(/==(#[A-Fa-f0-9]{6}):(.+?)==/g, '<mark style="background-color: $1">$2</mark>');
    text = text.replace(/==(.+?)==/g, '<mark>$1</mark>');
    text = text.replace(/::(#[A-Fa-f0-9]{6}):(.+?)::/g, '<span style="color: $1">$2</span>');
    text = text.replace(/~~(.+?)~~/g, '<del>$1</del>');
    text = text.replace(/\+\+(.+?)\+\+/g, '<u>$1</u>');
    text = text.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
    text = text.replace(/\n/g, '<br>');
    return text;
}

// ==========================================
// Utility functions
// ==========================================
function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ==========================================
// Live French preview (updates as user types)
// ==========================================
var livePreviewActive = true;
var previewTimeout = null;

function updateFrenchPreview() {
    if (!livePreviewActive) return;
    var textarea = document.getElementById('french_text');
    var preview = document.getElementById('french-preview');
    if (!textarea || !preview) return;

    var text = textarea.value;
    if (text.trim()) {
        preview.innerHTML = markdownToHtml(text);
        setupFrenchClickHandlers();
    } else {
        preview.innerHTML = '<span class="empty-output">French preview will appear here.</span>';
    }
}

// ==========================================
// DOM-based word wrapping (preserves HTML formatting)
// ==========================================
function wrapWords(container, className) {
    if (!container) return;

    function processNode(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            var text = node.textContent;
            if (!text.trim()) return;

            var parts = text.split(/(\s+)/);
            var fragment = document.createDocumentFragment();

            parts.forEach(function(part) {
                if (/^\s+$/.test(part)) {
                    fragment.appendChild(document.createTextNode(part));
                } else if (part.length > 0) {
                    var span = document.createElement('span');
                    span.className = className;
                    span.textContent = part;
                    fragment.appendChild(span);
                }
            });

            node.parentNode.replaceChild(fragment, node);
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            var children = Array.from(node.childNodes);
            children.forEach(processNode);
        }
    }

    processNode(container);
}

// ==========================================
// French word click handlers (supports Ctrl+Click for multi-word selection)
// ==========================================
function cleanPunctuation(text) {
    // Strip leading/trailing punctuation (keep accented chars, hyphens inside words)
    return text.replace(/^[^\w\u00C0-\u024F]+|[^\w\u00C0-\u024F]+$/g, '');
}

function setupFrenchClickHandlers() {
    var frPanel = document.getElementById('french-preview');
    if (!frPanel || !frPanel.textContent.trim() || frPanel.querySelector('.empty-output')) return;

    // Wrap words if not already wrapped
    if (!frPanel.querySelector('.clickable-word')) {
        wrapWords(frPanel, 'clickable-word');
    }

    var frWords = frPanel.querySelectorAll('.clickable-word');
    frWords.forEach(function(span) {
        if (span.dataset.clickBound) return;
        span.dataset.clickBound = '1';

        span.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            // Always use the span text, ignore browser selection
            var word = cleanPunctuation(span.textContent.trim());
            if (!word) return;

            var searchInput = document.getElementById('search-term');

            if (e.ctrlKey || e.metaKey) {
                // Ctrl+Click: add word to existing selection
                span.classList.add('highlighted');
                var existing = searchInput.value.trim();
                if (existing) {
                    searchInput.value = existing + ' ' + word;
                } else {
                    searchInput.value = word;
                }
            } else {
                // Normal click: replace selection with single word
                frWords.forEach(function(w) { w.classList.remove('highlighted'); });
                span.classList.add('highlighted');
                searchInput.value = word;
            }

            // Clear any browser text selection caused by ctrl+click
            window.getSelection().removeAllRanges();

            // Show context menu with the full (possibly multi-word) term
            showContextMenu(e.clientX, e.clientY, searchInput.value.trim());
        });
    });
}

// ==========================================
// Initialize interactive previews (after translation)
// ==========================================
function initInteractivePreviews() {
    var frPanel = document.getElementById('french-preview');
    var enPanel = document.getElementById('english-preview');
    if (!frPanel || !enPanel) return;
    if (!frPanel.textContent.trim() || frPanel.querySelector('.empty-output')) return;

    // Disable live preview - we now have interactive mode
    livePreviewActive = false;

    // Setup French click handlers
    setupFrenchClickHandlers();

    // Wrap English words if not already wrapped
    if (!enPanel.querySelector('.editable-word')) {
        wrapWords(enPanel, 'editable-word');
    }

    var enWords = enPanel.querySelectorAll('.editable-word');

    // English word double-click to edit
    enWords.forEach(function(span) {
        if (span.dataset.editBound) return;
        span.dataset.editBound = '1';

        span.addEventListener('dblclick', function handleDblClick(e) {
            e.preventDefault();
            var oldText = span.textContent;
            var input = document.createElement('input');
            input.type = 'text';
            input.value = oldText;
            input.style.cssText = 'font-family:Times New Roman;font-size:12pt;border:1px solid #3b82f6;border-radius:3px;padding:1px 4px;width:' + Math.max(60, oldText.length * 10) + 'px;';
            span.replaceWith(input);
            input.focus();
            input.select();

            function finishEdit() {
                var newText = input.value.trim() || oldText;
                var newSpan = document.createElement('span');
                newSpan.className = 'editable-word';
                newSpan.textContent = newText;
                newSpan.dataset.editBound = '1';
                if (newText !== oldText) {
                    newSpan.style.background = '#bbf7d0';
                    // Persist edit to server
                    persistEdit(oldText, newText);
                }
                input.replaceWith(newSpan);
                newSpan.addEventListener('dblclick', handleDblClick);
            }
            input.addEventListener('blur', finishEdit);
            input.addEventListener('keydown', function(ev) {
                if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); }
                if (ev.key === 'Escape') { input.value = oldText; input.blur(); }
            });
        });
    });
}

// ==========================================
// Persist inline edit to server
// ==========================================
async function persistEdit(oldText, newText) {
    try {
        var formData = new FormData();
        formData.append('old_text', oldText);
        formData.append('new_text', newText);
        var resp = await fetch('/api/edit-word', { method: 'POST', body: formData });
        var data = await resp.json();
        if (data.success) {
            // Update undo bar
            updateUndoBar(data.undo_info);
            // Update English preview with server-side rendered HTML
            if (data.translated_html) {
                var enPreview = document.getElementById('english-preview');
                if (enPreview) {
                    enPreview.innerHTML = data.translated_html;
                    wrapWords(enPreview, 'editable-word');
                    initInteractivePreviews();
                }
            }
            updateSidebarStats();
        }
    } catch (err) {
        console.error('Edit persist failed:', err);
    }
}

// ==========================================
// Context menu
// ==========================================
var menuTerm = '';
var toolNames = { 'termium': 'TERMIUM Plus', 'oqlf': 'OQLF', 'canada': 'Canada.ca' };

function showContextMenu(x, y, term) {
    menuTerm = term;
    var menu = document.getElementById('ctx-menu');
    document.getElementById('ctx-menu-term').textContent = '"' + term + '"';
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
    menu.style.display = 'block';
}

document.addEventListener('click', function() {
    document.getElementById('ctx-menu').style.display = 'none';
});

function searchFromMenu(tool) {
    document.getElementById('ctx-menu').style.display = 'none';
    if (!menuTerm) return;
    document.getElementById('search-term').value = menuTerm;
    searchTool(tool, toolNames[tool] || tool);
}

// ==========================================
// Search tool with status bars
// ==========================================
async function searchTool(tool, toolName) {
    var term = document.getElementById('search-term').value.trim();
    if (!term) {
        document.getElementById('search-status').innerHTML = '<div class="alert alert-warning">Please enter a term to search.</div>';
        setTimeout(function() { document.getElementById('search-status').innerHTML = ''; }, 3000);
        return;
    }

    var statusEl = document.getElementById('search-status');
    var statusId = 'status-' + tool + '-' + Date.now();

    // Show blue loading bar
    statusEl.insertAdjacentHTML('beforeend',
        '<div class="search-status-item status-loading" id="' + statusId + '">' +
        '<span class="spinner" style="width:14px;height:14px;"></span> ' +
        'Searching ' + escapeHtml(toolName) + ' for "' + escapeHtml(term) + '"...</div>');

    try {
        var formData = new FormData();
        formData.append('term', term);
        formData.append('tool', tool);

        var resp = await fetch('/api/search', { method: 'POST', body: formData });
        var html = await resp.text();

        // Append results
        var resultsEl = document.getElementById('search-results');
        resultsEl.insertAdjacentHTML('beforeend', html);

        // Process HTMX elements in new content
        if (window.htmx) htmx.process(resultsEl.lastElementChild);

        // Change status to green
        var statusItem = document.getElementById(statusId);
        if (statusItem) {
            statusItem.className = 'search-status-item status-done';
            statusItem.innerHTML = toolName + ' — "' + escapeHtml(term) + '" — done';
            setTimeout(function() { if (statusItem.parentNode) statusItem.remove(); }, 10000);
        }

        // Auto-scroll to results
        var lastResult = resultsEl.lastElementChild;
        if (lastResult) lastResult.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    } catch (err) {
        var statusItem = document.getElementById(statusId);
        if (statusItem) {
            statusItem.className = 'search-status-item status-error';
            statusItem.innerHTML = toolName + ' — Error: ' + escapeHtml(err.message);
        }
    }
}

function clearSearchResults() {
    document.getElementById('search-results').innerHTML = '';
    document.getElementById('search-status').innerHTML = '';
}

// ==========================================
// File upload
// ==========================================
function initFileUpload() {
    var uploadInput = document.getElementById('wordUpload');
    if (!uploadInput) return;
    uploadInput.addEventListener('change', async function(e) {
        var file = e.target.files[0];
        if (!file) return;
        var status = document.getElementById('upload-status');
        status.textContent = 'Extracting text...';
        var formData = new FormData();
        formData.append('file', file);
        try {
            var resp = await fetch('/api/upload', { method: 'POST', body: formData });
            var contentType = resp.headers.get('content-type') || '';
            if (!contentType.includes('application/json')) {
                if (resp.status === 401 || resp.redirected) {
                    status.textContent = 'Session expired. Please refresh the page and log in again.';
                } else {
                    status.textContent = 'Upload failed: server returned unexpected response (status ' + resp.status + ')';
                }
                return;
            }
            var data = await resp.json();
            if (data.error) { status.textContent = 'Error: ' + data.error; return; }
            document.getElementById('french_text').value = data.text;
            status.textContent = 'Extracted from "' + data.filename + '" (' + data.words + ' words, ' + data.paragraphs + ' paragraphs)';
            livePreviewActive = true;
            updateFrenchPreview();
        } catch (err) { status.textContent = 'Upload failed: ' + err.message; }
    });
}

// ==========================================
// Highlight helpers
// ==========================================
function highlightWordsInPreview(previewEl, term, className) {
    var words = previewEl.querySelectorAll('.editable-word');
    var termWords = term.toLowerCase().split(/\s+/);
    if (termWords.length === 0) return;

    for (var i = 0; i <= words.length - termWords.length; i++) {
        var match = true;
        for (var j = 0; j < termWords.length; j++) {
            var wordText = words[i + j].textContent.toLowerCase().replace(/^[^\w\u00C0-\u024F]+|[^\w\u00C0-\u024F]+$/g, '');
            if (wordText !== termWords[j]) { match = false; break; }
        }
        if (match) {
            for (var j = 0; j < termWords.length; j++) {
                words[i + j].classList.add(className);
            }
        }
    }
}

function clearHighlights(className) {
    var enPreview = document.getElementById('english-preview');
    if (!enPreview) return;
    enPreview.querySelectorAll('.' + className).forEach(function(el) {
        el.classList.remove(className);
    });
}

// ==========================================
// Changes log panel (persistent per session)
// ==========================================
var changesLog = [];

function renderChangesPanel() {
    var panel = document.getElementById('changes-panel');
    if (!panel) return;

    if (changesLog.length === 0) {
        panel.className = 'changes-panel';
        panel.innerHTML = '';
        return;
    }

    panel.className = 'changes-panel visible';

    var html = '<div class="changes-panel-header" onclick="toggleChangesPanel()">'
        + '<span>&#128221; Term Corrections (' + changesLog.length + ')</span>'
        + '<span class="changes-chevron" id="changes-chevron">&#9660;</span>'
        + '</div>'
        + '<div class="changes-panel-body" id="changes-panel-body">';

    // Most recent first
    for (var i = changesLog.length - 1; i >= 0; i--) {
        var entry = changesLog[i];
        var isLatest = (i === changesLog.length - 1);

        html += '<div class="change-entry' + (isLatest ? ' change-latest' : '') + '">'
            + '<div class="change-entry-header">'
            + '<div class="change-terms">'
            + '<span class="change-fr">' + escapeHtml(entry.french_term) + '</span>'
            + ' <span class="change-arrow">&rarr;</span> '
            + '<strong class="change-new">' + escapeHtml(entry.new_english) + '</strong>'
            + ' <span class="change-was">(was: ' + escapeHtml(entry.old_english) + ')</span>'
            + '</div>'
            + '<div class="change-actions">'
            + '<span class="change-count">' + entry.count + ' correction' + (entry.count > 1 ? 's' : '') + '</span>';

        if (isLatest) {
            html += ' <button class="btn btn-sm btn-outline" onclick="undoFromPanel()">Undo</button>';
        }

        html += '</div></div>';

        // Show individual changes
        if (entry.changes && entry.changes.length > 0) {
            html += '<div class="change-details">';
            for (var j = 0; j < entry.changes.length; j++) {
                var change = entry.changes[j];
                html += '<div class="change-detail-item">'
                    + '<span class="change-old-text">' + escapeHtml(change.old) + '</span>'
                    + ' &rarr; '
                    + '<span class="change-new-text">' + escapeHtml(change['new']) + '</span>'
                    + '</div>';
            }
            html += '</div>';
        }

        html += '</div>';
    }

    html += '</div>';
    panel.innerHTML = html;
}

function toggleChangesPanel() {
    var body = document.getElementById('changes-panel-body');
    var chevron = document.getElementById('changes-chevron');
    if (!body) return;

    if (body.style.display === 'none') {
        body.style.display = 'block';
        if (chevron) chevron.innerHTML = '&#9660;';
    } else {
        body.style.display = 'none';
        if (chevron) chevron.innerHTML = '&#9654;';
    }
}

async function undoFromPanel() {
    try {
        var resp = await fetch('/api/undo', { method: 'POST' });
        var data = await resp.json();

        if (data.success) {
            var enPreview = document.getElementById('english-preview');
            if (enPreview && data.translated_html) {
                enPreview.innerHTML = data.translated_html;
                wrapWords(enPreview, 'editable-word');
                initInteractivePreviews();
            }

            // Remove last entry from changes log
            changesLog.pop();
            renderChangesPanel();

            updateUndoBar(data.undo_info);
            updateSidebarStats();

            showToast('Reverted: "' + data.reverted_new + '" back to "' + data.reverted_old + '"', 'success');
        }
    } catch (err) {
        console.error('Undo from panel failed:', err);
    }
}

// ==========================================
// Use this translation (AI-powered smart replace)
// ==========================================
var smartStepState = null;

async function useThisTranslation(frenchTerm, newEnglish) {
    var msgEl = document.getElementById('glossary-add-msg');
    msgEl.innerHTML = '<div class="alert alert-info">'
        + '<span class="spinner" style="vertical-align:middle;margin-right:8px;"></span> '
        + 'AI is analyzing "<strong>' + escapeHtml(frenchTerm) + '</strong>" in translation...'
        + '</div>';

    // Scroll to the English preview so user sees the action
    var enPreview = document.getElementById('english-preview');
    if (enPreview) enPreview.scrollIntoView({ behavior: 'smooth', block: 'center' });

    try {
        var formData = new FormData();
        formData.append('french_term', frenchTerm);
        formData.append('new_english', newEnglish);

        var resp = await fetch('/api/smart-replace', { method: 'POST', body: formData });
        var data = await resp.json();

        if (!data.success) {
            msgEl.innerHTML = '<div class="alert alert-warning">' + escapeHtml(data.message) + '</div>';
            setTimeout(function() { msgEl.innerHTML = ''; }, 5000);
            return;
        }

        if (data.mode === 'step_by_step') {
            // Multiple occurrences: enter step-by-step mode
            smartStepState = {
                frenchTerm: frenchTerm,
                oldEnglish: data.old_english,
                newEnglish: newEnglish,
                total: data.total,
                currentIdx: 0,
                occurrences: data.occurrences,
                acceptedCount: 0,
                skippedCount: 0,
            };
            msgEl.innerHTML = '';
            renderSmartStepUI();
            return;
        }

        // Direct mode (single occurrence): apply immediately
        if (enPreview && data.translated_html) {
            enPreview.innerHTML = data.translated_html;
            wrapWords(enPreview, 'editable-word');
        }

        // Highlight new terms
        clearHighlights('highlight-correction');
        if (data.new_terms && enPreview) {
            data.new_terms.forEach(function(term) {
                highlightWordsInPreview(enPreview, term, 'highlight-correction');
            });
        }

        var firstHL = enPreview ? enPreview.querySelector('.highlight-correction') : null;
        if (firstHL) firstHL.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Add to changes log
        changesLog.push({
            french_term: frenchTerm,
            old_english: data.old_english,
            new_english: newEnglish,
            changes: data.changes || [],
            count: data.count,
        });
        renderChangesPanel();

        var summary = '1 correction applied: "' + data.changes[0].old + '" \u2192 "' + data.changes[0]['new'] + '"';
        msgEl.innerHTML = '<div class="alert alert-success">' + escapeHtml(summary) + '</div>';

        initInteractivePreviews();
        updateUndoBar(data.undo_info);
        updateSidebarStats();

        setTimeout(function() {
            clearHighlights('highlight-correction');
            msgEl.innerHTML = '';
        }, 8000);

    } catch (err) {
        msgEl.innerHTML = '<div class="alert alert-danger">Error: ' + escapeHtml(err.message) + '</div>';
    }
}

// ==========================================
// Smart step-by-step UI (in changes panel)
// ==========================================
function renderSmartStepUI() {
    if (!smartStepState) return;
    var s = smartStepState;
    var panel = document.getElementById('changes-panel');
    if (!panel) return;

    var occ = s.occurrences[s.currentIdx];
    var progress = Math.round((s.currentIdx / s.total) * 100);

    panel.className = 'changes-panel visible';

    var html = '<div class="smart-step-container">'
        + '<div class="smart-step-header">'
        + '<span>&#128260; Replacing "<strong>' + escapeHtml(s.oldEnglish) + '</strong>" &rarr; "<strong>' + escapeHtml(s.newEnglish) + '</strong>"</span>'
        + '<span class="smart-step-progress">' + (s.currentIdx + 1) + ' / ' + s.total + '</span>'
        + '</div>'
        + '<div class="smart-step-progressbar"><div class="smart-step-fill" style="width:' + progress + '%"></div></div>'
        + '<div class="smart-step-stats">'
        + '<span class="smart-step-accepted">' + s.acceptedCount + ' accepted</span>'
        + '<span class="smart-step-skipped">' + s.skippedCount + ' skipped</span>'
        + '</div>'
        + '<div class="smart-step-occurrence">'
        + '<div class="smart-step-context">"...' + escapeHtml(occ.context) + '..."</div>'
        + '<div class="smart-step-change">'
        + '<span class="change-old-text">' + escapeHtml(occ.find) + '</span>'
        + ' &rarr; '
        + '<input type="text" class="smart-step-input" id="smart-step-replace" value="' + escapeHtml(occ.replace) + '">'
        + '</div>'
        + '</div>'
        + '<div class="smart-step-buttons">'
        + '<button class="btn btn-sm btn-success" onclick="smartStepAccept()">&#10003; Accept</button>'
        + '<button class="btn btn-sm btn-outline" onclick="smartStepSkip()">&#10140; Skip</button>'
        + '<button class="btn btn-sm btn-outline" onclick="smartStepUndo()"' + (s.currentIdx === 0 ? ' disabled' : '') + '>&#8617; Undo</button>'
        + '<button class="btn btn-sm btn-danger" onclick="smartStepCancel()">&#10005; Cancel</button>'
        + '</div>'
        + '</div>';

    panel.innerHTML = html;

    // Highlight the current occurrence in the English preview
    highlightSmartStepOccurrence(occ.find);

    // Scroll the panel into view
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function highlightSmartStepOccurrence(findText) {
    clearHighlights('highlight-pending');
    clearHighlights('highlight-correction');
    var enPreview = document.getElementById('english-preview');
    if (!enPreview) return;

    if (!enPreview.querySelector('.editable-word')) {
        wrapWords(enPreview, 'editable-word');
    }

    // Find the specific text in the preview and highlight it
    var words = enPreview.querySelectorAll('.editable-word');
    var termWords = findText.toLowerCase().split(/\s+/);
    if (termWords.length === 0) return;

    // We want to find the Nth remaining match that hasn't been replaced
    // For now, highlight the first match we find
    for (var i = 0; i <= words.length - termWords.length; i++) {
        var match = true;
        for (var j = 0; j < termWords.length; j++) {
            var wordText = words[i + j].textContent.toLowerCase().replace(/^[^\w\u00C0-\u024F]+|[^\w\u00C0-\u024F]+$/g, '');
            if (wordText !== termWords[j]) { match = false; break; }
        }
        if (match) {
            for (var j = 0; j < termWords.length; j++) {
                words[i + j].classList.add('highlight-pending');
            }
            words[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }
    }
}

async function smartStepAccept() {
    if (!smartStepState) return;
    var replaceInput = document.getElementById('smart-step-replace');
    var replaceText = replaceInput ? replaceInput.value.trim() : '';

    try {
        var formData = new FormData();
        formData.append('action', 'accept');
        if (replaceText) formData.append('replace_text', replaceText);

        var resp = await fetch('/api/smart-replace-step', { method: 'POST', body: formData });
        var data = await resp.json();

        if (!data.success) return;

        smartStepState.currentIdx = data.current_idx;
        smartStepState.acceptedCount++;

        // Update English preview
        var enPreview = document.getElementById('english-preview');
        if (enPreview && data.translated_html) {
            enPreview.innerHTML = data.translated_html;
            wrapWords(enPreview, 'editable-word');
        }

        if (data.finished) {
            finishSmartSteps(data);
        } else {
            smartStepState.occurrences = smartStepState.occurrences;
            if (data.occurrence) {
                smartStepState.occurrences[data.current_idx] = data.occurrence;
            }
            renderSmartStepUI();
        }
    } catch (err) {
        console.error('Smart step accept failed:', err);
    }
}

async function smartStepSkip() {
    if (!smartStepState) return;

    try {
        var formData = new FormData();
        formData.append('action', 'skip');

        var resp = await fetch('/api/smart-replace-step', { method: 'POST', body: formData });
        var data = await resp.json();

        if (!data.success) return;

        smartStepState.currentIdx = data.current_idx;
        smartStepState.skippedCount++;

        if (data.finished) {
            finishSmartSteps(data);
        } else {
            renderSmartStepUI();
        }
    } catch (err) {
        console.error('Smart step skip failed:', err);
    }
}

async function smartStepUndo() {
    if (!smartStepState || smartStepState.currentIdx === 0) return;

    try {
        var formData = new FormData();
        formData.append('action', 'undo');

        var resp = await fetch('/api/smart-replace-step', { method: 'POST', body: formData });
        var data = await resp.json();

        if (!data.success) return;

        smartStepState.currentIdx = data.current_idx;
        // Figure out what was undone to adjust counters
        // The server already handled the undo, just re-sync
        if (smartStepState.acceptedCount > 0 || smartStepState.skippedCount > 0) {
            // Decrease the appropriate counter (we don't know which, so recalculate)
            smartStepState.acceptedCount = Math.max(0, smartStepState.acceptedCount - 1);
        }

        // Update English preview
        var enPreview = document.getElementById('english-preview');
        if (enPreview && data.translated_html) {
            enPreview.innerHTML = data.translated_html;
            wrapWords(enPreview, 'editable-word');
        }

        renderSmartStepUI();
    } catch (err) {
        console.error('Smart step undo failed:', err);
    }
}

async function smartStepCancel() {
    try {
        var resp = await fetch('/api/smart-replace-cancel', { method: 'POST' });
        var data = await resp.json();

        if (data.success) {
            var enPreview = document.getElementById('english-preview');
            if (enPreview && data.translated_html) {
                enPreview.innerHTML = data.translated_html;
                wrapWords(enPreview, 'editable-word');
                initInteractivePreviews();
            }
        }

        smartStepState = null;
        clearHighlights('highlight-pending');

        // Hide panel
        var panel = document.getElementById('changes-panel');
        if (panel) {
            panel.className = 'changes-panel';
            panel.innerHTML = '';
        }
        // Re-render existing changes log if any
        renderChangesPanel();

        var msgEl = document.getElementById('glossary-add-msg');
        msgEl.innerHTML = '<div class="alert alert-info">Replacement cancelled — all changes reverted.</div>';
        setTimeout(function() { msgEl.innerHTML = ''; }, 5000);
    } catch (err) {
        console.error('Smart step cancel failed:', err);
    }
}

function finishSmartSteps(data) {
    smartStepState = null;
    clearHighlights('highlight-pending');

    var msgEl = document.getElementById('glossary-add-msg');

    if (data.accepted_count > 0) {
        // Add to changes log
        changesLog.push({
            french_term: data.french_term,
            old_english: data.old_english,
            new_english: data.new_english,
            changes: data.changes || [],
            count: data.accepted_count,
        });
        renderChangesPanel();

        // Highlight accepted terms
        var enPreview = document.getElementById('english-preview');
        if (enPreview && data.new_terms) {
            data.new_terms.forEach(function(term) {
                highlightWordsInPreview(enPreview, term, 'highlight-correction');
            });
            var firstHL = enPreview.querySelector('.highlight-correction');
            if (firstHL) firstHL.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        var summary = data.accepted_count + ' accepted, ' + data.skipped_count + ' skipped';
        msgEl.innerHTML = '<div class="alert alert-success">Replacement complete: ' + escapeHtml(summary) + '</div>';

        initInteractivePreviews();
        updateUndoBar(data.undo_info);
        updateSidebarStats();

        setTimeout(function() {
            clearHighlights('highlight-correction');
            msgEl.innerHTML = '';
        }, 8000);
    } else {
        renderChangesPanel();
        msgEl.innerHTML = '<div class="alert alert-info">No replacements made (' + data.skipped_count + ' skipped).</div>';
        setTimeout(function() { msgEl.innerHTML = ''; }, 5000);
    }
}

// ==========================================
// Step-by-step replacement (multiple occurrences)
// ==========================================
var stepData = null;

async function initStepByStep(frenchTerm, oldEnglish, newEnglish, count) {
    var msgEl = document.getElementById('glossary-add-msg');
    msgEl.innerHTML = '<div class="alert alert-info"><span class="spinner" style="vertical-align:middle;margin-right:8px;"></span> Initializing replacement...</div>';

    try {
        var formData = new FormData();
        formData.append('french_term', frenchTerm);
        formData.append('old_english', oldEnglish);
        formData.append('new_english', newEnglish);

        var resp = await fetch('/api/replace-init', { method: 'POST', body: formData });
        var data = await resp.json();

        if (!data.success) {
            msgEl.innerHTML = '<div class="alert alert-warning">' + escapeHtml(data.message) + '</div>';
            setTimeout(function() { msgEl.innerHTML = ''; }, 5000);
            return;
        }

        stepData = {
            frenchTerm: frenchTerm,
            oldEnglish: oldEnglish,
            newEnglish: newEnglish,
            total: data.total,
            currentIdx: 0,
            replaced: 0,
            skipped: 0,
        };

        renderStepUI();
    } catch (err) {
        msgEl.innerHTML = '<div class="alert alert-danger">Error: ' + escapeHtml(err.message) + '</div>';
    }
}

function renderStepUI() {
    if (!stepData) return;
    var msgEl = document.getElementById('glossary-add-msg');
    var s = stepData;
    var progress = Math.round((s.currentIdx / s.total) * 100);

    // Highlight current occurrence in English preview
    clearHighlights('highlight-pending');
    clearHighlights('highlight-success');
    var enPreview = document.getElementById('english-preview');
    if (enPreview) {
        if (!enPreview.querySelector('.editable-word')) {
            wrapWords(enPreview, 'editable-word');
        }
        // Highlight the Nth remaining occurrence (skip already skipped ones)
        highlightNthOccurrence(enPreview, s.oldEnglish, s.skipped);
    }

    msgEl.innerHTML = '<div class="replace-step-bar">' +
        '<div class="step-info">Replacing <strong>"' + escapeHtml(s.oldEnglish) + '"</strong> with <strong>"' + escapeHtml(s.newEnglish) + '"</strong> (' + (s.currentIdx + 1) + ' of ' + s.total + ') — ' + s.replaced + ' replaced, ' + s.skipped + ' skipped</div>' +
        '<div class="progress-bar"><div class="progress-fill" style="width:' + progress + '%"></div></div>' +
        '<div class="step-edit"><label>Replace with:</label><input type="text" id="step-custom-term" value="' + escapeHtml(s.newEnglish) + '"></div>' +
        '<div class="step-buttons">' +
        '<button class="btn btn-sm btn-success" onclick="stepReplace()">Replace</button>' +
        '<button class="btn btn-sm btn-outline" onclick="stepSkip()">Skip</button>' +
        '<button class="btn btn-sm btn-outline" onclick="stepUndo()" ' + (s.currentIdx === 0 ? 'disabled' : '') + '>Undo</button>' +
        '<button class="btn btn-sm btn-danger" onclick="stepCancel()">Cancel</button>' +
        '</div></div>';
}

function highlightNthOccurrence(enPreview, term, n) {
    var words = enPreview.querySelectorAll('.editable-word');
    var termWords = term.toLowerCase().split(/\s+/);
    if (termWords.length === 0) return;

    var occurrenceIdx = 0;
    for (var i = 0; i <= words.length - termWords.length; i++) {
        var match = true;
        for (var j = 0; j < termWords.length; j++) {
            var wordText = words[i + j].textContent.toLowerCase().replace(/^[^\w\u00C0-\u024F]+|[^\w\u00C0-\u024F]+$/g, '');
            if (wordText !== termWords[j]) { match = false; break; }
        }
        if (match) {
            if (occurrenceIdx === n) {
                for (var j = 0; j < termWords.length; j++) {
                    words[i + j].classList.add('highlight-pending');
                }
                words[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            occurrenceIdx++;
        }
    }
}

async function stepReplace() {
    if (!stepData) return;
    var customTerm = document.getElementById('step-custom-term');
    var effectiveTerm = (customTerm && customTerm.value.trim()) || stepData.newEnglish;

    try {
        var formData = new FormData();
        formData.append('action', 'replace');
        formData.append('effective_term', effectiveTerm);

        var resp = await fetch('/api/replace-step', { method: 'POST', body: formData });
        var data = await resp.json();

        if (data.success) {
            stepData.replaced++;
            stepData.currentIdx++;

            // Update English preview
            var enPreview = document.getElementById('english-preview');
            if (enPreview && data.translated_html) {
                enPreview.innerHTML = data.translated_html;
                wrapWords(enPreview, 'editable-word');
            }

            if (data.finished) {
                finishStepByStep(data);
            } else {
                renderStepUI();
            }
        }
    } catch (err) {
        console.error('Step replace failed:', err);
    }
}

async function stepSkip() {
    if (!stepData) return;

    try {
        var formData = new FormData();
        formData.append('action', 'skip');

        var resp = await fetch('/api/replace-step', { method: 'POST', body: formData });
        var data = await resp.json();

        if (data.success) {
            stepData.skipped++;
            stepData.currentIdx++;

            if (data.finished) {
                finishStepByStep(data);
            } else {
                renderStepUI();
            }
        }
    } catch (err) {
        console.error('Step skip failed:', err);
    }
}

async function stepUndo() {
    if (!stepData || stepData.currentIdx === 0) return;

    try {
        var formData = new FormData();
        formData.append('action', 'undo');

        var resp = await fetch('/api/replace-step', { method: 'POST', body: formData });
        var data = await resp.json();

        if (data.success) {
            // Adjust counters based on what was undone
            stepData.currentIdx--;
            if (data.undone_action === 'replace') stepData.replaced--;
            if (data.undone_action === 'skip') stepData.skipped--;

            // Update English preview
            var enPreview = document.getElementById('english-preview');
            if (enPreview && data.translated_html) {
                enPreview.innerHTML = data.translated_html;
                wrapWords(enPreview, 'editable-word');
            }

            renderStepUI();
        }
    } catch (err) {
        console.error('Step undo failed:', err);
    }
}

async function stepCancel() {
    try {
        var resp = await fetch('/api/replace-cancel', { method: 'POST' });
        var data = await resp.json();

        if (data.success) {
            var enPreview = document.getElementById('english-preview');
            if (enPreview && data.translated_html) {
                enPreview.innerHTML = data.translated_html;
                wrapWords(enPreview, 'editable-word');
                initInteractivePreviews();
            }
        }

        stepData = null;
        clearHighlights('highlight-pending');
        document.getElementById('glossary-add-msg').innerHTML =
            '<div class="alert alert-info">Replacement cancelled — all changes reverted.</div>';
        setTimeout(function() { document.getElementById('glossary-add-msg').innerHTML = ''; }, 5000);
    } catch (err) {
        console.error('Step cancel failed:', err);
    }
}

function finishStepByStep(data) {
    stepData = null;
    clearHighlights('highlight-pending');

    var msgEl = document.getElementById('glossary-add-msg');
    if (data.replaced_count > 0) {
        msgEl.innerHTML = '<div class="alert alert-success">' + escapeHtml(data.message) + '</div>';

        // Highlight replaced terms in green
        var enPreview = document.getElementById('english-preview');
        if (enPreview && data.new_terms) {
            data.new_terms.forEach(function(term) {
                highlightWordsInPreview(enPreview, term, 'highlight-success');
            });
        }

        // Show diff viewer
        if (data.diff_html) {
            showDiffViewer(data.diff_html);
        }

        updateUndoBar(data.undo_info);
        initInteractivePreviews();
        updateSidebarStats();

        setTimeout(function() {
            clearHighlights('highlight-success');
            msgEl.innerHTML = '';
        }, 5000);
    } else {
        msgEl.innerHTML = '<div class="alert alert-info">No replacements made.</div>';
        setTimeout(function() { msgEl.innerHTML = ''; }, 3000);
    }
}

// ==========================================
// Undo
// ==========================================
function updateUndoBar(undoInfo) {
    var undoContainer = document.getElementById('undo-container');
    if (!undoContainer) return;

    if (!undoInfo || !undoInfo.has_undo) {
        undoContainer.innerHTML = '';
        return;
    }

    undoContainer.innerHTML = '<div class="undo-bar">' +
        '<span class="undo-info">Last change: <strong>"' + escapeHtml(undoInfo.old_term) + '"</strong> → <strong>"' + escapeHtml(undoInfo.new_term) + '"</strong></span>' +
        '<button class="btn btn-sm btn-outline" onclick="undoLastChange()">Undo</button>' +
        '</div>';
}

async function undoLastChange() {
    try {
        var resp = await fetch('/api/undo', { method: 'POST' });
        var data = await resp.json();

        if (data.success) {
            var enPreview = document.getElementById('english-preview');
            if (enPreview && data.translated_html) {
                enPreview.innerHTML = data.translated_html;
                wrapWords(enPreview, 'editable-word');
                initInteractivePreviews();
            }

            // Also remove from changes log if it matches
            if (changesLog.length > 0) {
                changesLog.pop();
                renderChangesPanel();
            }

            updateUndoBar(data.undo_info);
            updateSidebarStats();

            var msgEl = document.getElementById('glossary-add-msg');
            msgEl.innerHTML = '<div class="alert alert-success">Reverted: "' + escapeHtml(data.reverted_new) + '" back to "' + escapeHtml(data.reverted_old) + '"</div>';
            setTimeout(function() { msgEl.innerHTML = ''; }, 5000);
        }
    } catch (err) {
        console.error('Undo failed:', err);
    }
}

// ==========================================
// Before / After diff viewer
// ==========================================
function showDiffViewer(html) {
    var container = document.getElementById('diff-container');
    if (!container) return;
    container.innerHTML = html;
}

function hideDiffViewer() {
    var container = document.getElementById('diff-container');
    if (container) container.innerHTML = '';
}

// ==========================================
// Toast notification
// ==========================================
function showToast(message, type) {
    var toast = document.createElement('div');
    toast.className = 'toast-notification toast-' + (type || 'info');
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function() { toast.classList.add('show'); }, 10);
    setTimeout(function() {
        toast.classList.remove('show');
        setTimeout(function() { toast.remove(); }, 300);
    }, 4000);
}

// ==========================================
// Add to Glossary feedback (inline button + toast)
// ==========================================
function glossaryAddFeedback(form, event) {
    var btn = form.querySelector('button[type=submit]');
    if (!btn) return;

    var isSuccess = event.detail.successful && event.detail.xhr &&
                    event.detail.xhr.responseText.indexOf('alert-success') !== -1;

    if (isSuccess) {
        var origText = btn.textContent;
        btn.textContent = 'Added!';
        btn.disabled = true;
        btn.style.opacity = '0.7';
        showToast('Term added to glossary!', 'success');
        setTimeout(function() {
            btn.textContent = origText;
            btn.disabled = false;
            btn.style.opacity = '';
        }, 3000);
    } else if (event.detail.successful) {
        // Warning (e.g. duplicate)
        showToast('Term already exists in glossary', 'warning');
    } else {
        showToast('Failed to add term', 'danger');
    }

    // Scroll to detailed message
    var msg = document.getElementById('glossary-add-msg');
    if (msg && msg.innerHTML.trim()) {
        msg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// ==========================================
// Copy translation (rich HTML + plain text)
// ==========================================
async function copyTranslation() {
    var el = document.getElementById('english-preview');
    if (!el) return;
    var html = el.innerHTML;
    var text = el.innerText;

    try {
        await navigator.clipboard.write([
            new ClipboardItem({
                'text/html': new Blob([html], { type: 'text/html' }),
                'text/plain': new Blob([text], { type: 'text/plain' }),
            })
        ]);
    } catch (e) {
        // Fallback to plain text
        try {
            await navigator.clipboard.writeText(text);
        } catch (e2) {
            console.error('Copy failed:', e2);
            return;
        }
    }

    var btn = event.target.closest('.btn');
    if (btn) {
        var orig = btn.innerHTML;
        btn.textContent = 'Copied!';
        setTimeout(function() { btn.innerHTML = orig; }, 2000);
    }
}

// ==========================================
// Sidebar
// ==========================================
function toggleSidebar() {
    var sidebar = document.querySelector('.sidebar');
    var overlay = document.querySelector('.sidebar-overlay');
    var toggle = document.querySelector('.sidebar-toggle');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
    if (toggle) toggle.style.display = sidebar.classList.contains('open') ? 'none' : '';
}

function updateSidebarStats() {
    fetch('/api/stats')
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            var el;
            el = document.getElementById('stat-translations');
            if (el) el.textContent = data.translation_count;
            el = document.getElementById('stat-cost');
            if (el) el.textContent = '$' + data.total_cost.toFixed(4);
            el = document.getElementById('stat-glossary');
            if (el) el.textContent = data.glossary_count;
        })
        .catch(function() {});
}

// ==========================================
// HTMX: After translation loads
// ==========================================
document.body.addEventListener('htmx:afterSwap', function(e) {
    if (e.target.id === 'output-area') {
        // New translation: reset changes log
        changesLog = [];
        initInteractivePreviews();
        // Generate word alignment in the background (non-blocking)
        fetch('/api/alignment', { method: 'POST' })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.success) {
                    console.log('[OK] Word alignment loaded');
                }
            })
            .catch(function() {});
    }
    // Auto-dismiss success alerts after 5s
    e.target.querySelectorAll('.alert-success').forEach(function(a) {
        setTimeout(function() { a.remove(); }, 5000);
    });
});

// ==========================================
// On page load
// ==========================================
document.addEventListener('DOMContentLoaded', function() {
    // Check if we already have translation content
    var enPreview = document.getElementById('english-preview');
    if (enPreview && enPreview.textContent.trim() && !enPreview.querySelector('.empty-output')) {
        initInteractivePreviews();
    } else {
        livePreviewActive = true;
        updateFrenchPreview();
        setupFrenchClickHandlers();
    }

    // Live preview on textarea input
    var textarea = document.getElementById('french_text');
    if (textarea) {
        textarea.addEventListener('input', function() {
            clearTimeout(previewTimeout);
            previewTimeout = setTimeout(updateFrenchPreview, 300);
        });
    }

    // File upload
    initFileUpload();
});
