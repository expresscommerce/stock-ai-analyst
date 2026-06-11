/* ═══════════════════════════════════════════════
   Dashboard JS — Data loading, WebSocket, UI
   ═══════════════════════════════════════════════ */

// ── Globals ──
let exchangeRates = {};
const socket = typeof io !== 'undefined' ? io() : null;

// ── Toast Notifications ──
function showToast(msg, type = 'info') {
    const c = document.getElementById('toast-container');
    if (!c) return;
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<span>${msg}</span>`;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 4000);
}

// ── Format Helpers ──
function fmt(n, d = 2) { return n != null ? Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }) : '—'; }
function fmtLarge(n) {
    if (n == null) return '—';
    if (n >= 1e12) return (n / 1e12).toFixed(2) + 'T';
    if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    return n.toLocaleString();
}
function chgClass(v) { return v > 0 ? 'positive' : v < 0 ? 'negative' : ''; }
function chgSign(v) { return v > 0 ? '+' + fmt(v) + '%' : fmt(v) + '%'; }

// ── Initialize Dashboard ──
function initDashboard() {
    loadDashboardData();
    loadSectorHeatmap();
    loadAlerts();
    renderWatchlist();
    renderSidebarWatchlist();

    // WebSocket
    if (socket) {
        socket.on('price_update', (data) => {
            showToast('Prices updated', 'success');
            loadDashboardData();
        });
    }

    // Auto-refresh every 5 min
    setInterval(loadDashboardData, 300000);
}

// ── Load Dashboard Data ──
async function loadDashboardData() {
    try {
        const res = await fetch('/api/dashboard-data');
        const data = await res.json();

        renderIndices(data.indices || []);
        renderMovers(data.movers || {});
        renderNews(data.news || []);
        renderBriefing(data.briefing);

        if (data.exchange_rates) {
            exchangeRates = data.exchange_rates;
            renderRates(exchangeRates);
            convertCurrency();
        }
    } catch (e) {
        console.error('Dashboard load error:', e);
    }
}

// ── Render Indices ──
function renderIndices(indices) {
    const grid = document.getElementById('indices-grid');
    if (!grid) return;
    if (!indices.length) {
        grid.innerHTML = '<div class="card index-card"><div class="index-name">No data</div></div>';
        return;
    }
    grid.innerHTML = indices.map(i => `
        <div class="card index-card">
            <div class="index-name">${i.company_name || i.ticker}</div>
            <div class="index-price ${chgClass(i.percent_change)}">${fmt(i.price)}</div>
            <div class="index-change ${chgClass(i.percent_change)}">${chgSign(i.percent_change)}</div>
        </div>
    `).join('');
}

// ── Render Movers Tables ──
function renderMovers(movers) {
    renderMoverTable('gainers-table', movers.gainers || []);
    renderMoverTable('losers-table', movers.losers || []);
}
function renderMoverTable(id, stocks) {
    const table = document.querySelector(`#${id} tbody`);
    if (!table) return;
    if (!stocks.length) { table.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted);text-align:center;padding:1rem;">No data</td></tr>'; return; }
    table.innerHTML = stocks.map(s => `
        <tr>
            <td class="ticker" onclick="location.href='/stock/${s.ticker}'">${s.ticker}</td>
            <td style="font-size:.78rem;color:var(--text-secondary);">${(s.company_name || '').substring(0, 20)}</td>
            <td class="price">$${fmt(s.price)}</td>
            <td class="change ${chgClass(s.percent_change)}">${chgSign(s.percent_change)}</td>
        </tr>
    `).join('');
}

