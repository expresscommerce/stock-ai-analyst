/* ═══════════════════════════════════════════════
   TradingView Lightweight Charts Integration
   ═══════════════════════════════════════════════ */

let tvChart = null;
let candlestickSeries = null;
let volumeSeries = null;
let smaSeries = null;

const chartColors = {
    green: '#10b981',
    red: '#ef4444',
    volumeGreen: 'rgba(16, 185, 129, 0.4)',
    volumeRed: 'rgba(239, 68, 68, 0.4)',
    smaLine: '#2563eb',
    gridColor: '#f8fafc',
    textColor: '#475569',
    borderColor: '#e2e8f0',
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

// ── Parse Date helper for TV scale ──
function parseDateToTime(dateStr) {
    // If it contains space or time colon, parse as Unix timestamp
    const hasTime = dateStr.includes(':') || dateStr.includes(' ') || dateStr.includes('T');
    if (hasTime) {
        return Math.floor(new Date(dateStr).getTime() / 1000);
    }
    // Else return YYYY-MM-DD
    return dateStr.split(' ')[0];
}

// ── Calculate Simple Moving Average ──
function calculateSMA(data, count) {
    const r = [];
    for (let i = 0; i < data.length; i++) {
        if (i < count - 1) continue;
        let sum = 0.0;
        for (let j = 0; j < count; j++) {
            sum += data[i - j].close;
        }
        r.push({
            time: data[i].time,
            value: sum / count
        });
    }
    return r;
}

// ── TradingView Price Chart ──
async function loadPriceChart(ticker, period) {
    try {
        const res = await fetch(`/api/stock/${ticker}/history/${period}`);
        const data = await res.json();
        const hist = data.history || [];
        if (!hist.length) return;

        const container = document.getElementById('tv-chart-container');
        const tooltip = document.getElementById('tv-chart-tooltip');
        if (!container) return;

        // Reset container contents
        container.innerHTML = '';

        // Initialize Lightweight Chart
        tvChart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: container.clientHeight || 420,
            layout: {
                background: { type: 'solid', color: '#ffffff' },
                textColor: chartColors.textColor,
                fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            },
            grid: {
                vertLines: { color: chartColors.gridColor },
                horzLines: { color: chartColors.gridColor },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    width: 1,
                    color: '#94a3b8',
                    style: LightweightCharts.LineStyle.Dashed,
                },
                horzLine: {
                    width: 1,
                    color: '#94a3b8',
                    style: LightweightCharts.LineStyle.Dashed,
                },
            },
            rightPriceScale: {
                borderColor: chartColors.borderColor,
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.25,
                },
            },
            timeScale: {
                borderColor: chartColors.borderColor,
                timeVisible: true,
                secondsVisible: false,
            },
        });

        // 1. Candlestick Series
        candlestickSeries = tvChart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: chartColors.green,
            downColor: chartColors.red,
            borderUpColor: chartColors.green,
            borderDownColor: chartColors.red,
            wickUpColor: chartColors.green,
            wickDownColor: chartColors.red,
        });

        // 2. Volume Series (Overlay)
        volumeSeries = tvChart.addSeries(LightweightCharts.HistogramSeries, {
            color: chartColors.volumeGreen,
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '', // Overlay series
        });

        volumeSeries.priceScale().applyOptions({
            scaleMargins: {
                top: 0.8,
                bottom: 0,
            },
        });

        // 3. SMA 20 Overlay Line
        smaSeries = tvChart.addSeries(LightweightCharts.LineSeries, {
            color: chartColors.smaLine,
            lineWidth: 1.5,
            title: 'SMA 20',
        });

        // Process data
        const chartData = [];
        const volumeData = [];

        hist.forEach((h, i) => {
            const timeVal = parseDateToTime(h.date);
            
            // Build data point
            chartData.push({
                time: timeVal,
                open: h.open,
                high: h.high,
                low: h.low,
                close: h.close
            });

            // Determine volume color matching the candle color
            const isUp = h.close >= h.open;
            volumeData.push({
                time: timeVal,
                value: h.volume,
                color: isUp ? chartColors.volumeGreen : chartColors.volumeRed
            });
        });

        // Set series data
        candlestickSeries.setData(chartData);
        volumeSeries.setData(volumeData);

        // Calculate and set SMA 20
        const smaData = calculateSMA(chartData, 20);
        smaSeries.setData(smaData);

        // Fit time scale to show all data
        tvChart.timeScale().fitContent();

        // ── Hover Tooltip Event Handler ──
        tvChart.subscribeCrosshairMove(param => {
            if (!tooltip) return;

            if (
                param.point === undefined ||
                !param.time ||
                param.point.x < 0 ||
                param.point.x > container.clientWidth ||
                param.point.y < 0 ||
                param.point.y > container.clientHeight
            ) {
                tooltip.style.display = 'none';
                return;
            }

            const candle = param.seriesData.get(candlestickSeries);
            const volume = param.seriesData.get(volumeSeries);

            if (!candle) {
                tooltip.style.display = 'none';
                return;
            }

            const isUp = candle.close >= candle.open;
            const priceColor = isUp ? chartColors.green : chartColors.red;
            const sign = isUp ? '+' : '';
            const diff = candle.close - candle.open;
            const pct = ((diff / candle.open) * 100).toFixed(2);

            let timeString = '';
            if (typeof param.time === 'object') {
                timeString = `${param.time.year}-${String(param.time.month).padStart(2, '0')}-${String(param.time.day).padStart(2, '0')}`;
            } else {
                const date = new Date(param.time * 1000);
                timeString = date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
            }

            tooltip.style.display = 'block';
            tooltip.innerHTML = `
                <span style="font-weight: 700; margin-right: 8px; color: var(--text-primary);">${timeString}</span>
                O: <span style="color: ${priceColor}; font-weight: 600;">${candle.open.toFixed(2)}</span>
                H: <span style="color: ${priceColor}; font-weight: 600;">${candle.high.toFixed(2)}</span>
                L: <span style="color: ${priceColor}; font-weight: 600;">${candle.low.toFixed(2)}</span>
                C: <span style="color: ${priceColor}; font-weight: 600;">${candle.close.toFixed(2)}</span>
                Chg: <span style="color: ${priceColor}; font-weight: 600;">${sign}${diff.toFixed(2)} (${sign}${pct}%)</span>
                Vol: <span style="color: var(--text-secondary); font-weight: 600;">${fmtLarge(volume ? volume.value : 0)}</span>
            `;
        });

        // ── Resize Handler ──
        const resizeObserver = new ResizeObserver(entries => {
            if (entries.length === 0 || !entries[0].contentRect) return;
            const { width, height } = entries[0].contentRect;
            tvChart.applyOptions({ width, height });
        });
        resizeObserver.observe(container);

    } catch (e) {
        console.error('Chart error:', e);
    }
}

function setupPeriodTabs(ticker) {
    document.querySelectorAll('.period-tab').forEach(tab => {
        // Remove old event listener clones if any
        const newTab = tab.cloneNode(true);
        tab.parentNode.replaceChild(newTab, tab);
        
        newTab.addEventListener('click', () => {
            document.querySelectorAll('.period-tab').forEach(t => t.classList.remove('active'));
            newTab.classList.add('active');
            loadPriceChart(ticker, newTab.dataset.period);
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
