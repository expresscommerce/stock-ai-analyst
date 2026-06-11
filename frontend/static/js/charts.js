/* ═══════════════════════════════════════════════
   Chart.js — Price charts, volume, sparklines
   ═══════════════════════════════════════════════ */

let priceChart = null;
let volumeChart = null;

const chartColors = {
    green: '#10b981', red: '#ef4444', blue: '#2563eb', cyan: '#0891b2',
    gridColor: '#f1f5f9', textColor: '#64748b',
};

const defaultChartOptions = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: {
        backgroundColor: '#ffffff', titleColor: '#0f172a', bodyColor: '#475569',
        borderColor: '#e2e8f0', borderWidth: 1, padding: 10, cornerRadius: 8,
        titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
        bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
    }},
    scales: {
        x: { grid: { color: chartColors.gridColor, drawBorder: false }, ticks: { color: chartColors.textColor, font: { size: 10 }, maxTicksLimit: 8 } },
        y: { grid: { color: chartColors.gridColor, drawBorder: false }, ticks: { color: chartColors.textColor, font: { family: "'JetBrains Mono', monospace", size: 10 } }, position: 'right' },
    },
    interaction: { intersect: false, mode: 'index' },
    animation: { duration: 800, easing: 'easeOutQuart' },
};

// ── Load Stock Detail Page ──
async function loadStockDetail(ticker) {
    try {
        const res = await fetch(`/api/stock/${ticker}/data`);
        const data = await res.json();
        if (data.error) { showToast(data.error, 'error'); return; }

        renderStockHero(data.stock);
        renderStockStats(data.stock);
        renderIndicators(data.technical);
        renderStockNews(data.news || []);
        loadPriceChart(ticker, '1mo');
        setupPeriodTabs(ticker);
    } catch (e) { console.error('Stock detail error:', e); showToast('Failed to load stock data', 'error'); }
}

function renderStockHero(s) {
    const ne = document.getElementById('stock-name');
    const pe = document.getElementById('stock-price');
    const ce = document.getElementById('stock-change');
    if (ne) ne.textContent = `${s.company_name || s.ticker} · ${s.exchange || ''} · ${s.currency || 'USD'}`;
    if (pe) { pe.textContent = '$' + fmt(s.price); pe.className = 'stock-hero-price ' + chgClass(s.percent_change); }
    if (ce) { ce.textContent = `${chgSign(s.percent_change)}`; ce.className = 'stock-hero-change ' + chgClass(s.percent_change); }
}

function renderStockStats(s) {
    const grid = document.getElementById('stats-grid');
    if (!grid) return;
    const stats = [
        ['Market Cap', fmtLarge(s.market_cap)], ['P/E Ratio', fmt(s.pe_ratio)],
        ['52W High', '$' + fmt(s.week_52_high)], ['52W Low', '$' + fmt(s.week_52_low)],
        ['Open', '$' + fmt(s.open)], ['Day High', '$' + fmt(s.high)],
        ['Day Low', '$' + fmt(s.low)], ['Volume', fmtLarge(s.volume)],
        ['Div Yield', s.dividend_yield ? (s.dividend_yield * 100).toFixed(2) + '%' : '—'],
    ];
    grid.innerHTML = stats.map(([l, v]) => `<div class="stat-item"><div class="stat-label">${l}</div><div class="stat-value">${v}</div></div>`).join('');
}

function renderIndicators(t) {
    const grid = document.getElementById('indicators-grid');
    if (!grid) return;
    const items = [
        ['RSI (14)', t.rsi, t.rsi_signal, t.rsi_signal === 'Overbought' ? 'negative' : t.rsi_signal === 'Oversold' ? 'positive' : ''],
        ['MACD', t.macd, t.macd_trend, t.macd_trend === 'Bullish' ? 'positive' : 'negative'],
        ['SMA 50', t.sma_50, '', ''], ['SMA 200', t.sma_200, '', ''],
        ['MA Cross', '', t.ma_cross, t.ma_cross?.includes('Golden') ? 'positive' : 'negative'],
        ['Bollinger', '', t.bb_signal, ''],
        ['Volume', fmtLarge(t.current_volume), t.volume_spike ? '⚠️ Spike!' : 'Normal', t.volume_spike ? 'negative' : ''],
    ];
    grid.innerHTML = items.map(([l, v, sig, cls]) => `
        <div class="indicator-card">
            <div class="indicator-label">${l}</div>
            <div class="indicator-value">${v != null ? v : '—'}</div>
            ${sig ? `<div class="indicator-signal ${cls}">${sig}</div>` : ''}
        </div>
    `).join('');
}