// ── Render News ──
function renderNews(news) {
    const feed = document.getElementById('news-feed');
    if (!feed) return;
    if (!news.length) { feed.innerHTML = '<div style="color:var(--text-muted);padding:.5rem;">No news available. Configure NEWS_API_KEY to fetch articles.</div>'; return; }
    feed.innerHTML = news.map(n => {
        const sentClass = n.sentiment_label === 'positive' ? 'pos' : n.sentiment_label === 'negative' ? 'neg' : 'neu';
        const time = n.published_at ? new Date(n.published_at).toLocaleDateString() : '';
        return `
        <div class="news-item">
            <div class="news-sentiment ${sentClass}"></div>
            <div>
                <div class="news-title"><a href="${n.url}" target="_blank" rel="noopener">${n.title}</a></div>
                <div class="news-meta"><span>${n.source || ''}</span><span>${time}</span>
                    ${n.tickers?.length ? `<span>${n.tickers.join(', ')}</span>` : ''}
                </div>
            </div>
        </div>`;
    }).join('');
}

// ── Render AI Briefing ──
function renderBriefing(briefing) {
    const el = document.getElementById('daily-briefing');
    if (!el) return;
    if (!briefing) { el.innerHTML = '<em style="color:var(--text-muted);">No briefing available yet. The AI generates a daily report at 9:00 AM UTC.</em>'; return; }
    el.innerHTML = `<div class="ai-badge">AI Briefing — ${briefing.report_date || 'Today'}</div><div style="white-space:pre-wrap;">${briefing.content}</div>`;
}

// ── Sector Heatmap ──
async function loadSectorHeatmap() {
    try {
        const res = await fetch('/api/charts/sector-heatmap');
        const data = await res.json();
        renderHeatmap(data.sectors || []);
    } catch (e) { console.error('Heatmap error:', e); }
}
function renderHeatmap(sectors) {
    const grid = document.getElementById('heatmap-grid');
    if (!grid) return;
    grid.innerHTML = sectors.map(s => {
        const c = s.percent_change;
        const intensity = Math.min(Math.abs(c) * 15, 100);
        const bg = c >= 0 ? `rgba(16,185,129,${intensity/100 * 0.5 + 0.1})` : `rgba(239,68,68,${intensity/100 * 0.5 + 0.1})`;
        return `<div class="heatmap-cell" style="background:${bg}">
            <div class="sector-name">${s.name}</div>
            <div class="sector-change">${chgSign(c)}</div>
        </div>`;
    }).join('');
}

// ── Currency ──
function renderRates(rates) {
    const el = document.getElementById('rates-list');
    if (!el) return;
    const keys = Object.keys(rates).filter(k => k !== 'USD').slice(0, 6);
    el.innerHTML = keys.map(k => `<div style="display:flex;justify-content:space-between;padding:.25rem 0;font-size:.78rem;border-bottom:1px solid var(--border-color);">
        <span style="color:var(--text-muted);">USD/${k}</span>
        <span style="font-family:'JetBrains Mono',monospace;font-weight:600;">${fmt(rates[k], 4)}</span>
    </div>`).join('');
}
function convertCurrency() {
    const amt = parseFloat(document.getElementById('conv-amount')?.value) || 1;
    const from = document.getElementById('conv-from')?.value || 'USD';
    const to = document.getElementById('conv-to')?.value || 'PKR';
    const el = document.getElementById('conv-result');
    if (!el) return;
    if (!Object.keys(exchangeRates).length) { el.textContent = 'Loading...'; return; }
    const fromRate = exchangeRates[from] || 1;
    const toRate = exchangeRates[to] || 1;
    const result = (amt / fromRate) * toRate;
    el.textContent = `${fmt(amt)} ${from} = ${fmt(result, 4)} ${to}`;
}

