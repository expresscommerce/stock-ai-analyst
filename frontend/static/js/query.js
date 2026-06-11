/* ═══════════════════════════════════════════════
   Query JS — NL query with SSE streaming
   ═══════════════════════════════════════════════ */

let queryInProgress = false;

async function sendQuery() {
    if (queryInProgress) return;
    const input = document.getElementById('query-input');
    const btn = document.getElementById('query-btn');
    const btnText = document.getElementById('query-btn-text');
    const responseEl = document.getElementById('query-response');
    const question = input?.value?.trim();

    if (!question) { showToast('Please enter a question', 'error'); return; }

    queryInProgress = true;
    btn.disabled = true;
    btnText.textContent = 'Thinking...';
    responseEl.classList.add('active');
    responseEl.innerHTML = '<em style="color:var(--text-muted);">Analyzing your question...</em>';

    try {
        // Try streaming first
        const res = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, stream: false }),
        });

        const data = await res.json();

        if (data.error) {
            responseEl.innerHTML = `<span style="color:var(--red);">${data.error}</span>`;
        } else {
            // Format the answer with markdown-like styling
            let answer = data.answer || 'No response received.';
            answer = answer.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            answer = answer.replace(/\n/g, '<br>');

            let html = answer;
            if (data.tickers?.length) {
                html += `<div style="margin-top:.75rem;padding-top:.75rem;border-top:1px solid var(--border-color);font-size:.75rem;color:var(--text-muted);">
                    Referenced tickers: ${data.tickers.map(t => `<a href="/stock/${t}" style="color:var(--accent-blue);text-decoration:none;font-weight:600;">${t}</a>`).join(', ')}
                </div>`;
            }
            responseEl.innerHTML = html;
        }
    } catch (e) {
        console.error('Query error:', e);
        responseEl.innerHTML = '<span style="color:var(--red);">Failed to get response. Please try again.</span>';
    }

    queryInProgress = false;
    btn.disabled = false;
    btnText.textContent = 'Analyze';
}

// ── SSE streaming version (for future use) ──
async function sendQueryStream() {
    const input = document.getElementById('query-input');
    const responseEl = document.getElementById('query-response');
    const question = input?.value?.trim();
    if (!question) return;

    responseEl.classList.add('active');
    responseEl.textContent = '';

    try {
        const res = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, stream: true }),
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') break;
                    responseEl.textContent += data;
                }
            }
        }
    } catch (e) {
        responseEl.textContent += '\n\nStream interrupted.';
    }
}