function renderStockNews(news) {
    const el = document.getElementById('stock-news');
    if (!el) return;
    if (!news.length) { el.innerHTML = '<div style="color:var(--text-muted);padding:.5rem;">No related news found.</div>'; return; }
    el.innerHTML = news.map(n => {
        const sentClass = n.sentiment_label === 'positive' ? 'pos' : n.sentiment_label === 'negative' ? 'neg' : 'neu';
        return `<div class="news-item"><div class="news-sentiment ${sentClass}"></div><div>
            <div class="news-title"><a href="${n.url}" target="_blank">${n.title}</a></div>
            <div class="news-meta"><span>${n.source||''}</span><span>${n.published_at ? new Date(n.published_at).toLocaleDateString() : ''}</span></div>
        </div></div>`;
    }).join('');
}

// ── Price Chart ──
async function loadPriceChart(ticker, period) {
    try {
        const res = await fetch(`/api/stock/${ticker}/history/${period}`);
        const data = await res.json();
        const hist = data.history || [];
        if (!hist.length) return;

        const labels = hist.map(h => h.date);
        const closes = hist.map(h => h.close);
        const volumes = hist.map(h => h.volume);
        const isUp = closes[closes.length - 1] >= closes[0];
        const lineColor = isUp ? chartColors.green : chartColors.red;

        // Price chart
        const ctx = document.getElementById('price-chart');
        if (!ctx) return;
        if (priceChart) priceChart.destroy();
        priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data: closes, borderColor: lineColor, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4,
                    fill: true, backgroundColor: (context) => {
                        const g = context.chart.ctx.createLinearGradient(0, 0, 0, 350);
                        g.addColorStop(0, lineColor + '30'); g.addColorStop(1, lineColor + '00');
                        return g;
                    }, tension: 0.3,
                }],
            },
            options: { ...defaultChartOptions },
        });

        // Volume chart
        const vctx = document.getElementById('volume-chart');
        if (!vctx) return;
        if (volumeChart) volumeChart.destroy();
        const volColors = hist.map((h, i) => i === 0 ? chartColors.blue + '60' : h.close >= hist[i - 1].close ? chartColors.green + '60' : chartColors.red + '60');
        volumeChart = new Chart(vctx, {
            type: 'bar',
            data: { labels, datasets: [{ data: volumes, backgroundColor: volColors, borderRadius: 2 }] },
            options: { ...defaultChartOptions, scales: { ...defaultChartOptions.scales, y: { ...defaultChartOptions.scales.y, ticks: { ...defaultChartOptions.scales.y.ticks, callback: v => fmtLarge(v) } } } },
        });
    } catch (e) { console.error('Chart error:', e); }
}

function setupPeriodTabs(ticker) {
    document.querySelectorAll('.period-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.period-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            loadPriceChart(ticker, tab.dataset.period);
        });
    });
}

// ── AI Analysis ──
async function loadAnalysis(ticker) {
    const el = document.getElementById('ai-analysis-content');
    if (!el) return;
    el.innerHTML = '<em style="color:var(--text-muted);">🔄 Generating AI analysis...</em>';
    try {
        const res = await fetch(`/api/stock/${ticker}/analysis`);
        const data = await res.json();
        el.textContent = data.analysis || 'Analysis unavailable.';
    } catch (e) { el.textContent = '⚠️ Failed to generate analysis. Please try again.'; }
}