// ── Alerts ──
async function loadAlerts() {
    try {
        const res = await fetch('/api/alerts');
        const data = await res.json();
        renderAlerts(data.alerts || []);
    } catch (e) { console.error('Alerts error:', e); }
}
function renderAlerts(alerts) {
    const el = document.getElementById('alerts-list');
    if (!el) return;
    if (!alerts.length) { el.innerHTML = '<div style="color:var(--text-muted);font-size:.8rem;">No active alerts.</div>'; return; }
    el.innerHTML = alerts.map(a => `
        <div class="alert-item">
            <div><strong>${a.ticker}</strong> — ${a.alert_type.replace('_', ' ')} $${fmt(a.threshold_value)}</div>
            <button class="alert-delete" onclick="deleteAlert(${a.id})">✕</button>
        </div>
    `).join('');
}
async function createAlert() {
    const ticker = document.getElementById('alert-ticker')?.value?.toUpperCase();
    const type = document.getElementById('alert-type')?.value;
    const value = parseFloat(document.getElementById('alert-value')?.value);
    if (!ticker || !value) { showToast('Fill all alert fields', 'error'); return; }
    try {
        await fetch('/api/alerts', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ticker, alert_type: type, threshold_value: value}) });
        showToast(`Alert set for ${ticker}`, 'success');
        loadAlerts();
    } catch (e) { showToast('Failed to create alert', 'error'); }
}
async function deleteAlert(id) {
    try { await fetch(`/api/alerts/${id}`, {method: 'DELETE'}); loadAlerts(); } catch(e) {}
}

// ── Watchlist (localStorage) ──
function getWatchlist() { try { return JSON.parse(localStorage.getItem('watchlist') || '[]'); } catch { return []; } }
function saveWatchlist(list) { localStorage.setItem('watchlist', JSON.stringify(list)); }
function addToWatchlist() {
    const inp = document.getElementById('watchlist-add-input');
    const ticker = inp?.value?.toUpperCase().trim();
    if (!ticker) return;
    const list = getWatchlist();
    if (!list.includes(ticker)) { list.push(ticker); saveWatchlist(list); showToast(`${ticker} added to watchlist`, 'success'); }
    inp.value = '';
    renderWatchlist();
    renderSidebarWatchlist();
}
function removeFromWatchlist(ticker) {
    saveWatchlist(getWatchlist().filter(t => t !== ticker));
    renderWatchlist();
    renderSidebarWatchlist();
}
function toggleWatchlistFromDetail(ticker) {
    const list = getWatchlist();
    if (list.includes(ticker)) { removeFromWatchlist(ticker); showToast(`${ticker} removed`, 'info'); }
    else { list.push(ticker); saveWatchlist(list); showToast(`${ticker} added`, 'success'); renderWatchlist(); renderSidebarWatchlist(); }
}
async function renderWatchlist() {
    const grid = document.getElementById('watchlist-grid');
    if (!grid) return;
    const list = getWatchlist();
    if (!list.length) { grid.innerHTML = '<div style="color:var(--text-muted);font-size:.85rem;padding:1rem;text-align:center;">Add tickers to your watchlist.</div>'; return; }
    grid.innerHTML = list.map(t => `
        <div class="watchlist-card" onclick="location.href='/stock/${t}'">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div class="watchlist-ticker">${t}</div>
                <button class="alert-delete" onclick="event.stopPropagation();removeFromWatchlist('${t}')">✕</button>
            </div>
            <div class="watchlist-price" id="wl-price-${t}">...</div>
            <div class="watchlist-change" id="wl-change-${t}">...</div>
        </div>
    `).join('');
    // Load prices
    for (const t of list) {
        try {
            const res = await fetch(`/api/stock/${t}/data`);
            const data = await res.json();
            if (data.stock) {
                const pe = document.getElementById(`wl-price-${t}`);
                const ce = document.getElementById(`wl-change-${t}`);
                if (pe) pe.textContent = '$' + fmt(data.stock.price);
                if (ce) { ce.textContent = chgSign(data.stock.percent_change); ce.className = 'watchlist-change ' + chgClass(data.stock.percent_change); }
            }
        } catch (e) {}
    }
}
function renderSidebarWatchlist() {
    const el = document.getElementById('sidebar-watchlist');
    if (!el) return;
    const list = getWatchlist();
    el.innerHTML = list.slice(0, 5).map(t => `<a href="/stock/${t}" class="nav-item">${t}</a>`).join('');
}
