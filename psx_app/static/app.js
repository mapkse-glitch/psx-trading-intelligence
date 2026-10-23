// PSX Trading Intelligence Dashboard v1.2 — Frontend Application
const DEFAULT_QUICK_SYMBOLS = [
  "ATRL", "OGDC", "PPL", "PSO", "LUCK", "MLCF", "UBL", "HBL", "SYS", "TRG", "SAZEW", "FFC", "HUBC", "ENGROH"
];

function getSymbolSearchCounts() {
  try {
    const raw = localStorage.getItem("psx_symbol_search_counts_v2");
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    return {};
  }
}

function recordSymbolSearch(sym) {
  if (!sym) return;
  const clean = String(sym).trim().toUpperCase().split("-")[0];
  if (!clean || clean === "ALL" || clean === "CORE36" || clean.length > 10) return;
  try {
    const counts = getSymbolSearchCounts();
    counts[clean] = (counts[clean] || 0) + 1;
    localStorage.setItem("psx_symbol_search_counts_v2", JSON.stringify(counts));
  } catch (e) {
    // ignore storage errors
  }
}

function getQuickSelectSymbols(limit = 14) {
  const counts = getSymbolSearchCounts();
  const pool = new Set([...Object.keys(counts), ...DEFAULT_QUICK_SYMBOLS]);
  const arr = Array.from(pool);
  arr.sort((a, b) => {
    const ca = counts[a] || 0;
    const cb = counts[b] || 0;
    if (cb !== ca) return cb - ca;
    const ia = DEFAULT_QUICK_SYMBOLS.indexOf(a);
    const ib = DEFAULT_QUICK_SYMBOLS.indexOf(b);
    return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
  });
  return arr.slice(0, limit).map((sym) => ({
    symbol: sym,
    count: counts[sym] || 0,
  }));
}

const state = {
  currentView: "overview",
  apiCache: {},
  stagedBatch: null,
  ideas: {
    scope_or_sector: "CORE36",
    direction: "ALL",
    query: "",
  },
  analyst: {
    symbol: "ATRL",
    action: "Evaluate Buy / Hold / Sell",
  },
  top5Filter: { ticker: "ATRL", start_date: "2026-10-01", end_date: null, search: "", end_date_manual: false },
  accTab: { "91404": "dashboard", "91269": "dashboard" },
  accSelectedDate: { "91404": null, "91269": null },
  accDateManual: { "91404": false, "91269": false },
  commitInFlight: false,
  lastSnapshotId: null,
  freshnessStatus: null,
  freshnessInFlight: null,
  // Separate, independent per-sheet filter state for Module C (matching Futures_Analysis.xlsx)
  futures: {
    subtab: "monthly_comparison",
    apply_rolling: true,
    meta: null,
    monthly_comparison: { selected_date: null, days: 30 },
    month_filter: { selected_date: null, days: 30, contract_month: "OCT" },
    symbol_filter: { contract_month: "OCTB", days: 30, base_symbol: "OGDC", selected_date: "ALL" },
    annualized_comparison: { selected_date: null, days: 30 },
    date_filter: { selected_date: null, days: 30 },
    future_symbol_summary: { contract_symbol: "AGHA-OCT" },
    date_summary: { selected_date: null },
  },
  technical: {
    subtab: "core36",
    selectedSymbol: "ATRL",
    search: "",
    signalFilter: "ALL",
  },
  selectedDoc: "CLOUD_HOSTING_AND_SYNC_GUIDE.md",
};

const VIEW_TITLES = {
  overview: "Overview",
  import: "02 • Import and Update Center",
  top5: "03 • Top 5 Volume & Rate Register",
  acc91404: "04 • Account 91404 Performance (THM00601)",
  acc91269: "05 • Account 91269 Performance (THM00601)",
  futures: "06 • Futures Comparison & Annualized Analysis",
  technical: "07 • Technical Analysis, Setup Generator & 36-Ticker",
  reconciliation: "08 • Data Quality & Legacy Reconciliation",
  exports: "09 • Exports & reports",
  settings: "10 • Settings, Rule Versioning & Database Backup",
};

function fmtNum(v, decimals = 2) {
  if (v === null || v === undefined || v === "N/A" || Number.isNaN(Number(v))) return "N/A";
  return Number(v).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// Global display format for calendar dates across the whole dashboard: DD-MM-YYYY
// (e.g. 22-09-2026) — matches the Excel workbooks. Timestamps render as "DD-MM-YYYY HH:MM".
function fmtDate(v) {
  if (!v) return "—";
  const str = String(v);
  if (/^\d{4}-\d{2}-\d{2}$/.test(str)) return `${str.slice(8,10)}-${str.slice(5,7)}-${str.slice(0,4)}`;
  if (/^\d{4}-\d{2}-\d{2}[T ]/.test(str)) {
    const date = new Date(str);
    if (!Number.isNaN(date.getTime())) {
      const parts = new Intl.DateTimeFormat('en-GB', {timeZone:'Asia/Karachi', year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date);
      const get = type => parts.find(p=>p.type===type)?.value;
      return `${get('day')}-${get('month')}-${get('year')} ${get('hour')}:${get('minute')} PKT`;
    }
  }
  return str;
}
function escapeHtml(v) { return String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }

function fmtInt(v) {
  if (v === null || v === undefined || v === "N/A" || Number.isNaN(Number(v))) return "N/A";
  return Math.round(Number(v)).toLocaleString("en-US");
}

function fmtPct(v, isFraction = true) {
  if (v === null || v === undefined || v === "N/A" || Number.isNaN(Number(v))) return "N/A";
  const pct = isFraction ? Number(v) * 100 : Number(v);
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function pnlClass(v) {
  if (v === null || v === undefined || v === "N/A") return "";
  const n = Number(v);
  if (n > 0) return "pos";
  if (n < 0) return "neg";
  return "";
}

function showToast(msg, isError = false) {
  const el = document.getElementById("toastBanner");
  el.textContent = msg;
  el.style.borderColor = isError ? "var(--neg-red)" : "var(--pos-green)";
  el.style.backgroundColor = isError ? "var(--neg-red-bg)" : "var(--pos-green-bg)";
  el.style.color = isError ? "var(--neg-red)" : "var(--pos-green)";
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 5500);
}

function copyTextToClipboard(text, label = "Analysis report") {
  navigator.clipboard.writeText(text).then(() => {
    showToast(`Copied ${label} to clipboard!`);
  }).catch(() => {
    showToast(`Could not copy to clipboard automatically.`, true);
  });
}

async function apiGet(url, useCache = true) {
  if (useCache && state.apiCache[url]) {
    return state.apiCache[url];
  }
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API request failed");
  }
  const data = await res.json();
  if (useCache) {
    state.apiCache[url] = data;
  }
  return data;
}

function clearClientCache() {
  state.apiCache = {};
  renderLatestBadge(state.currentView).catch(() => {});
}

async function refreshCurrentView() {
  const fresh = await verifyWorkspaceFreshness(true);
  clearClientCache();
  await switchView(state.currentView);
  showToast(fresh.status === 'CURRENT' ? "Latest cloud snapshot verified; refreshed current data." : (fresh.status === 'LOCAL' ? "Refreshed local canonical data (cloud sync is not configured)." : fresh.message), !['CURRENT','LOCAL'].includes(fresh.status));
}

async function switchView(view) {
  if (view === "exports") { exportCurrentModule(); return; }
  state.currentView = view;
  toggleMenu(false);
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === view);
  });
  document.getElementById("viewTitle").textContent = VIEW_TITLES[view] || "Dashboard";
  const previous = document.getElementById("viewContainer");
  const container = document.createElement('div');
  container.id = 'viewContainer'; container.className = 'view-container'; container.tabIndex = -1;
  container.innerHTML = '<p class="loading" role="status">Loading workspace…</p>';
  previous.replaceWith(container);

  container.style.animation = "none";
  container.offsetHeight;
  container.style.animation = "";

  renderLatestBadge(view).catch(() => {});
  try {
    if (view === "overview") await renderOverview(container);
    else if (view === "import") await renderImportCenter(container);
    else if (view === "top5") await renderTop5View(container);
    else if (view === "acc91404") await renderAccountView(container, "91404");
    else if (view === "acc91269") await renderAccountView(container, "91269");
    else if (view === "futures") await renderFuturesView(container);
    else if (view === "technical") await renderTechnicalView(container);
    else if (view === "reconciliation") await renderReconciliationView(container);
    else if (view === "exports") await renderExportsView(container);
    else if (view === "settings") await renderSettingsView(container);
  } catch (err) {
    container.innerHTML = `<div class="card"><h3 class="neg">Error loading view</h3><p>${escapeHtml(err.message)}</p></div>`;
  }
}

// ============================================================================
// SHARED COMPONENT BUILDERS:
// 1. Trading Ideas Generator Card
// 2. Automated Technical Analyst Card
// ============================================================================
function buildQuickSelectBarHtml(activeSymbol, onClickFnName) {
  const quickItems = getQuickSelectSymbols(13);
  return quickItems.map((item) => {
    const isAct = item.symbol === activeSymbol;
    const countBadge = item.count > 0 ? `<span class="quick-count">${item.count}</span>` : "";
    return `<button type="button" class="quick-pill ${isAct ? "active" : ""}" onclick="${onClickFnName}('${item.symbol}')" title="${item.count > 0 ? `Searched ${item.count} time(s)` : "Click to analyze"}">${item.symbol}${countBadge}</button>`;
  }).join("");
}

function buildTradingIdeasCardHtml(ideasRes, filtersMeta) {
  if (ideasRes.status === "BLOCKED") return `<section class="card notice" id="tradingIdeasCard"><h3>Setups paused: check dates</h3><p>${escapeHtml(ideasRes.message)}</p><button class="btn btn-secondary" onclick="switchView('settings')">Review date integrity</button></section>`;
  const idState = state.ideas;
  const sectorOptions = (filtersMeta?.sectors || []).map(
    (s) => `<option value="${s}" ${idState.scope_or_sector === s ? "selected" : ""}>Sector: ${s}</option>`
  ).join("");

  return `
    <div class="card card-hero" id="tradingIdeasCard">
      <div class="card-header">
        <div>
          <div class="card-title">
            <span class="badge badge-blue">CARD 1</span>
            1. Trading Ideas Generator — Rule-scored candidates
          </div>
          <div class="card-subtitle">Scans imported historical prices (${ideasRes.candidates_scanned} candidates analyzed) combining 9-Factor Technicals, Module A Top 5 Volume &amp; Module C Futures Basis</div>
        </div>
        <span class="badge badge-green" title="Every number below is computed directly from the canonical SQLite database — 9-Factor Technicals (Module D), Module A Top 5 Volume Register and Module C Futures basis. No external AI/prompts involved.">Pure Data &amp; Analysis • As of ${fmtDate(ideasRes.setups[0] ? ideasRes.setups[0].trade_date : "latest data")}</span>
      </div>

      <div class="filter-bar" style="margin-bottom:14px;">
        <div class="filter-group">
          <label>Stock / Index / Sector:</label>
          <select id="ideasScopeSelect" onchange="runTradingIdeasGenerator()">
            <option value="CORE36" ${idState.scope_or_sector === "CORE36" ? "selected" : ""}>Index: Core 36 Institutional Watchlist</option>
            <option value="TOP5_VOL" ${idState.scope_or_sector === "TOP5_VOL" ? "selected" : ""}>Index: Top 5 Volume Register (23 Tickers)</option>
            <option value="FUTURES" ${idState.scope_or_sector === "FUTURES" ? "selected" : ""}>Index: Deliverable Futures Universe</option>
            <option value="ALL_MARKET" ${idState.scope_or_sector === "ALL_MARKET" ? "selected" : ""}>Index: All PSX Cash Equities (531 Symbols)</option>
            ${sectorOptions}
          </select>
        </div>
        <div class="filter-group">
          <label>Custom Ticker/Sector:</label>
          <input type="text" id="ideasQueryInput" placeholder="e.g. OGDC, Cement, Banking..." value="${idState.query}" style="width:165px;" onkeydown="if(event.key==='Enter')runTradingIdeasGenerator()" />
        </div>
        <div class="filter-group">
          <label>Setup Direction:</label>
          <select id="ideasDirSelect" onchange="runTradingIdeasGenerator()">
            <option value="ALL" ${idState.direction === "ALL" ? "selected" : ""}>All directions</option>
            <option value="LONG" ${idState.direction === "LONG" ? "selected" : ""}>Long / Buy Setups Only</option>
            <option value="SHORT" ${idState.direction === "SHORT" ? "selected" : ""}>Short / Tactical Sell Only</option>
          </select>
        </div>
        <button class="btn btn-primary" onclick="runTradingIdeasGenerator()">⚡ Scan &amp; Generate 5 Setups</button>
      </div>

      <p class="score-disclaimer">Scores rank deterministic technical rules—not a probability of profit. Historical data only; no order is placed.</p>
      <div class="setup-grid">
        ${ideasRes.setups.map((st) => {
          const isLong = st.direction.includes("BUY");
          return `
            <div class="setup-card">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span class="badge ${isLong ? "badge-green" : "badge-red"}">#${st.rank} • ${st.direction}</span>
                  <b style="font-size:15px;margin-left:6px;cursor:pointer;color:var(--text-main);text-decoration:underline;" onclick="triggerAnalystForTicker('${st.symbol}')" title="Click to analyze ${st.symbol} in Card 2">${st.display_label}</b>
                  <span style="font-size:11px;color:var(--text-muted);margin-left:4px;">(${st.sector})</span>
                </div>
                <div style="text-align:right;">
                  <span class="badge badge-blue">Score ${st.setup_score}/100</span>
                </div>
              </div>

              <div class="conviction-bar-bg">
                <div class="conviction-bar-fill" style="width:${st.setup_score}%"></div>
              </div>

              <div class="setup-price-grid">
                <div class="setup-price-cell"><span>Entry</span><b style="color:var(--accent-blue);">${fmtNum(st.entry_price)}</b></div>
                <div class="setup-price-cell"><span>Target 1</span><b class="pos">${fmtNum(st.target_1)}</b></div>
                <div class="setup-price-cell"><span>Target 2</span><b class="pos">${fmtNum(st.target_2)}</b></div>
                <div class="setup-price-cell"><span>Stop-Loss</span><b class="neg">${fmtNum(st.stop_loss)}</b></div>
                <div class="setup-price-cell"><span>R/R (T2)</span><b>${st.risk_reward_t2}</b></div>
              </div>

              <div style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0;">
                <span class="badge badge-blue" title="Wilder RSI(14)">RSI ${st.rsi14}</span>
                <span class="badge badge-blue" title="Average Directional Index — trend strength">ADX ${st.adx14}</span>
                <span class="badge ${st.trend_state.startsWith("Bullish") ? "badge-green" : (st.trend_state.startsWith("Bearish") ? "badge-red" : "badge-blue")}" title="EMA 9 / 21 / 50 alignment">${st.trend_state}</span>
                <span class="badge ${st.momentum_state.startsWith("Rising") ? "badge-green" : "badge-red"}" title="MACD histogram momentum">${st.momentum_state}</span>
                <span class="badge badge-blue" title="Session volume vs 20-day average">Vol ${st.volume_ratio}× avg</span>
              </div>
              <div style="font-size:11.4px;color:var(--warn-amber);background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.3);border-radius:6px;padding:6px 9px;margin-bottom:8px;"><b>⚠ Invalidation:</b> ${st.invalidation}</div>

              <details class="setup-details"><summary>View rationale &amp; background</summary><div style="font-size:12px;color:var(--text-main);">
                <b style="color:var(--accent-blue);">Technical rationale</b>
                <ul style="padding-left:16px;margin-top:3px;">
                  ${st.technical_why.map((line) => `<li>${line}</li>`).join("")}
                </ul>
              </div>

              <div style="font-size:11.6px;color:var(--text-main);">
                <b style="color:var(--pos-green);">Background &amp; liquidity (verify independently)</b>
                <ul style="padding-left:16px;margin-top:3px;">
                  ${st.fundamental_why.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
                </ul>
              </div></details>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function buildAutomatedAnalystCardHtml(analystRes) {
  if (analystRes.status === "BLOCKED" || analystRes.status === "NO_DATA") return `<section class="card notice" id="automatedAnalystCard"><h3>Analysis unavailable</h3><p>${escapeHtml(analystRes.message)}</p></section>`;
  const anState = state.analyst;
  const lat = analystRes.latest || {};
  const sig = lat.signal || {};
  const tl = analystRes.trend_line || {};
  const ws = analystRes.weekly_summary || {};
  const dp = (lat.daily_pivots || {}).classic || {};
  const wp = (lat.weekly_pivots || {}).pivots || {};

  return `
    <div class="card card-hero" id="automatedAnalystCard">
      <div class="card-header">
        <div>
          <div class="card-title">
            <span class="badge badge-green">CARD 2</span>
            2. Automated Technical Analyst — Daily &amp; Weekly Step-by-Step Breakdown
          </div>
          <div class="card-subtitle">Multi-timeframe Daily + Weekly chart analysis, Linear Regression Trend Lines, Support/Resistance, Moving Averages &amp; Momentum</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <span class="badge badge-green" title="Computed directly from daily &amp; weekly OHLCV, Wilder RSI, MACD, Bollinger, EMA stack, ADX and pivot data — no external AI/prompts involved.">Pure Data &amp; Analysis</span>
          <button class="btn btn-primary" onclick="openTickerDeepDive('${analystRes.symbol}')">📈 Open Interactive Chart →</button>
        </div>
      </div>

      <div class="filter-bar" style="margin-bottom:14px;">
        <div class="filter-group">
          <label>Ticker Symbol:</label>
          <input type="text" id="analystTickerInput" value="${anState.symbol}" style="width:105px;font-weight:700;" onkeydown="if(event.key==='Enter')runAutomatedAnalyst()" />
        </div>
        <div class="filter-group" style="flex-wrap:wrap;">
          <label title="Automatically ranks your most-searched symbols first!">Quick Select (Most Searched):</label>
          ${buildQuickSelectBarHtml(anState.symbol, "triggerAnalystForTicker")}
        </div>
        <div class="filter-group">
          <label>Action Mode:</label>
          <select id="analystActionSelect" onchange="runAutomatedAnalyst()">
            <option value="Evaluate Buy / Hold / Sell" ${anState.action === "Evaluate Buy / Hold / Sell" ? "selected" : ""}>Evaluate Buy / Hold / Sell</option>
            <option value="Evaluate Long Entry Setup" ${anState.action === "Evaluate Long Entry Setup" ? "selected" : ""}>Evaluate Long Entry Setup</option>
            <option value="Evaluate Short / Take-Profit" ${anState.action === "Evaluate Short / Take-Profit" ? "selected" : ""}>Evaluate Short / Take-Profit</option>
          </select>
        </div>
        <button class="btn btn-primary" onclick="runAutomatedAnalyst()">🔍 Run Technical Analyst</button>
      </div>

      <div class="grid-4" style="margin-bottom:14px;">
        <div class="kpi-box">
          <div class="kpi-label">${analystRes.display_label} (${analystRes.sector})</div>
          <div class="kpi-value">${fmtNum(lat.close)} PKR</div>
          <div class="kpi-sub ${pnlClass(lat.change_pct)}">Daily Chg: ${fmtPct(lat.change_pct, false)} • 4W Chg: ${fmtPct(ws.change_4w_pct, false)}</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">20D Trend Line &amp; Channel</div>
          <div class="kpi-value ${pnlClass(tl.slope_pkr_per_day)}" style="font-size:16px;">Slope: ${tl.slope_pkr_per_day > 0 ? "+" : ""}${tl.slope_pkr_per_day} PKR/d</div>
          <div class="kpi-sub">Channel: ${fmtNum(tl.lower_channel_support)} – ${fmtNum(tl.upper_channel_resistance)} PKR</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Daily &amp; Weekly Pivots</div>
          <div class="kpi-value" style="font-size:16px;">D-P: ${fmtNum(dp.P)} | W-P: ${fmtNum(wp.P)}</div>
          <div class="kpi-sub">S1: ${fmtNum(dp.S1)} | R1: ${fmtNum(dp.R1)} | R2: ${fmtNum(dp.R2)}</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Step-by-Step Signal Verdict</div>
          <div class="kpi-value ${sig.score > 0 ? "pos" : (sig.score < 0 ? "neg" : "")}">${sig.combined_signal} (${sig.score > 0 ? "+" : ""}${sig.score}/9)</div>
          <div class="kpi-sub">Entry: ${fmtNum(sig.entry_reference)} | SL: ${fmtNum(sig.stop_loss_reference)} | Target: ${fmtNum(sig.target_reference)}</div>
        </div>
      </div>

      ${(() => {
        const ss = analystRes.structure_snapshot || {};
        return `<div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px;">
          ${[
            [ss.weekly_trend, ss.weekly_trend && ss.weekly_trend.startsWith("BULLISH") ? "badge-green" : (ss.weekly_trend && ss.weekly_trend.startsWith("BEARISH") ? "badge-red" : "badge-blue")],
            [ss.price_vs_daily_pivot, ss.price_vs_daily_pivot && ss.price_vs_daily_pivot.startsWith("ABOVE") ? "badge-green" : "badge-red"],
            [ss.ma_alignment, ss.ma_alignment && parseInt(ss.ma_alignment) >= 5 ? "badge-green" : "badge-blue"],
            [ss.rsi_zone, "badge-blue"],
            [ss.adx_strength, "badge-blue"],
            [ss.macd_momentum, ss.macd_momentum && ss.macd_momentum.startsWith("Rising") ? "badge-green" : "badge-red"],
          ].filter(x => x[0]).map(([txt, cls]) => `<span class="badge ${cls}">${txt}</span>`).join("")}
        </div>`;
      })()}

      <div class="grid-2" style="margin-bottom:0;">
        <div class="step-list">
          ${(analystRes.step_by_step_analysis || []).map((st) => `
            <div class="step-item">
              <div class="step-item-hdr">
                <span>${st.step}</span>
                <span class="badge badge-blue">${st.verdict}</span>
              </div>
              <div style="font-size:12px;color:var(--text-main);">${st.detail}</div>
            </div>
          `).join("")}
        </div>

        <div style="display:flex;flex-direction:column;gap:12px;">
          ${(() => {
            const kl = analystRes.key_levels || {};
            const lvl = (name, v, role, tone) => v == null ? "" : `<tr><td>${name}</td><td class="num"><b>${fmtNum(v)}</b></td><td><span class="badge ${tone}">${role}</span></td></tr>`;
            return `<div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Key Levels Map (${analystRes.symbol})</th><th class="num">Price (PKR)</th><th>Role</th></tr></thead>
              <tbody>
                ${lvl("Upper Channel Resistance", kl.upper_channel, "Trend Limit", "badge-blue")}
                ${lvl("Swing High (20D)", kl.swing_high_20d, "Major Resistance", "badge-red")}
                ${lvl("Daily R3", kl.r3, "Resistance", "badge-red")}
                ${lvl("Daily R2", kl.r2, "Resistance", "badge-red")}
                ${lvl("Daily R1", kl.r1, "Resistance", "badge-red")}
                ${lvl("Regression Center (20D)", kl.regression_center, "Fair Value", "badge-blue")}
                ${lvl("Daily Pivot (P)", kl.daily_pivot, "Balance Point", "badge-blue")}
                ${lvl("Weekly Pivot (W-P)", kl.weekly_pivot, "Weekly Balance", "badge-blue")}
                ${lvl("Daily S1", kl.s1, "Support", "badge-green")}
                ${lvl("Daily S2", kl.s2, "Support", "badge-green")}
                ${lvl("Daily S3", kl.s3, "Support", "badge-green")}
                ${lvl("Swing Low (20D)", kl.swing_low_20d, "Major Support", "badge-green")}
                ${lvl("Lower Channel Support", kl.lower_channel, "Trend Limit", "badge-blue")}
              </tbody>
            </table>
          </div>`;
          })()}

          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr><th>Moving Average (Daily &amp; Weekly)</th><th class="num">Level (PKR)</th><th class="num">Dist %</th><th>Alignment Status</th></tr>
              </thead>
              <tbody>
                ${(analystRes.moving_averages_matrix || []).map((m) => `
                  <tr>
                    <td><b>${m.name}</b></td>
                    <td class="num">${fmtNum(m.value)}</td>
                    <td class="num ${pnlClass(m.distance_pct)}">${fmtPct(m.distance_pct, false)}</td>
                    <td><span class="badge ${m.status.includes("BULLISH") ? "badge-green" : "badge-red"}">${m.status}</span></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>

          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr><th>Week</th><th>Period</th><th class="num">Open</th><th class="num">High</th><th class="num">Low</th><th class="num">Close</th><th class="num">Volume</th></tr>
              </thead>
              <tbody>
                ${(ws.recent_weeks || []).slice(-5).reverse().map((w) => `
                  <tr>
                    <td><b>${w.week_key}</b></td>
                    <td>${w.start_date.slice(5)} → ${w.end_date.slice(5)}</td>
                    <td class="num">${fmtNum(w.open)}</td>
                    <td class="num">${fmtNum(w.high)}</td>
                    <td class="num">${fmtNum(w.low)}</td>
                    <td class="num"><b>${fmtNum(w.close)}</b></td>
                    <td class="num">${fmtInt(w.volume)}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function runTradingIdeasGenerator() {
  const scopeEl = document.getElementById("ideasScopeSelect");
  const queryEl = document.getElementById("ideasQueryInput");
  const dirEl = document.getElementById("ideasDirSelect");
  if (scopeEl) state.ideas.scope_or_sector = scopeEl.value;
  if (queryEl) {
    state.ideas.query = queryEl.value;
    if (queryEl.value.trim()) recordSymbolSearch(queryEl.value.trim());
  }
  if (dirEl) state.ideas.direction = dirEl.value;

  const qs = new URLSearchParams({
    scope_or_sector: state.ideas.scope_or_sector,
    direction: state.ideas.direction,
    query: state.ideas.query,
    limit: "5",
  });
  const [ideasRes, filtersMeta] = await Promise.all([
    apiGet(`/api/intelligence/trading-ideas?${qs.toString()}`, false),
    apiGet("/api/intelligence/filters"),
  ]);
  const cardEl = document.getElementById("tradingIdeasCard");
  if (cardEl) {
    cardEl.outerHTML = buildTradingIdeasCardHtml(ideasRes, filtersMeta);
  }
}

async function runAutomatedAnalyst(explicitSymbol = null) {
  const symEl = document.getElementById("analystTickerInput");
  const actEl = document.getElementById("analystActionSelect");

  if (explicitSymbol) {
    state.analyst.symbol = explicitSymbol.trim().toUpperCase();
    if (symEl) symEl.value = state.analyst.symbol;
  } else if (symEl && symEl.value.trim()) {
    state.analyst.symbol = symEl.value.trim().toUpperCase();
  }
  if (actEl) state.analyst.action = actEl.value;

  recordSymbolSearch(state.analyst.symbol);

  const res = await apiGet(
    `/api/intelligence/automated-analyst/${encodeURIComponent(state.analyst.symbol)}?action=${encodeURIComponent(state.analyst.action)}`,
    false
  );
  const cardEl = document.getElementById("automatedAnalystCard");
  if (cardEl) {
    cardEl.outerHTML = buildAutomatedAnalystCardHtml(res);
  }
}

async function triggerAnalystForTicker(sym) {
  const clean = (sym || "ATRL").trim().toUpperCase();
  state.analyst.symbol = clean;
  recordSymbolSearch(clean);
  const cardEl = document.getElementById("automatedAnalystCard");
  if (cardEl) {
    await runAutomatedAnalyst(clean);
    if (state.currentView === "technical" && state.technical.subtab === "deep_dive") {
      state.technical.selectedSymbol = clean;
      await renderTechnicalView(document.getElementById("viewContainer"));
    }
  } else {
    openTickerDeepDive(clean);
  }
}

// ============================================================================
// 01. OVERVIEW DASHBOARD
// ============================================================================
async function renderOverview(container) {
  const ticket = beginViewRender(container);
  const [data, status] = await Promise.all([apiGet('/api/overview?brief=true'), apiGet('/api/system/status', false)]);
  const sys = data.system, a = data.account_91404, b = data.account_91269;
  const cloud = status.cloud_sync;
  const source = status.dates.sources;
  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `
    <section class="workspace-intro"><div><div class="eyebrow">PSX / TRADING WORKSPACE</div><h1>A clearer view of your market.</h1><p>Review your accounts, compare futures and keep imported data in one place.</p></div><button class="btn btn-primary" onclick="switchView('import')">+ Import daily files</button></section>
    ${!status.dates.ok ? `<section class="notice card" role="alert"><h3>Date integrity needs attention</h3><p>${escapeHtml(status.dates.message)}</p><button class="btn btn-secondary" onclick="switchView('settings')">Review dates</button></section>` : ''}
    <div class="trust-strip"><span><b>Source</b> Imported end-of-day data</span><span><b>Cash as of</b> ${fmtDate(source.cash?.latest_date)}</span><span><b>Futures as of</b> ${fmtDate(source.futures?.latest_date)}</span><span><b>Cloud</b> ${escapeHtml(cloud.health)}</span></div>
    <div class="section-heading"><h2>Your accounts</h2><span>YTD within imported coverage · PKR · separate ledgers</span></div>
    <div class="grid-2 account-overview">
      ${[[a,'91404'],[b,'91269']].map(([acc,id])=>`<section class="card account-card"><div class="account-card-top"><span class="eyebrow">ACCOUNT ${id}</span><button class="text-button" onclick="switchView('acc${id}')">Open account →</button></div><div class="metric-caption">Net P&amp;L</div><div class="account-value ${pnlClass(acc.ytd.net_pnl)}">${fmtNum(acc.ytd.net_pnl)} <small>PKR</small></div><div class="account-footer"><span>Latest trading day <b>${fmtDate(acc.latest_trading_day)}</b></span><span>${fmtInt(acc.trading_days_count)} days · ${fmtInt(acc.symbols_count)} symbols</span></div></section>`).join('')}
    </div>
    <div class="section-heading"><h2>Continue your analysis</h2><span>Detailed tools, without the clutter</span></div>
    <div class="workflow-grid">
      <section class="card workflow-card"><span class="eyebrow">01 / VOLUME</span><h3>Top 5 register</h3><p>${fmtInt(sys.top5.records)} ranked rows across ${fmtInt(sys.top5.tickers)} tickers. Latest ${fmtDate(sys.top5.max_date)}.</p><button class="btn btn-secondary" onclick="switchView('top5')">Explore volume →</button></section>
      <section class="card workflow-card"><span class="eyebrow">02 / FUTURES</span><h3>Compare cash &amp; futures</h3><p>Same-date basis and annualized spreads. Each worksheet keeps its own filters.</p><button class="btn btn-secondary" onclick="switchView('futures')">Compare futures →</button></section>
      <section class="card workflow-card"><span class="eyebrow">03 / TECHNICALS</span><h3>Research your next setup</h3><p>Core 36 watchlist, indicator history and rule-based scores—not win probabilities.</p><button class="btn btn-secondary" onclick="switchView('technical')">Open technicals →</button></section>
    </div>
    <section class="card utility-card"><div><h3>Keep your data dependable</h3><p>Integrity, reference reconciliation and cloud sync are separate checks. No blanket “100% reconciled” claim.</p></div><div class="action-row"><button class="btn btn-secondary" onclick="switchView('reconciliation')">Check data quality</button><button class="btn btn-secondary" onclick="switchView('settings')">Backups &amp; settings</button></div></section>
    <p class="workspace-note">Historical analysis only. This workspace does not supply live quotes or execute trades. Dates: DD-MM-YYYY · Times: Asia/Karachi.</p>`;
}

// ============================================================================
// 02. IMPORT AND UPDATE CENTER
// ============================================================================
// Emergency-only "Push Snapshot" button: hidden whenever auto-sync is healthy
// (every successful upload Commit pushes automatically). It reappears only if a
// push actually fails, or when GitHub sync is not configured yet (LOCAL mode).
function renderSyncButtons(cs) {
  if (cs.backend === 'turso') return `<span class="badge ${cs.health==='ACTIVE'?'badge-green':'badge-red'}">${escapeHtml(cs.health)}</span><button class="btn btn-secondary" onclick="reloadCloudData()">Refresh database views</button><a class="btn btn-secondary" href="https://app.turso.tech" target="_blank" rel="noopener noreferrer">Turso &amp; backups</a>${cs.last_error?`<p class="neg">${escapeHtml(cs.last_error)}</p>`:''}`;
  return `<a class="btn btn-secondary" href="/api/cloud-sync/download-snapshot" download>Download current snapshot</a>
    <span class="badge ${cs.health==='ACTIVE'?'badge-green':'badge-amber'}">${escapeHtml(cs.health || 'UNKNOWN')}</span>
    ${cs.health!=='ACTIVE'?`<button class="btn btn-secondary" onclick="triggerCloudSyncNow()">Retry cloud save</button>`:''}
    ${cs.enabled?`<button class="btn btn-secondary" onclick="reloadCloudData()">Reload cloud data</button>`:''}
    ${cs.last_error?`<p class="neg">${escapeHtml(cs.last_error)}</p>`:''}
    ${cs.pending_local_changes?'<p class="neg">Local changes are not confirmed in the cloud. Download this snapshot before closing.</p>':''}`;
}

async function renderImportCenter(container) {
  const ticket = beginViewRender(container);
  const hist = await apiGet("/api/imports/history", false);
  const cs = hist.cloud_sync || {};

  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `
    <div class="card card-hero">
      <div class="card-header">
        <div>
          <div class="card-title">Data storage &amp; cloud sync</div>
          <div class="card-subtitle">Status: <b class="${cs.health === "ACTIVE" ? "pos" : "warn"}">${cs.provider || "Local Mode"}</b>${cs.last_pull ? ` • Last pull: <span style="color:var(--text-muted);">${fmtDate(cs.last_pull)}</span>` : ""}${cs.last_push ? ` • Last verified cloud save: <span style="color:var(--text-muted);">${fmtDate(cs.last_push)}</span>` : ""}</div>
          ${cs.last_error ? `<div style="margin-top:6px;font-size:12px;color:var(--neg-red);background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.35);border-radius:6px;padding:8px 10px;"><b>⚠ Sync Issue:</b> ${cs.last_error}</div>` : ""}
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          ${renderSyncButtons(cs)}
        </div>
      </div>
      <div style="font-size:12px;color:var(--text-main);">
        <b>Where your uploaded data is saved:</b> ${cs.backend==='turso' ? 'Prices, account records, settings and audit records are committed directly to Turso. Upload pieces and parsed staging are stored temporarily in Turso so another Vercel worker can finish the import. Successful commit removes parsed staging; incomplete uploads expire after 24 hours and are swept during subsequent staging. Original source files are not permanently archived by this dashboard—keep your originals and independent backups. No full database is downloaded to Vercel or pushed to GitHub.' : 'Local SQLite mode: use an independent backup and verify the configured persistence provider.'}

      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Manual File Upload &amp; Staging Center</div>
          <div class="card-subtitle">Supports single/multiple Ticker .TXT, TradeLog .TXT/.CSV/.XLSX, Cash/Futures OHLCV (2026.xlsx, 2026F.xlsx, INDEX.xlsx), or .ZIP archives</div>
        </div>
      </div>

      <div class="dropzone" id="uploadDropzone"
        onclick="document.getElementById('fileUploadInput').click()"
        ondragenter="event.preventDefault();event.stopPropagation();this.classList.add('drag-active')"
        ondragover="event.preventDefault();event.stopPropagation();this.classList.add('drag-active')"
        ondragleave="event.preventDefault();event.stopPropagation();this.classList.remove('drag-active')"
        ondrop="event.preventDefault();event.stopPropagation();this.classList.remove('drag-active');handleStageFiles(event.dataTransfer.files)">
        <h3 style="margin-bottom:6px;color:var(--accent-blue);">Click to Select Files or Drag &amp; Drop Files Here</h3>
        <p style="color:var(--text-muted);font-size:12px;">
          Drag any <b>.txt, .csv, .xlsx, .xls, .zip</b> file(s) directly onto this box, or click to browse • Files are staged and validated first before modifying your canonical database.
        </p>
        <input type="file" id="fileUploadInput" multiple accept=".txt,.csv,.xlsx,.xls,.zip" style="display:none" onchange="handleStageFiles(this.files)" />
      </div>

      <div id="stagedPreviewArea"></div>
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">Import &amp; Update Audit History</div>
        <div class="card-subtitle">Complete transactional log of all historical migrations and incremental user imports</div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Batch ID</th>
              <th>Status</th>
              <th>File Name(s)</th>
              <th>Source Label</th>
              <th>Timestamp (PKT)</th>
              <th class="num">Files</th>
              <th class="num">Rows Read</th>
              <th class="num">New Records</th>
              <th class="num">Duplicates Ignored</th>
              <th class="num">Revisions</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${hist.batches.map((b) => `
              <tr>
                <td class="num">#${b.id} <span style="color:var(--text-muted);font-size:10.5px;">(${b.batch_uuid.slice(0, 8)})</span></td>
                <td><span class="badge ${b.status === "COMMITTED" ? "badge-green" : (b.status === "STAGED" ? "badge-amber" : "badge-red")}">${b.status}</span></td>
                <td style="max-width:230px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:11px;" title="${(b.filenames || []).join(", ")}">
                  ${(b.filenames || []).slice(0, 2).join(", ") || "—"}${(b.filenames || []).length > 2 ? ` <span style="color:var(--accent-blue);">+${(b.filenames || []).length - 2} more</span>` : ""}
                </td>
                <td><b>${b.source_label}</b></td>
                <td>${fmtDate(b.committed_at || b.created_at || "")}</td>
                <td class="num">${b.files_count}</td>
                <td class="num">${fmtInt(b.rows_read)}</td>
                <td class="num pos">${fmtInt(b.new_records)}</td>
                <td class="num">${fmtInt(b.duplicates_ignored)}</td>
                <td class="num">${fmtInt(b.revisions_count)}</td>
                <td style="white-space:nowrap;">
                  ${b.status === "STAGED" ? `
                    ${b.staged_resumable ? `<button class="btn btn-success" style="padding:3px 8px;font-size:10.5px;" onclick="resumeStagedBatch('${b.batch_uuid}')" title="Commit this staged batch into the database">✓ Commit Now</button> ` : `<span style="color:var(--warn-amber);font-size:10.5px;" title="The temporary staging files for this batch no longer exist on the running server (cold restart). Please Discard and re-upload the file.">⚠ Expired</span> `}
                    <button class="btn btn-secondary" style="padding:3px 8px;font-size:10.5px;" onclick="discardStagedBatch('${b.batch_uuid}')" title="Remove this uncommitted staged entry from the audit list">✕ Discard</button>
                  ` : ""}
                  ${b.status === "COMMITTED" ? `<span style="color:var(--pos-green);font-size:10.5px;" title="Canonical data — protected">✓ Safe</span>` : ""}
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function fmtBytes(n) {
  if (!isFinite(n)) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = n, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

function _newUploadId() {
  if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
  return `u-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`.replace(/[^a-zA-Z0-9-]/g, "").padEnd(12, "x");
}

async function _uploadOneChunk(file, uid, idx, total) {
  const CHUNK = 3 * 1024 * 1024;
  const blob = file.slice(idx * CHUNK, (idx + 1) * CHUNK);
  const url = `/api/imports/upload-chunk?upload_id=${encodeURIComponent(uid)}&name=${encodeURIComponent(file.name)}&idx=${idx}&total=${total}`;
  const res = await fetch(url, { method: "POST", body: blob });
  if (!res.ok) {
    let detail = `Chunk upload failed (HTTP ${res.status})`;
    try { const ej = await res.json(); if (ej.detail) detail = ej.detail; } catch (_) {}
    let e = new Error(`Uploading "${file.name}" — ${detail}`);
    e.fatal = true;
    throw e;
  }
}

async function uploadFilesChunked(filesArr, previewEl) {
  const CHUNK = 3 * 1024 * 1024;
  const uploads = [];
  let totalChunks = 0;
  const filesInfo = filesArr.map((f) => {
    const plan = { file: f, uid: _newUploadId(), total: Math.max(1, Math.ceil(f.size / CHUNK)) };
    totalChunks += plan.total;
    uploads.push({ upload_id: plan.uid, name: f.name, total_chunks: plan.total });
    return plan;
  });
  let sent = 0;
  const MAX_ROUNDS = 3;
  for (let round = 0; round < MAX_ROUNDS; round++) {
    let missingOnly = null;
    if (round > 0) {
      // Ask the server which pieces it is still missing (covers instance switches).
      const chk = await fetch("/api/imports/stage-chunked", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uploads }),
      });
      if (chk.ok) return await chk.json();
      if (chk.status === 409) {
        try {
          const ej = await chk.json();
          const det = ej.detail || {};
          missingOnly = {};
          for (const u of det.uploads || []) for (const ix of u.missing || []) missingOnly[`${u.upload_id}:${ix}`] = true;
        } catch (_) {}
      } else {
        let detail = `Staging failed (HTTP ${chk.status})`;
        try { const ej = await chk.json(); detail = typeof ej.detail === "string" ? ej.detail : JSON.stringify(ej.detail); } catch (_) {}
        throw new Error(detail);
      }
    }
    for (const plan of filesInfo) {
      for (let i = 0; i < plan.total; i++) {
        const key = `${plan.uid}:${i}`;
        if (missingOnly && !missingOnly[key]) continue;
        sent += 1;
        previewEl.innerHTML = `<div class="skeleton-card">Uploading <b>${plan.file.name}</b> piece ${i + 1}/${plan.total} (${sent} sent)...<div style="margin-top:6px;font-size:11px;color:var(--text-muted);">Large files are automatically split into safe ~3 MB pieces for Vercel to stay below the request size limit.</div></div>`;
        await _uploadOneChunk(plan.file, plan.uid, i, plan.total);
      }
    }
  }
  // Final assembly attempt
  const res = await fetch("/api/imports/stage-chunked", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uploads }),
  });
  if (!res.ok) {
    let detail = `Staging failed (HTTP ${res.status})`;
    try { const ej = await res.json(); detail = typeof ej.detail === "string" ? ej.detail : JSON.stringify(ej.detail); } catch (_) {}
    throw new Error(detail);
  }
  return await res.json();
}

async function handleStageFiles(fileList) {
  if (!fileList || fileList.length === 0) return;
  const previewEl = document.getElementById("stagedPreviewArea");
  const filesArr = [...fileList];
  const totalBytes = filesArr.reduce((s, f) => s + f.size, 0);
  previewEl.innerHTML = `<div class="skeleton-card">Analyzing and staging ${filesArr.length} file(s) (${fmtBytes(totalBytes)})...</div>`;

  try {
    let manifest;
    // Vercel rejects any single request body over ~4.5 MB. Whenever any file is
    // near that limit, slice EVERY file into small pieces and upload chunk-by-chunk;
    // the server reassembles them and produces the exact same staged manifest.
    const needsChunking = filesArr.some((f) => f.size > 3 * 1024 * 1024);
    if (needsChunking) {
      manifest = await uploadFilesChunked(filesArr, previewEl);
    } else {
      const fd = new FormData();
      for (const f of filesArr) fd.append("files", f);
      const res = await fetch("/api/imports/stage", { method: "POST", body: fd });
      if (!res.ok) {
        let detail = `Staging failed (HTTP ${res.status} ${res.statusText || ""})`;
        try { const ej = await res.json(); if (ej.detail) detail = ej.detail; } catch (_) {}
        throw new Error(detail.trim());
      }
      manifest = await res.json();
    }
    state.stagedBatch = manifest;
    const skippedFiles = manifest.files.filter(f => !f.rows_accepted);
    const hasImportableRows = manifest.rows_accepted > 0;

    previewEl.innerHTML = `
      <div class="card card-hero">
        <div class="card-header">
          <div>
            <div class="card-title" style="color:var(--accent-blue);">Staged Import Preview — ${!hasImportableRows ? 'No Importable Rows' : skippedFiles.length ? 'Review Skipped Files' : 'Ready to Commit'}</div>
            <div class="card-subtitle">Batch UUID: ${manifest.batch_uuid} • ${manifest.files_count} file(s) analyzed</div>
          </div>
          <button class="btn btn-success" ${hasImportableRows ? '' : 'disabled'} onclick="commitStagedBatch('${manifest.batch_uuid}')">
            ✓ Import and Update Canonical Database
          </button>
        </div>

        ${skippedFiles.length ? `<div class="notice" role="alert"><b>Not imported: ${skippedFiles.map(f => escapeHtml(f.filename)).join(', ')}</b><p>These files have zero accepted rows. They are not duplicates and will not be added by clicking Import. Review the format or parser issues below.</p></div>` : ''}

        <div class="grid-4">
          <div class="kpi-box"><div class="kpi-label">Rows Read</div><div class="kpi-value">${fmtInt(manifest.rows_read)}</div></div>
          <div class="kpi-box"><div class="kpi-label">New Canonical Records</div><div class="kpi-value pos">${fmtInt(manifest.new_records)}</div></div>
          <div class="kpi-box"><div class="kpi-label">Exact Duplicates Ignored</div><div class="kpi-value">${fmtInt(manifest.duplicates_ignored)}</div></div>
          <div class="kpi-box"><div class="kpi-label">Source Revisions Detected</div><div class="kpi-value">${fmtInt(manifest.revisions_count)}</div></div>
        </div>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Detected Schema</th>
                <th>Module</th>
                <th>Dates Detected</th>
                <th>Accounts</th>
                <th class="num">Rows Read</th>
                <th class="num">New</th>
                <th class="num">Duplicates</th>
                <th class="num">Revisions</th>
              </tr>
            </thead>
            <tbody>
              ${manifest.files.map((f) => `
                <tr>
                  <td><b>${f.filename}</b></td>
                  <td><span class="badge ${f.rows_accepted ? 'badge-blue' : 'badge-amber'}">${f.file_type}${f.rows_accepted ? '' : ' — SKIPPED'}</span>
                    ${(f.issues || []).filter(i => i.issue_type === 'UNRECOGNIZED_SCHEMA' || i.severity === 'ERROR').map(i => `<div class="neg">${escapeHtml(i.message)}</div>`).join('')}</td>
                  <td>${f.module}</td>
                  <td>${(f.detected_dates || []).join(" → ") || "—"}</td>
                  <td>${(f.detected_accounts || []).join(", ") || "—"}</td>
                  <td class="num">${fmtInt(f.rows_read)}</td>
                  <td class="num pos">${fmtInt(f.new_records)}</td>
                  <td class="num">${fmtInt(f.duplicates_ignored)}</td>
                  <td class="num">${fmtInt(f.revisions_count)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    previewEl.innerHTML = `<div class="card neg">Failed to stage files: ${err.message}</div>`;
  }
}

async function commitStagedBatch(batchUuid) {
  if (state.commitInFlight) return;
  state.commitInFlight = true;
  const buttons = [...document.querySelectorAll('button')].filter(b => (b.getAttribute('onclick') || '').includes('commitStagedBatch'));
  buttons.forEach(b => {b.disabled = true; b.dataset.originalLabel = b.textContent; b.textContent = 'Importing & verifying cloud save…';});
  const started = performance.now();
  try {
    const res = await fetch("/api/imports/commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch_uuid: batchUuid, allow_revisions: true }),
    });
    if (!res.ok) {
      let detail = `Commit failed (HTTP ${res.status})`;
      try { const ej = await res.json(); if (ej.detail) detail = ej.detail; } catch (_) {}
      throw new Error(detail);
    }
    const committed = await res.json();
    state.stagedBatch = null;
    clearClientCache();
    let note;
    if (committed.cloud_sync?.backend === 'turso' && committed.cloud_sync.saved) {
      note = 'Saved directly to Turso. No GitHub snapshot upload is needed.';
    } else if (committed.cloud_sync && committed.cloud_sync.pushed) {
      note = ` & auto-pushed to GitHub (${committed.cloud_sync.commit_sha.slice(0, 7)})! Cloud save confirmed; already-open workers must reload cloud data before editing.`;
    } else if (committed.cloud_sync && committed.cloud_sync.error) {
      note = `.\n⚠ GitHub push FAILED: ${committed.cloud_sync.error}\nCloud save is NOT confirmed. Local data on Vercel is temporary. Download the snapshot now and retry after fixing the issue.`;
    } else if (committed.status === "ALREADY_COMMITTED") {
      note = `Batch already committed earlier — no records were added again.`;
    } else {
      note = `.\nCommitted and saved to the active database on this app instance.`;
    }
    showToast(
      `${committed.status === "ALREADY_COMMITTED" ? "Import already completed" : `Import & Update Complete: ${committed.new_records} new records added, ${committed.duplicates_ignored} duplicates safely skipped`}. ${committed.verified_date_repairs || 0} source-verified date repairs. ${note} (${((performance.now()-started)/1000).toFixed(1)}s)`, Boolean(committed.cloud_sync && !committed.cloud_sync.pushed && !committed.cloud_sync.saved)
    );
    await renderImportCenter(document.getElementById("viewContainer"));
  } catch (err) {
    showToast(`Commit error: ${err.message}`, true);
  } finally {
    state.commitInFlight = false;
    buttons.forEach(b => {b.disabled = false; b.textContent = b.dataset.originalLabel;});
  }
}

async function resumeStagedBatch(batchUuid) {
  await commitStagedBatch(batchUuid);
}

async function discardStagedBatch(batchUuid) {
  try {
    const res = await fetch("/api/imports/discard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch_uuid: batchUuid, allow_revisions: true }),
    });
    if (!res.ok) {
      let detail = `Discard failed (HTTP ${res.status})`;
      try { const ej = await res.json(); if (ej.detail) detail = ej.detail; } catch (_) {}
      throw new Error(detail);
    }
    clearClientCache();
    state.stagedBatch = null;
    showToast(`Staged batch ${batchUuid.slice(0, 8)} discarded from the audit list (no data was added). You can safely re-upload the source files.`);
    await renderImportCenter(document.getElementById("viewContainer"));
  } catch (err) {
    showToast(`Discard error: ${err.message}`, true);
  }
}

// ============================================================================
// 03. MODULE A: TOP 5 VOLUME & RATE REGISTER
// ============================================================================
async function renderTop5View(container) {
  const ticket = beginViewRender(container);
  const f = state.top5Filter;

  async function fetchRegisterPass() {
    const qs = new URLSearchParams();
    if (f.ticker && f.ticker !== "ALL") qs.set("ticker", f.ticker);
    if (f.start_date) qs.set("start_date", f.start_date);
    if (f.end_date_manual && f.end_date) qs.set("end_date", f.end_date);
    if (f.search) qs.set("search", f.search);
    return apiGet(`/api/top5/register?${qs.toString()}`, false);
  }

  // Always fetch FRESH data (never stale cache) — new imports appear instantly
  // when switching from the Import Center to this view, without a page refresh.
  let data = await fetchRegisterPass();
  const latestAvailable = data.latest_date;

  // The "To Date" filter auto-points to the newest date in the database
  // (e.g. if 19-Oct data was just imported, To Date instantly becomes 19-Oct),
  // unless the user deliberately pinned a custom end date.
  if (!f.end_date_manual && latestAvailable && f.end_date !== latestAvailable) {
    f.end_date = latestAvailable;
  }

  const trendTicker = f.ticker && f.ticker !== "ALL" ? f.ticker : "ATRL";
  const trendData = await apiGet(`/api/top5/trend/${trendTicker}`);

  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `
    <div class="filter-bar">
      <div class="filter-group">
        <label>Ticker:</label>
        <select id="top5TickerSelect" onchange="updateTop5Filter()">
          <option value="ALL" ${f.ticker === "ALL" ? "selected" : ""}>ALL 23 TICKERS</option>
          ${data.available_tickers.map((t) => `<option value="${t}" ${f.ticker === t ? "selected" : ""}>${t}</option>`).join("")}
        </select>
      </div>
      <div class="filter-group">
        <label>From Date:</label>
        <input type="date" id="top5StartInput" value="${f.start_date}" onchange="updateTop5Filter()" />
      </div>
      <div class="filter-group">
        <label>To Date:</label>
        <input type="date" id="top5EndInput" value="${f.end_date}" onchange="state.top5Filter.end_date_manual=true;updateTop5Filter()" />
        <span class="badge ${f.end_date_manual ? "badge-amber" : "badge-green"}" style="font-size:10px;" title="Latest date available in the database: ${latestAvailable}.${f.end_date_manual ? " You pinned a custom end date — click Reset to return to automatic latest-date tracking." : " Auto-tracking the latest available date."}">
          ${f.end_date_manual ? `Pinned (latest: ${fmtDate(latestAvailable)})` : `Auto → Latest: ${fmtDate(latestAvailable)}`}
        </span>
        ${f.end_date_manual ? `<button class="btn btn-secondary" style="padding:3px 8px;font-size:10.5px;" title="Return To Date to the latest available data (${latestAvailable})" onclick="resetTop5EndToLatest()">↺ Reset to Latest</button>` : ""}
      </div>
      <div class="filter-group">
        <label>Search:</label>
        <input type="text" id="top5SearchInput" placeholder="Ticker or date..." value="${f.search}" oninput="scheduleTop5Search(this.value)" />
      </div>
      <div style="margin-left:auto;display:flex;gap:8px;">
        <a class="btn btn-primary" href="/api/exports/generate/top5_xlsx" download>⬇ Export Top 5 Workbook (.xlsx)</a>
        <a class="btn btn-secondary" href="/api/exports/generate/csv_top5" download>CSV</a>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">${trendData.ticker} — Top 5 Volume &amp; Rank-1 Rate Trend (${trendData.trading_days} Trading Sessions)</div>
          <div class="card-subtitle">Chronological progression across imported trading dates • Latest available data: ${latestAvailable ? fmtDate(latestAvailable) : "N/A"}</div>
        </div>
      </div>
      ${renderTop5SvgChart(trendData.trend)}
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Top 5 Volume &amp; Rate Register Blocks (${data.blocks_count} Ticker-Date Blocks • ${data.total_rows} Rows)</div>
          <div class="card-subtitle">Date Header Format: DD-MM-YYYY • Visible Columns: Rank, Rate, Volume, Trades (Sorted by Volume Descending)</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,350px),1fr));gap:14px;">
        ${data.date_blocks.slice(0, 60).map((blk) => `
          <div style="background:var(--bg-card-alt);border:1px solid var(--border-color);border-radius:8px;padding:12px;">
            <div style="font-weight:700;color:var(--accent-blue);margin-bottom:8px;font-size:13px;">
              ${blk.title}
            </div>
            <table class="data-table">
              <thead>
                <tr><th>Rank</th><th class="num">Rate</th><th class="num">Volume</th><th class="num">Trades</th></tr>
              </thead>
              <tbody>
                ${blk.rows.map((r) => {
                  const pct = blk.max_volume > 0 ? Math.round((r.volume / blk.max_volume) * 92) : 0;
                  return `
                    <tr>
                      <td><b>${r.rank}</b></td>
                      <td class="num">${fmtNum(r.rate)}</td>
                      <td class="num vol-bar-cell">
                        <div class="vol-bar-fill" style="width:${pct}%"></div>
                        <span class="vol-bar-text">${fmtInt(r.volume)}</span>
                      </td>
                      <td class="num">${fmtInt(r.trades)}</td>
                    </tr>
                  `;
                }).join("")}
              </tbody>
            </table>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function updateTop5Filter() {
  state.top5Filter.ticker = document.getElementById("top5TickerSelect").value;
  if (state.top5Filter.ticker && state.top5Filter.ticker !== "ALL") {
    recordSymbolSearch(state.top5Filter.ticker);
  }
  state.top5Filter.start_date = document.getElementById("top5StartInput").value;
  state.top5Filter.end_date = document.getElementById("top5EndInput").value;
  const srchEl = document.getElementById("top5SearchInput");
  if (srchEl) state.top5Filter.search = srchEl.value;
  renderTop5View(document.getElementById("viewContainer"));
}

function resetTop5EndToLatest() {
  state.top5Filter.end_date_manual = false;
  renderTop5View(document.getElementById("viewContainer"));
}

// Debounce free-text typing so the app NEVER auto-submits in the middle of a word.
// The table only refreshes after the user pauses, and keyboard focus is restored.
let top5SearchTimer = null;
function scheduleTop5Search(val) {
  state.top5Filter.search = val;
  clearTimeout(top5SearchTimer);
  top5SearchTimer = setTimeout(async () => {
    const typedValue = val;
    await renderTop5View(document.getElementById("viewContainer"));
    const el = document.getElementById("top5SearchInput");
    if (el && el.value === typedValue) {
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    }
  }, 700);
}

function renderTop5SvgChart(trend) {
  if (!trend || trend.length === 0) return `<p>No trend data available.</p>`;
  const w = 860, h = 190, padL = 55, padR = 55, padT = 20, padB = 30;
  const maxVol = Math.max(...trend.map((d) => d.top5_total_volume), 1);
  const rates = trend.map((d) => d.rank1_rate).filter((v) => v != null);
  const minRate = Math.min(...rates, 0) * 0.98;
  const maxRate = Math.max(...rates, 1) * 1.02;

  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  const stepX = trend.length > 1 ? plotW / (trend.length - 1) : plotW;

  const bars = trend.map((d, i) => {
    const x = padL + i * stepX;
    const bh = (d.top5_total_volume / maxVol) * plotH;
    const y = padT + plotH - bh;
    return `<rect x="${x - 4}" y="${y}" width="8" height="${bh}" fill="rgba(56,189,248,0.35)" rx="2"><title>${fmtDate(d.trade_date)}: Top 5 Vol=${fmtInt(d.top5_total_volume)}, Rank1 Rate=${fmtNum(d.rank1_rate)}</title></rect>`;
  }).join("");

  const pts = trend.map((d, i) => {
    const x = padL + i * stepX;
    const y = padT + plotH - ((d.rank1_rate - minRate) / (maxRate - minRate || 1)) * plotH;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return `
    <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:190px;background:#070c18;border-radius:7px;border:1px solid var(--border-color);">
      ${bars}
      <polyline fill="none" stroke="#10b981" stroke-width="2.2" points="${pts}" />
      <text x="${padL}" y="14" fill="#38bdf8" font-size="10">Bars: Top 5 Total Volume (Max ${fmtInt(maxVol)})</text>
      <text x="${w - 230}" y="14" fill="#10b981" font-size="10">Line: Rank 1 Rate (${fmtNum(minRate)} – ${fmtNum(maxRate)} PKR)</text>
      <text x="${padL}" y="${h - 8}" fill="#94a3b8" font-size="10">${fmtDate(trend[0].trade_date)}</text>
      <text x="${w - padR - 55}" y="${h - 8}" fill="#94a3b8" font-size="10">${fmtDate(trend[trend.length - 1].trade_date)}</text>
    </svg>
  `;
}

// ============================================================================
// 04 & 05. MODULE B: ACCOUNT 91404 & ACCOUNT 91269 PERFORMANCE
// ============================================================================
async function renderAccountView(container, accountId) {
  const ticket = beginViewRender(container);
  const selDate = state.accDateManual[accountId] ? state.accSelectedDate[accountId] : null;
  const qs = selDate ? `?selected_date=${encodeURIComponent(selDate)}` : "";
  const rep = await apiGet(`/api/accounts/${accountId}${qs}`);
  const activeTab = state.accTab[accountId] || "dashboard";
  state.accSelectedDate[accountId] = rep.selected_date;

  const tDates = rep.trading_dates || rep.available_dates || [];
  if (!tDates.length) {
    if (!currentViewRender(container, ticket)) return;
    container.innerHTML = `<section class="card"><h3>Account ${escapeHtml(accountId)}</h3><p>No trading records have been imported for this account yet. The other account remains separate.</p><p>Import your source files or restore a verified backup to begin.</p><button class="btn btn-primary" onclick="switchView('import')">Import account files</button></section>`;
    return;
  }
  const tabs = [
    ["dashboard", "Dashboard"],
    ["daily_summary", `Daily Summary (${tDates.length}d)`],
    ["daily_detail", `Daily Detail (${fmtDate(rep.selected_date)})`],
    ["mtd_qtd_ytd", "MTD / QTD / YTD"],
    ["monthly_yearly", "Monthly & Yearly Summary"],
    ["symbol_perf", `Symbol Performance (${rep.symbol_performance.length})`],
    ["trade_log", `Trade Log (${rep.trade_log.length})`],
    ["data_checks", "Data Checks & Audit"],
  ];

  let bodyHtml = "";
  if (activeTab === "dashboard") {
    const d = rep.dashboard;
    bodyHtml = `
      <div class="grid-4">
        <div class="kpi-box"><div class="kpi-label">YTD Buy Value (PKR)</div><div class="kpi-value">${fmtNum(d.ytd?.buy_value)}</div><div class="kpi-sub">Shares: ${fmtInt(d.ytd?.buy_qty)}</div></div>
        <div class="kpi-box"><div class="kpi-label">YTD Sell Value (PKR)</div><div class="kpi-value">${fmtNum(d.ytd?.sell_value)}</div><div class="kpi-sub">Shares: ${fmtInt(d.ytd?.sell_qty)}</div></div>
        <div class="kpi-box"><div class="kpi-label">YTD Total Charges (Comm + SST)</div><div class="kpi-value">${fmtNum(d.ytd?.total_charges)}</div><div class="kpi-sub">Comm: ${fmtNum(d.ytd?.commission_amount)} | SST: ${fmtNum(d.ytd?.sst_amount)}</div></div>
        <div class="kpi-box"><div class="kpi-label">YTD Net P&amp;L (PKR)</div><div class="kpi-value ${pnlClass(d.ytd?.net_pnl)}">${fmtNum(d.ytd?.net_pnl)}</div><div class="kpi-sub">Return on Buy: ${fmtPct(d.ytd?.return_on_buy)}</div></div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header"><div class="card-title">Latest Trading Day (${d.latest_trading_day})</div></div>
          <table class="data-table">
            <tbody>
              <tr><td><b>Buy Value (PKR)</b></td><td class="num">${fmtNum(d.latest_day?.buy_value)}</td></tr>
              <tr><td><b>Sell Value (PKR)</b></td><td class="num">${fmtNum(d.latest_day?.sell_value)}</td></tr>
              <tr><td><b>Gross P&amp;L (PKR)</b></td><td class="num ${pnlClass(d.latest_day?.gross_pnl)}">${fmtNum(d.latest_day?.gross_pnl)}</td></tr>
              <tr><td><b>Commission (PKR)</b></td><td class="num">${fmtNum(d.latest_day?.commission_amount)}</td></tr>
              <tr><td><b>SST 13% (PKR)</b></td><td class="num">${fmtNum(d.latest_day?.sst_amount)}</td></tr>
              <tr><td><b>Total Charges (PKR)</b></td><td class="num">${fmtNum(d.latest_day?.total_charges)}</td></tr>
              <tr><td><b>Net P&amp;L (PKR)</b></td><td class="num ${pnlClass(d.latest_day?.net_pnl)}">${fmtNum(d.latest_day?.net_pnl)}</td></tr>
              <tr><td><b>Return on Buy</b></td><td class="num ${pnlClass(d.latest_day?.return_on_buy)}">${fmtPct(d.latest_day?.return_on_buy)}</td></tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-header"><div class="card-title">MTD / QTD / YTD &amp; Best/Worst Symbols</div></div>
          <table class="data-table" style="margin-bottom:14px;">
            <thead><tr><th>Period</th><th class="num">Gross P&amp;L</th><th class="num">Total Charges</th><th class="num">Net P&amp;L (PKR)</th><th class="num">Return on Buy</th></tr></thead>
            <tbody>
              <tr><td><b>MTD</b></td><td class="num">${fmtNum(d.mtd?.gross_pnl)}</td><td class="num">${fmtNum(d.mtd?.total_charges)}</td><td class="num ${pnlClass(d.mtd?.net_pnl)}">${fmtNum(d.mtd?.net_pnl)}</td><td class="num">${fmtPct(d.mtd?.return_on_buy)}</td></tr>
              <tr><td><b>QTD</b></td><td class="num">${fmtNum(d.qtd?.gross_pnl)}</td><td class="num">${fmtNum(d.qtd?.total_charges)}</td><td class="num ${pnlClass(d.qtd?.net_pnl)}">${fmtNum(d.qtd?.net_pnl)}</td><td class="num">${fmtPct(d.qtd?.return_on_buy)}</td></tr>
              <tr><td><b>YTD</b></td><td class="num">${fmtNum(d.ytd?.gross_pnl)}</td><td class="num">${fmtNum(d.ytd?.total_charges)}</td><td class="num ${pnlClass(d.ytd?.net_pnl)}">${fmtNum(d.ytd?.net_pnl)}</td><td class="num">${fmtPct(d.ytd?.return_on_buy)}</td></tr>
            </tbody>
          </table>
          <div style="display:flex;gap:12px;">
            <div class="kpi-box" style="flex:1;"><div class="kpi-label">Best Symbol (All Dates)</div><div class="kpi-value pos">${d.best_symbol?.symbol}</div><div class="kpi-sub">Net P&amp;L: +${fmtNum(d.best_symbol?.net_pnl)} PKR</div></div>
            <div class="kpi-box" style="flex:1;"><div class="kpi-label">Worst Symbol (All Dates)</div><div class="kpi-value neg">${d.worst_symbol?.symbol}</div><div class="kpi-sub">Net P&amp;L: ${fmtNum(d.worst_symbol?.net_pnl)} PKR</div></div>
          </div>
        </div>
      </div>

      <div class="grid-4">
        <div class="kpi-box"><div class="kpi-label">Total Traded Turnover (Buy+Sell, PKR)</div><div class="kpi-value">${fmtNum(d.total_traded_turnover_pkr)}</div><div class="kpi-sub">All imported YTD data</div></div>
        <div class="kpi-box"><div class="kpi-label">Symbols Traded</div><div class="kpi-value">${d.symbols_count ?? "—"}</div><div class="kpi-sub">Unique symbols in account history</div></div>
        <div class="kpi-box"><div class="kpi-label">Trading Days</div><div class="kpi-value">${d.trading_days_count ?? "—"}</div><div class="kpi-sub">Sessions with ≥1 execution</div></div>
        <div class="kpi-box"><div class="kpi-label">Total Shares Traded (Buy+Sell)</div><div class="kpi-value">${fmtInt(d.total_traded_shares)}</div><div class="kpi-sub">Gross two-way volume</div></div>
      </div>
    `;
  } else if (activeTab === "daily_summary") {
    const rows = rep.daily_summary.rows;
    const tot = rep.daily_summary.total;
    bodyHtml = `
      <div class="card">
        <div class="card-header"><div class="card-title">Daily Summary — Account ${accountId} (One Row per Trading Date)</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Date</th><th>Symbols Traded</th><th class="num">Buy Qty</th><th class="num">Sell Qty</th><th class="num">Net Qty</th>
                <th class="num">Buy Value (PKR)</th><th class="num">Sell Value (PKR)</th>
                <th class="num">Avg Buy</th><th class="num">Avg Sell</th>
                <th class="num">Gross P&amp;L</th><th class="num">Commission</th><th class="num">SST 13%</th>
                <th class="num">Total Charges</th><th class="num">Net P&amp;L (PKR)</th><th class="num">Return on Buy</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map((r) => `
                <tr style="cursor:pointer" title="Click to open the full Daily Trade Summary for ${r.trade_date}" onclick="openAccountDateDetail('${accountId}', '${r.trade_date}')">
                  <td><b>${fmtDate(r.trade_date)}</b></td>
                  <td style="max-width:190px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${r.symbols_str || ""}"><b>${r.symbols_count || 0}</b> <span style="color:var(--text-muted);font-size:10.5px;">${r.symbols_str || "—"}</span></td>
                  <td class="num">${fmtInt(r.buy_qty)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td>
                  <td class="num">${fmtInt(r.net_qty)}</td>
                  <td class="num">${fmtNum(r.buy_value)}</td>
                  <td class="num">${fmtNum(r.sell_value)}</td>
                  <td class="num">${fmtNum(r.avg_buy_price)}</td>
                  <td class="num">${fmtNum(r.avg_sell_price)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td class="num">${fmtNum(r.commission_amount)}</td>
                  <td class="num">${fmtNum(r.sst_amount)}</td>
                  <td class="num">${fmtNum(r.total_charges)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                </tr>
              `).join("")}
              ${tot ? `
                <tr class="total-row">
                  <td>TOTAL</td>
                  <td style="color:var(--text-muted);font-size:10.5px;" title="${tot.symbols_str || ""}">${tot.symbols_count || 0} symbols</td>
                  <td class="num">${fmtInt(tot.buy_qty)}</td>
                  <td class="num">${fmtInt(tot.sell_qty)}</td>
                  <td class="num">${fmtInt(tot.net_qty)}</td>
                  <td class="num">${fmtNum(tot.buy_value)}</td>
                  <td class="num">${fmtNum(tot.sell_value)}</td>
                  <td class="num">${fmtNum(tot.avg_buy_price)}</td>
                  <td class="num">${fmtNum(tot.avg_sell_price)}</td>
                  <td class="num ${pnlClass(tot.gross_pnl)}">${fmtNum(tot.gross_pnl)}</td>
                  <td class="num">${fmtNum(tot.commission_amount)}</td>
                  <td class="num">${fmtNum(tot.sst_amount)}</td>
                  <td class="num">${fmtNum(tot.total_charges)}</td>
                  <td class="num ${pnlClass(tot.net_pnl)}">${fmtNum(tot.net_pnl)}</td>
                  <td class="num ${pnlClass(tot.return_on_buy)}">${fmtPct(tot.return_on_buy)}</td>
                </tr>
              ` : ""}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (activeTab === "daily_detail") {
    const det = rep.selected_date_detail || rep.daily_detail;
    const s = det.summary || {};
    bodyHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Daily Trade Summary — ${fmtDate(det.trade_date)} (Account ${accountId})</div>
            <div class="card-subtitle">Symbol-by-symbol weighted averages, Slab 1 / Slab 2 commission, 13% SST, and Net P&amp;L</div>
          </div>
          <div class="filter-group">
            <label>Select Trading Date:</label>
            <select onchange="openAccountDateDetail('${accountId}', this.value)">
              ${tDates.slice().reverse().map((d) => `<option value="${d}" ${d === det.trade_date ? "selected" : ""}>${d}</option>`).join("")}
            </select>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Symbol</th><th class="num">Buy Qty</th><th class="num">Buy Value</th><th class="num">Avg Buy</th>
                <th class="num">Sell Qty</th><th class="num">Sell Value</th><th class="num">Avg Sell</th>
                <th class="num">Price Diff</th><th class="num">Net Qty</th><th class="num">Gross P&amp;L</th>
                <th>Commission Slab</th><th class="num">Commission</th><th class="num">SST 13%</th>
                <th class="num">Total Charges</th><th class="num">Net P&amp;L</th><th class="num">Return on Buy</th>
              </tr>
            </thead>
            <tbody>
              ${det.symbols.map((r) => `
                <tr>
                  <td><b>${r.symbol}</b></td>
                  <td class="num">${fmtInt(r.buy_qty)}</td>
                  <td class="num">${fmtNum(r.buy_value)}</td>
                  <td class="num">${fmtNum(r.avg_buy_price)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td>
                  <td class="num">${fmtNum(r.sell_value)}</td>
                  <td class="num">${fmtNum(r.avg_sell_price)}</td>
                  <td class="num ${pnlClass(r.price_diff)}">${fmtNum(r.price_diff)}</td>
                  <td class="num">${fmtInt(r.net_qty)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td><span class="badge badge-blue">${r.commission_slab_label}</span></td>
                  <td class="num">${fmtNum(r.commission_amount, 4)}</td>
                  <td class="num">${fmtNum(r.sst_amount, 4)}</td>
                  <td class="num">${fmtNum(r.total_charges, 4)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                </tr>
              `).join("")}
              <tr class="total-row">
                <td>TOTAL</td>
                <td class="num">${fmtInt(s.buy_qty)}</td>
                <td class="num">${fmtNum(s.buy_value)}</td>
                <td class="num">${fmtNum(s.avg_buy_price)}</td>
                <td class="num">${fmtInt(s.sell_qty)}</td>
                <td class="num">${fmtNum(s.sell_value)}</td>
                <td class="num">${fmtNum(s.avg_sell_price)}</td>
                <td class="num ${pnlClass(s.price_diff)}">${fmtNum(s.price_diff)}</td>
                <td class="num">${fmtInt(s.net_qty)}</td>
                <td class="num ${pnlClass(s.gross_pnl)}">${fmtNum(s.gross_pnl)}</td>
                <td>—</td>
                <td class="num">${fmtNum(s.commission_amount, 4)}</td>
                <td class="num">${fmtNum(s.sst_amount, 4)}</td>
                <td class="num">${fmtNum(s.total_charges, 4)}</td>
                <td class="num ${pnlClass(s.net_pnl)}">${fmtNum(s.net_pnl)}</td>
                <td class="num ${pnlClass(s.return_on_buy)}">${fmtPct(s.return_on_buy)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (activeTab === "mtd_qtd_ytd") {
    const blocks = [
      ["MTD Summary (Month-to-Date)", rep.mtd_summary],
      ["QTD Summary (Quarter-to-Date)", rep.qtd_summary],
      ["YTD Summary (Year-to-Date)", rep.ytd_summary],
    ];
    bodyHtml = `${blocks.map(([title, b]) => `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">${title}</div>
            <div class="card-subtitle">Period Start (calendar): ${b.start} • Period End (latest trade): ${b.end} • First Trading Day in Period: ${b.first_trading_day} • Trading Days: ${b.trading_days}</div>
          </div>
        </div>
        <div class="grid-4" style="margin-bottom:12px;">
          <div class="kpi-box"><div class="kpi-label">Buy Quantity / Value</div><div class="kpi-value">${fmtInt(b.buy_qty)}</div><div class="kpi-sub">${fmtNum(b.buy_value)} PKR • Avg ${fmtNum(b.avg_buy_price)}</div></div>
          <div class="kpi-box"><div class="kpi-label">Sell Quantity / Value</div><div class="kpi-value">${fmtInt(b.sell_qty)}</div><div class="kpi-sub">${fmtNum(b.sell_value)} PKR • Avg ${fmtNum(b.avg_sell_price)}</div></div>
          <div class="kpi-box"><div class="kpi-label">Total Charges (Comm + 13% SST)</div><div class="kpi-value">${fmtNum(b.total_charges)}</div><div class="kpi-sub">Comm ${fmtNum(b.commission_amount)} + SST ${fmtNum(b.sst_amount)} PKR</div></div>
          <div class="kpi-box"><div class="kpi-label">Net P&amp;L (After All Charges)</div><div class="kpi-value ${pnlClass(b.net_pnl)}">${fmtNum(b.net_pnl)}</div><div class="kpi-sub">Gross ${fmtNum(b.gross_pnl)} • Return on Buy: ${fmtPct(b.return_on_buy)}</div></div>
        </div>
        <div class="table-wrap" style="max-height:340px;overflow-y:auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Date</th><th>Symbols</th><th class="num">Buy Qty</th><th class="num">Sell Qty</th><th class="num">Net Qty</th>
                <th class="num">Buy Value (PKR)</th><th class="num">Sell Value (PKR)</th>
                <th class="num">Gross P&amp;L (PKR)</th><th class="num">Commission</th><th class="num">SST 13%</th>
                <th class="num">Total Charges</th><th class="num">Net P&amp;L (PKR)</th><th class="num">Return on Buy</th>
              </tr>
            </thead>
            <tbody>
              ${(b.daily_rows || []).map((r) => `
                <tr>
                  <td><b>${fmtDate(r.trade_date)}</b></td>
                  <td style="max-width:170px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${r.symbols_str || ""}"><b>${r.symbols_count || 0}</b> <span style="color:var(--text-muted);font-size:10.5px;">${r.symbols_str || "—"}</span></td>
                  <td class="num">${fmtInt(r.buy_qty)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td>
                  <td class="num">${fmtInt(r.net_qty)}</td>
                  <td class="num">${fmtNum(r.buy_value)}</td>
                  <td class="num">${fmtNum(r.sell_value)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td class="num">${fmtNum(r.commission_amount)}</td>
                  <td class="num">${fmtNum(r.sst_amount)}</td>
                  <td class="num">${fmtNum(r.total_charges)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                </tr>
              `).join("")}
              <tr class="total-row">
                <td>TOTAL</td>
                <td style="color:var(--text-muted);font-size:10.5px;">${b.symbols_count || 0} symbols</td>
                <td class="num">${fmtInt(b.buy_qty)}</td>
                <td class="num">${fmtInt(b.sell_qty)}</td>
                <td class="num">${fmtInt(b.net_qty)}</td>
                <td class="num">${fmtNum(b.buy_value)}</td>
                <td class="num">${fmtNum(b.sell_value)}</td>
                <td class="num ${pnlClass(b.gross_pnl)}">${fmtNum(b.gross_pnl)}</td>
                <td class="num">${fmtNum(b.commission_amount)}</td>
                <td class="num">${fmtNum(b.sst_amount)}</td>
                <td class="num">${fmtNum(b.total_charges)}</td>
                <td class="num ${pnlClass(b.net_pnl)}">${fmtNum(b.net_pnl)}</td>
                <td class="num ${pnlClass(b.return_on_buy)}">${fmtPct(b.return_on_buy)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    `).join("")}`;
  } else if (activeTab === "monthly_yearly") {
    const mTot = rep.monthly_summary.total;
    const yTot = rep.yearly_summary.total;
    bodyHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Monthly Summary — Month-Wise Performance (Account ${accountId})</div>
            <div class="card-subtitle">One row per calendar month with trading data, oldest → newest (matches the monthly sheet of the Trade Summary workbook)</div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Month</th><th class="num">Days</th><th class="num">Buy Qty</th><th class="num">Buy Value (PKR)</th><th class="num">Avg Buy</th><th class="num">Sell Qty</th><th class="num">Sell Value (PKR)</th><th class="num">Avg Sell</th><th class="num">Price Diff (S−B)</th><th class="num">Net Qty</th><th class="num">Gross P&amp;L</th><th>Commission Slab</th><th class="num">Commission</th><th class="num">SST 13%</th><th class="num">Total Charges</th><th class="num">Net P&amp;L</th><th class="num">Return on Buy</th></tr>
            </thead>
            <tbody>
              ${rep.monthly_summary.rows.map((r) => `
                <tr>
                  <td><b>${r.month}</b></td><td class="num">${r.trading_days}</td>
                  <td class="num">${fmtInt(r.buy_qty)}</td><td class="num">${fmtNum(r.buy_value)}</td><td class="num">${fmtNum(r.avg_buy_price)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td><td class="num">${fmtNum(r.sell_value)}</td><td class="num">${fmtNum(r.avg_sell_price)}</td>
                  <td class="num ${pnlClass(r.price_diff)}">${fmtNum(r.price_diff)}</td><td class="num">${fmtInt(r.net_qty)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td><span class="badge badge-blue">${r.commission_slab_label}</span></td>
                  <td class="num">${fmtNum(r.commission_amount)}</td><td class="num">${fmtNum(r.sst_amount)}</td>
                  <td class="num">${fmtNum(r.total_charges)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                </tr>
              `).join("")}
              ${mTot ? `
                <tr class="total-row">
                  <td>TOTAL</td><td class="num">${mTot.trading_days}</td>
                  <td class="num">${fmtInt(mTot.buy_qty)}</td><td class="num">${fmtNum(mTot.buy_value)}</td><td class="num">${fmtNum(mTot.avg_buy_price)}</td>
                  <td class="num">${fmtInt(mTot.sell_qty)}</td><td class="num">${fmtNum(mTot.sell_value)}</td><td class="num">${fmtNum(mTot.avg_sell_price)}</td>
                  <td class="num ${pnlClass(mTot.price_diff)}">${fmtNum(mTot.price_diff)}</td><td class="num">${fmtInt(mTot.net_qty)}</td>
                  <td class="num ${pnlClass(mTot.gross_pnl)}">${fmtNum(mTot.gross_pnl)}</td><td>—</td>
                  <td class="num">${fmtNum(mTot.commission_amount)}</td><td class="num">${fmtNum(mTot.sst_amount)}</td>
                  <td class="num">${fmtNum(mTot.total_charges)}</td>
                  <td class="num ${pnlClass(mTot.net_pnl)}">${fmtNum(mTot.net_pnl)}</td>
                  <td class="num ${pnlClass(mTot.return_on_buy)}">${fmtPct(mTot.return_on_buy)}</td>
                </tr>` : ""}
            </tbody>
          </table>
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Yearly Summary — Year-Wise Performance (Account ${accountId})</div>
            <div class="card-subtitle">One row per calendar year with trading data (weighted averages from totals; Return on Buy = Net P&amp;L ÷ Buy Value, never averaged)</div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Year</th><th class="num">Days</th><th class="num">Buy Qty</th><th class="num">Buy Value (PKR)</th><th class="num">Avg Buy</th><th class="num">Sell Qty</th><th class="num">Sell Value (PKR)</th><th class="num">Avg Sell</th><th class="num">Price Diff (S−B)</th><th class="num">Net Qty</th><th class="num">Gross P&amp;L</th><th>Commission Slab</th><th class="num">Commission</th><th class="num">SST 13%</th><th class="num">Total Charges</th><th class="num">Net P&amp;L</th><th class="num">Return on Buy</th></tr>
            </thead>
            <tbody>
              ${rep.yearly_summary.rows.map((r) => `
                <tr>
                  <td><b>${r.year}</b></td><td class="num">${r.trading_days}</td>
                  <td class="num">${fmtInt(r.buy_qty)}</td><td class="num">${fmtNum(r.buy_value)}</td><td class="num">${fmtNum(r.avg_buy_price)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td><td class="num">${fmtNum(r.sell_value)}</td><td class="num">${fmtNum(r.avg_sell_price)}</td>
                  <td class="num ${pnlClass(r.price_diff)}">${fmtNum(r.price_diff)}</td><td class="num">${fmtInt(r.net_qty)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td><span class="badge badge-blue">${r.commission_slab_label}</span></td>
                  <td class="num">${fmtNum(r.commission_amount)}</td><td class="num">${fmtNum(r.sst_amount)}</td>
                  <td class="num">${fmtNum(r.total_charges)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                </tr>
              `).join("")}
              ${yTot ? `
                <tr class="total-row">
                  <td>TOTAL</td><td class="num">${yTot.trading_days}</td>
                  <td class="num">${fmtInt(yTot.buy_qty)}</td><td class="num">${fmtNum(yTot.buy_value)}</td><td class="num">${fmtNum(yTot.avg_buy_price)}</td>
                  <td class="num">${fmtInt(yTot.sell_qty)}</td><td class="num">${fmtNum(yTot.sell_value)}</td><td class="num">${fmtNum(yTot.avg_sell_price)}</td>
                  <td class="num ${pnlClass(yTot.price_diff)}">${fmtNum(yTot.price_diff)}</td><td class="num">${fmtInt(yTot.net_qty)}</td>
                  <td class="num ${pnlClass(yTot.gross_pnl)}">${fmtNum(yTot.gross_pnl)}</td><td>—</td>
                  <td class="num">${fmtNum(yTot.commission_amount)}</td><td class="num">${fmtNum(yTot.sst_amount)}</td>
                  <td class="num">${fmtNum(yTot.total_charges)}</td>
                  <td class="num ${pnlClass(yTot.net_pnl)}">${fmtNum(yTot.net_pnl)}</td>
                  <td class="num ${pnlClass(yTot.return_on_buy)}">${fmtPct(yTot.return_on_buy)}</td>
                </tr>` : ""}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (activeTab === "symbol_perf") {
    const sTot = rep.symbol_performance_total;
    bodyHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Symbol Performance — All Trading Dates (Ranked by Net P&amp;L Descending)</div>
            <div class="card-subtitle">Hover over any row's Dates column to see every exact trading date for that symbol</div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Rank</th><th>Symbol</th><th>Trading Dates (First → Last)</th><th class="num">Days</th><th class="num">Buy Qty</th><th class="num">Sell Qty</th><th class="num">Buy Value (PKR)</th><th class="num">Sell Value (PKR)</th><th class="num">Gross P&amp;L</th><th class="num">Commission</th><th class="num">SST</th><th class="num">Total Charges</th><th class="num">Net P&amp;L (PKR)</th><th class="num">Return on Buy</th><th></th></tr>
            </thead>
            <tbody>
              ${rep.symbol_performance.map((r, i) => `
                <tr title="All dates: ${r.dates_str || ''}">
                  <td class="num">#${i + 1}</td>
                  <td><b>${r.symbol}</b></td>
                  <td style="font-size:11px;"><b>${r.first_date || "—"}</b> → <b>${r.last_date || "—"}</b></td>
                  <td class="num">${r.trading_days}</td>
                  <td class="num">${fmtInt(r.buy_qty)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td>
                  <td class="num">${fmtNum(r.buy_value)}</td>
                  <td class="num">${fmtNum(r.sell_value)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td class="num">${fmtNum(r.commission_amount)}</td>
                  <td class="num">${fmtNum(r.sst_amount)}</td>
                  <td class="num">${fmtNum(r.total_charges)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                  <td style="color:${r.note && r.note.includes("Best") ? "var(--pos-green)" : "var(--neg-red)"};font-weight:700;font-size:11px;white-space:nowrap;">${r.note || ""}</td>
                </tr>
              `).join("")}
              ${sTot ? `
                <tr class="total-row">
                  <td class="num">—</td>
                  <td><b>TOTAL</b></td>
                  <td style="font-size:11px;">${fmtDate(sTot.first_date) || "—"} → ${fmtDate(sTot.last_date) || "—"}</td>
                  <td class="num">${sTot.trading_days}</td>
                  <td class="num">${fmtInt(sTot.buy_qty)}</td>
                  <td class="num">${fmtInt(sTot.sell_qty)}</td>
                  <td class="num">${fmtNum(sTot.buy_value)}</td>
                  <td class="num">${fmtNum(sTot.sell_value)}</td>
                  <td class="num ${pnlClass(sTot.gross_pnl)}">${fmtNum(sTot.gross_pnl)}</td>
                  <td class="num">${fmtNum(sTot.commission_amount)}</td>
                  <td class="num">${fmtNum(sTot.sst_amount)}</td>
                  <td class="num">${fmtNum(sTot.total_charges)}</td>
                  <td class="num ${pnlClass(sTot.net_pnl)}">${fmtNum(sTot.net_pnl)}</td>
                  <td class="num ${pnlClass(sTot.return_on_buy)}">${fmtPct(sTot.return_on_buy)}</td>
                  <td></td>
                </tr>` : ""}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (activeTab === "trade_log") {
    bodyHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Master Execution Trade Log — Account ${accountId}</div>
            <div class="card-subtitle">Execution-level deduplication by Account + Execution ID; Short Sell normalized to SELL while preserving Original Side</div>
          </div>
        </div>
        ${rep.trade_log.length === 0 ? `<p style="color:var(--text-muted);">Historical dates for Account ${accountId} were migrated from the legacy summary workbook. Upload new raw TradeLog .TXT/.CSV files in the Import Center to populate execution-level rows.</p>` : `
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr><th>Date</th><th>Time</th><th>Symbol</th><th>Market</th><th>Raw Type</th><th>Normalized</th><th>Order ID</th><th>Execution ID</th><th class="num">Qty</th><th class="num">Price</th><th class="num">Value</th><th>Slab</th><th class="num">Comm</th><th class="num">SST</th></tr>
              </thead>
              <tbody>
                ${rep.trade_log.map((ex) => `
                  <tr>
                    <td>${fmtDate(ex.trade_date)}</td><td>${ex.trade_time}</td><td><b>${ex.symbol}</b></td><td>${ex.market_type}</td>
                    <td>${ex.raw_side}</td>
                    <td><span class="badge ${ex.normalized_side === "BUY" ? "badge-green" : "badge-red"}">${ex.normalized_side}</span></td>
                    <td class="num">${ex.order_id}</td><td class="num">${ex.execution_id}</td>
                    <td class="num">${fmtInt(ex.quantity)}</td><td class="num">${fmtNum(ex.price)}</td><td class="num">${fmtNum(ex.trade_value)}</td>
                    <td>${ex.commission_slab}</td><td class="num">${fmtNum(ex.commission_amount, 4)}</td><td class="num">${fmtNum(ex.sst_amount, 4)}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  } else if (activeTab === "data_checks") {
    const rec = rep.data_checks.reconciliation;
    bodyHtml = `
      <div class="card">
        <div class="card-header"><div class="card-title">Internal Reconciliation &amp; Data Integrity Checks — Account ${accountId}</div></div>
        <div class="grid-4">
          <div class="kpi-box"><div class="kpi-label">Reconciliation Status</div><div class="kpi-value pos">${rec.passed ? "TOTALS AGREE" : "CHECK"}</div></div>
          <div class="kpi-box"><div class="kpi-label">Daily vs Symbol Net P&amp;L Diff</div><div class="kpi-value">${rec.daily_vs_symbol_net_pnl_diff}</div></div>
          <div class="kpi-box"><div class="kpi-label">Monthly vs Daily Net P&amp;L Diff</div><div class="kpi-value">${rec.monthly_vs_daily_net_pnl_diff}</div></div>
          <div class="kpi-box"><div class="kpi-label">Open / Unmatched Net Qty Rows</div><div class="kpi-value">${rec.unmatched_count}</div></div>
        </div>
      </div>
    `;
  }

  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:10px;">
      <div class="subtabs" style="margin-bottom:0;border-bottom:none;">
        ${tabs.map(([k, lbl]) => `
          <button class="subtab-btn ${activeTab === k ? "active" : ""}" onclick="switchAccountSubtab('${accountId}', '${k}')">${lbl}</button>
        `).join("")}
      </div>
      <div style="display:flex;gap:8px;">
        <a class="btn btn-primary" href="/api/exports/generate/account_${accountId}_xlsx" download>⬇ Export Account ${accountId} (.xlsx)</a>
        <a class="btn btn-secondary" href="/api/exports/generate/csv_${accountId}" download>CSV</a>
      </div>
    </div>
    <div class="filter-bar"><span class="badge ${state.accDateManual[accountId] ? 'badge-amber' : 'badge-green'}">${state.accDateManual[accountId] ? 'Pinned: '+fmtDate(rep.selected_date)+' · Latest:' : 'Auto → Latest:'} ${fmtDate(tDates[tDates.length-1])}</span>${state.accDateManual[accountId] ? `<button class="btn btn-secondary" onclick="state.accDateManual['${accountId}']=false;renderAccountView(document.getElementById('viewContainer'),'${accountId}')">Reset to Latest</button>` : ''}</div>
    ${bodyHtml}
  `;
}

function switchAccountSubtab(accountId, tabKey) {
  state.accTab[accountId] = tabKey;
  renderAccountView(document.getElementById("viewContainer"), accountId);
}

function openAccountDateDetail(accountId, tradeDate) {
  state.accSelectedDate[accountId] = tradeDate;
  state.accDateManual[accountId] = true;
  state.accTab[accountId] = "daily_detail";
  renderAccountView(document.getElementById("viewContainer"), accountId);
}

// ============================================================================
// 06. MODULE C: FUTURES COMPARISON & ANNUALIZED ANALYSIS
// Separate per-sheet filter bars matching Futures_Analysis (6).xlsx
// ============================================================================

async function renderFuturesView(container) {
  const ticket = beginViewRender(container);
  const f = state.futures;
  const meta = await apiGet(`/api/futures/metadata?apply_rolling=${f.apply_rolling}`);
  f.meta = meta;
  const availDates = meta.dates || meta.retained_dates || [];
  const latestDate = meta.latest_date || "";
  const earliestDate = availDates.length ? availDates[0] : latestDate;
  for (const tab of ['monthly_comparison','month_filter','annualized_comparison','date_filter','date_summary']) {
    if (!f[tab].date_manual) f[tab].selected_date = latestDate;
  }

  // Reference workbook: seven visible sheets; retain existing app policy tab.
  const subtabs = [
    ["monthly_comparison", "Monthly Comparison"],
    ["month_filter", "Month Filter"],
    ["symbol_filter", "Symbol Filter"],
    ["annualized_comparison", "Annualized Comparison"],
    ["date_filter", "Date Filter"],
    ["future_symbol_summary", "Future Symbol Summary"],
    ["date_summary", "Date Summary"],
    ["rolling_window", "2-Month Rolling Retention"],
  ];

  let filterBarHtml = "";
  let contentHtml = "";

  const exportBtnHtml = `
    <div style="margin-left:auto;display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:8px;">
      <span class="date-readout" title="A NOV contract can trade in October. Contract expiry month is not the trading date.">Contract month ≠ trading date</span> <a class="btn btn-primary" href="${futuresExportUrl()}" download>⬇ Export 8-Sheet Futures_Analysis.xlsx</a>
    </div>
  `;

  // Match the workbook ListDates dropdown, with explicit DD-MM-YYYY display.
  const dateCtrl = (tabKey, st) => {
    const val = st.selected_date;
    const isAll = !/^\d{4}-\d{2}-\d{2}$/.test(val || "");
    const shown = isAll ? latestDate : val;
    return `
      <div class="filter-group" title="Worksheet date filter — select an imported trading date, matching the Excel ListDates dropdown. Dates are displayed as DD-MM-YYYY; no browser-locale month/day ambiguity.">
        <label>Selected Date:</label>
        <span class="date-readout">${isAll ? "All dates" : fmtDate(shown)}</span>
        <select aria-label="Selected date for this worksheet" ${isAll ? "disabled" : ""} onchange="state.futures.${tabKey}.date_manual=true;state.futures.${tabKey}.selected_date=this.value;renderFuturesView(document.getElementById('viewContainer'))">${availDates.map(d=>`<option value="${d}" ${d===shown?'selected':''}>${fmtDate(d)}</option>`).join('')}</select>
        <span class="badge ${st.date_manual ? 'badge-amber' : 'badge-green'}">${isAll ? 'All retained dates · Latest:' : (st.date_manual ? 'Pinned · Latest:' : 'Auto → Latest:')} ${fmtDate(latestDate)}</span>
        ${st.date_manual ? `<button class="btn btn-secondary" onclick="state.futures.${tabKey}.date_manual=false;state.futures.${tabKey}.selected_date=null;renderFuturesView(document.getElementById('viewContainer'))">Reset to Latest</button>` : ''}
      </div>
      <div class="filter-group">
        <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;" title="The Excel sheets show the single selected date; tick this only if you want the full 2-month retained window returned instead.">
          <input type="checkbox" ${isAll ? "checked" : ""} onchange="state.futures.${tabKey}.date_manual=this.checked;state.futures.${tabKey}.selected_date=this.checked?'ALL':'${latestDate}';renderFuturesView(document.getElementById('viewContainer'))" />
          All retained 2-month dates
        </label>
      </div>
    `;
  };
  const daysCtrl = (tabKey, st) => `
      <div class="filter-group" title="Same as this sheet's 'Days:' filter cell in Excel (default 30).">
        <label>Days:</label>
        <input type="number" min="1" max="365" value="${st.days}" style="width:74px;" onchange="state.futures.${tabKey}.days=Number(this.value)||30;renderFuturesView(document.getElementById('viewContainer'))" />
      </div>`;
  const resolvedNote = (res) => res.date_was_resolved && res.requested_date
    ? ` <span class="badge" style="background:#f59e0b;color:#111827;" title="${res.requested_date} is not a trading day in the active window">Picked ${fmtDate(res.requested_date)} → showing nearest trading day ${fmtDate(res.selected_date)}</span>`
    : "";

  if (f.subtab === "monthly_comparison") {
    const st = f.monthly_comparison;
    const qs = new URLSearchParams({
      view_mode: "monthly_comparison",
      selected_date: st.selected_date,
      days: String(st.days),
      apply_rolling: String(f.apply_rolling),
    });
    const comp = await apiGet(`/api/futures/comparison?${qs.toString()}`);

    filterBarHtml = `
      <div class="filter-bar">
        ${dateCtrl("monthly_comparison", st)}
        ${daysCtrl("monthly_comparison", st)}
        ${exportBtnHtml}
      </div>
    `;
    contentHtml = renderFuturesComparisonTableCard(
      "MONTHLY COMPARISON — FUTURES vs CURRENT",
      `Selected Date: ${fmtDate(comp.selected_date)}${resolvedNote(comp)} (${comp.rows_count} Rows) • Sorted by Annualized % Ascending • Days = ${st.days}`,
      comp.rows
    );
  } else if (f.subtab === "month_filter") {
    const st = f.month_filter;
    const qs = new URLSearchParams({
      view_mode: "month_filter",
      selected_date: st.selected_date,
      contract_month: st.contract_month,
      days: String(st.days),
      apply_rolling: String(f.apply_rolling),
    });
    const comp = await apiGet(`/api/futures/comparison?${qs.toString()}`);

    filterBarHtml = `
      <div class="filter-bar">
        ${dateCtrl("month_filter", st)}
        ${daysCtrl("month_filter", st)}
        <div class="filter-group" title="Same as this sheet's 'Month/Contract:' filter cell in Excel (e.g. OCT).">
          <label>Month/Contract:</label>
          <select onchange="state.futures.month_filter.contract_month=this.value;renderFuturesView(document.getElementById('viewContainer'))">
            <option value="ALL" ${st.contract_month === "ALL" ? "selected" : ""}>ALL CONTRACTS</option>
            ${(meta.contracts || []).map((c) => `<option value="${c}" ${c === st.contract_month ? "selected" : ""}>${c}</option>`).join("")}
          </select>
        </div>
        ${exportBtnHtml}
      </div>
    `;
    contentHtml = renderFuturesComparisonTableCard(
      "MONTH / CONTRACT FILTER",
      `Selected Date: ${fmtDate(comp.selected_date)}${resolvedNote(comp)} • Month/Contract: ${st.contract_month} (${comp.rows_count} Rows) • Sorted by Annualized % Ascending • Days = ${st.days}`,
      comp.rows
    );
  } else if (f.subtab === "symbol_filter") {
    const st = f.symbol_filter;
    st.selected_date = "ALL";
    const qs = new URLSearchParams({
      view_mode: "symbol_filter",
      selected_date: "ALL",
      contract_month: st.contract_month,
      base_symbol: st.base_symbol,
      days: String(st.days),
      apply_rolling: String(f.apply_rolling),
    });
    const comp = await apiGet(`/api/futures/comparison?${qs.toString()}`);

    filterBarHtml = `
      <div class="filter-bar">
        <div class="filter-group" title="Same as this sheet's 'Month/Contract:' filter cell in Excel (e.g. OCTB).">
          <label>Month/Contract:</label>
          <select onchange="state.futures.symbol_filter.contract_month=this.value;renderFuturesView(document.getElementById('viewContainer'))">
            <option value="ALL" ${st.contract_month === "ALL" ? "selected" : ""}>ALL CONTRACTS</option>
            ${(meta.contracts || []).map((c) => `<option value="${c}" ${c === st.contract_month ? "selected" : ""}>${c}</option>`).join("")}
          </select>
        </div>
        ${daysCtrl("symbol_filter", st)}
        <div class="filter-group" title="Same as this sheet's 'Symbol:' filter cell in Excel (e.g. OGDC).">
          <label>Symbol:</label>
          <select onchange="state.futures.symbol_filter.base_symbol=this.value;recordSymbolSearch(this.value);renderFuturesView(document.getElementById('viewContainer'))">
            <option value="ALL" ${st.base_symbol === "ALL" ? "selected" : ""}>ALL SYMBOLS</option>
            ${(meta.base_symbols || []).map((s2) => `<option value="${s2}" ${s2 === st.base_symbol ? "selected" : ""}>${s2}</option>`).join("")}
          </select>
        </div>
        ${exportBtnHtml}
      </div>
    `;
    contentHtml = renderFuturesComparisonTableCard(
      "SYMBOL FILTER — ALL DATES FOR SELECTED CONTRACT & SYMBOL",
      `Month/Contract: ${st.contract_month} • Symbol: ${st.base_symbol} • Days: ${st.days} (${comp.rows_count} Date Rows, Sorted Chronologically)`,
      comp.rows
    );
  } else if (f.subtab === "annualized_comparison") {
    const st = f.annualized_comparison;
    const qs = new URLSearchParams({
      view_mode: "annualized_comparison",
      selected_date: st.selected_date,
      days: String(st.days),
      apply_rolling: String(f.apply_rolling),
    });
    const comp = await apiGet(`/api/futures/comparison?${qs.toString()}`);

    filterBarHtml = `
      <div class="filter-bar">
        ${dateCtrl("annualized_comparison", st)}
        ${daysCtrl("annualized_comparison", st)}
        ${exportBtnHtml}
      </div>
    `;
    contentHtml = renderFuturesComparisonTableCard(
      "ANNUALIZED COMPARISON — ALL SYMBOLS & CONTRACTS",
      `Selected Date: ${fmtDate(comp.selected_date)}${resolvedNote(comp)} (${comp.rows_count} Rows) • Sorted by Annualized % Ascending • Days = ${st.days}`,
      comp.rows
    );
  } else if (f.subtab === "date_filter") {
    const st = f.date_filter;
    const qs = new URLSearchParams({
      view_mode: "date_filter",
      selected_date: st.selected_date,
      days: String(st.days),
      apply_rolling: String(f.apply_rolling),
    });
    const comp = await apiGet(`/api/futures/comparison?${qs.toString()}`);

    filterBarHtml = `
      <div class="filter-bar">
        ${dateCtrl("date_filter", st)}
        ${daysCtrl("date_filter", st)}
        ${exportBtnHtml}
      </div>
    `;
    contentHtml = renderFuturesComparisonTableCard(
      "DATE FILTER — FULL DAY COMPARISON",
      `Selected Date: ${fmtDate(comp.selected_date)}${resolvedNote(comp)} (${comp.rows_count} Rows) • Sorted by Annualized % Ascending • Days = ${st.days}`,
      comp.rows
    );
  } else if (f.subtab === "future_symbol_summary") {
    const st = f.future_symbol_summary;
    const res = await apiGet(`/api/futures/symbol-summary?contract_symbol=${encodeURIComponent(st.contract_symbol)}&apply_rolling=${f.apply_rolling}`);

    filterBarHtml = `
      <div class="filter-bar">
        <div class="filter-group" title="Same as this sheet's 'Symbol / Item:' filter cell in Excel (e.g. AGHA-OCT).">
          <label>Symbol / Item:</label>
          <select onchange="state.futures.future_symbol_summary.contract_symbol=this.value;renderFuturesView(document.getElementById('viewContainer'))">
            <option value="ALL" ${st.contract_symbol === "ALL" ? "selected" : ""}>ALL CONTRACT SYMBOLS</option>
            ${(meta.contract_symbols || []).map((cs) => `<option value="${cs}" ${cs === st.contract_symbol ? "selected" : ""}>${cs}</option>`).join("")}
          </select>
        </div>
        <div class="filter-group">
          <label>Date Window:</label>
          <select onchange="state.futures.apply_rolling=(this.value==='true');renderFuturesView(document.getElementById('viewContainer'))">
            <option value="true" ${f.apply_rolling ? "selected" : ""}>2-Month Active Window (Sep–Oct 2026)</option>
            <option value="false" ${!f.apply_rolling ? "selected" : ""}>All Dates From Start (Aug–Oct 2026)</option>
          </select>
        </div>
        ${exportBtnHtml}
      </div>
    `;
    contentHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">FUTURE SYMBOL SUMMARY — ALL RETAINED DATES (2026F)</div>
            <div class="card-subtitle">Symbol / Item: <b>${res.selected_contract_symbol}</b> (${res.rows_count} Trading Days) • Sorted by DATE Ascending • Change = CLOSE − PR_CL</div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>DATE</th><th class="num">PR_CL</th><th class="num">OPEN</th><th class="num">High</th><th class="num">LOW</th><th class="num">AVG</th><th class="num">CLOSE</th><th class="num">VOLUME</th><th class="num">Change</th></tr>
            </thead>
            <tbody>
              ${res.rows.map((r) => `
                <tr>
                  <td><b>${fmtDate(r.DATE)}</b></td>
                  <td class="num">${fmtNum(r.PR_CL)}</td>
                  <td class="num">${fmtNum(r.OPEN)}</td>
                  <td class="num">${fmtNum(r.High)}</td>
                  <td class="num">${fmtNum(r.LOW)}</td>
                  <td class="num">${fmtNum(r.AVG)}</td>
                  <td class="num">${fmtNum(r.CLOSE)}</td>
                  <td class="num">${fmtInt(r.VOLUME)}</td>
                  <td class="num ${pnlClass(r.Change)}">${fmtNum(r.Change)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (f.subtab === "date_summary") {
    const st = f.date_summary;
    const res = await apiGet(`/api/futures/date-summary?selected_date=${encodeURIComponent(st.selected_date)}&apply_rolling=${f.apply_rolling}`);

    filterBarHtml = `
      <div class="filter-bar">
        ${dateCtrl("date_summary", st)}
        ${exportBtnHtml}
      </div>
    `;
    contentHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">DATE SUMMARY — ALL SYMBOLS FOR SELECTED DATE (2026F)</div>
            <div class="card-subtitle">Selected Date: <b>${fmtDate(res.selected_date)}</b>${resolvedNote(res)} (${res.rows_count} Futures Contracts) • Sorted by SYMBOL Ascending • Change = CLOSE − PR_CL</div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>DATE</th><th>SYMBOL</th><th class="num">PR_CL</th><th class="num">OPEN</th><th class="num">High</th><th class="num">LOW</th><th class="num">AVG</th><th class="num">CLOSE</th><th class="num">VOLUME</th><th class="num">Change</th></tr>
            </thead>
            <tbody>
              ${res.rows.map((r) => `
                <tr>
                  <td>${fmtDate(r.DATE)}</td>
                  <td><b>${r.SYMBOL}</b></td>
                  <td class="num">${fmtNum(r.PR_CL)}</td>
                  <td class="num">${fmtNum(r.OPEN)}</td>
                  <td class="num">${fmtNum(r.High)}</td>
                  <td class="num">${fmtNum(r.LOW)}</td>
                  <td class="num">${fmtNum(r.AVG)}</td>
                  <td class="num">${fmtNum(r.CLOSE)}</td>
                  <td class="num">${fmtInt(r.VOLUME)}</td>
                  <td class="num ${pnlClass(r.Change)}">${fmtNum(r.Change)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (f.subtab === "rolling_window") {
    const prev = await apiGet("/api/futures/rolling-window-preview?months=2");
    filterBarHtml = `
      <div class="filter-bar">
        <span class="badge badge-blue">RETENTION POLICY</span>
        <div class="filter-group">
          <label>Active Rolling Policy:</label>
          <select onchange="state.futures.apply_rolling=(this.value==='true');renderFuturesView(document.getElementById('viewContainer'))">
            <option value="true" ${f.apply_rolling ? "selected" : ""}>Enforce 2-Month Rolling Retention (Sep–Oct 2026 Active)</option>
            <option value="false" ${!f.apply_rolling ? "selected" : ""}>Show Full Database History Including August 2026</option>
          </select>
        </div>
        ${exportBtnHtml}
      </div>
    `;
    contentHtml = `
      <div class="card">
        <div class="card-header"><div class="card-title">2-Month Rolling Data Retention Policy Preview</div></div>
        <div class="grid-4">
          <div class="kpi-box"><div class="kpi-label">Latest Date in Dataset</div><div class="kpi-value">${fmtDate(prev.latest_date)}</div></div>
          <div class="kpi-box"><div class="kpi-label">2-Month Cutoff Date</div><div class="kpi-value">${fmtDate(prev.cutoff_date)}</div></div>
          <div class="kpi-box"><div class="kpi-label">Active Retained Futures Rows</div><div class="kpi-value pos">${fmtInt(prev.futures_rows_retained_in_active_window)}</div></div>
          <div class="kpi-box"><div class="kpi-label">Older Futures Rows (August)</div><div class="kpi-value">${fmtInt(prev.futures_rows_older_than_cutoff)}</div></div>
        </div>
        <p style="color:var(--text-muted);">${prev.note}</p>
      </div>
    `;
  }

  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `
    <div class="subtabs">
      ${subtabs.map(([k, lbl]) => `
        <button class="subtab-btn ${f.subtab === k ? "active" : ""}" onclick="state.futures.subtab='${k}';renderFuturesView(document.getElementById('viewContainer'))">${lbl}</button>
      `).join("")}
    </div>
    ${filterBarHtml}
    ${contentHtml}
  `;
}

function renderFuturesComparisonTableCard(title, subtitle, rows) {
  return `
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">${title}</div>
          <div class="card-subtitle">${subtitle}</div>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Date</th><th>Symbol</th><th>Contract/Month</th>
              <th class="num">Current Value</th><th class="num">Future Value</th>
              <th class="num">Volume</th><th class="num">High</th><th class="num">Low</th>
              <th class="num">Difference</th><th class="num">Difference %</th>
              <th class="num">Days</th><th class="num">Annualized %</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((r) => `
              <tr>
                <td><b>${fmtDate(r.trade_date)}</b></td>
                <td><b>${r.symbol}</b></td>
                <td><span class="badge badge-blue">${r.contract}</span></td>
                <td class="num">${fmtNum(r.current_value)}</td>
                <td class="num">${fmtNum(r.future_value)}</td>
                <td class="num">${fmtInt(r.volume)}</td>
                <td class="num">${fmtNum(r.high)}</td>
                <td class="num">${fmtNum(r.low)}</td>
                <td class="num ${pnlClass(r.difference)}">${r.difference > 0 ? "+" : ""}${fmtNum(r.difference)}</td>
                <td class="num ${pnlClass(r.difference_pct)}">${fmtPct(r.difference_pct, false)}</td>
                <td class="num">${r.days}</td>
                <td class="num ${pnlClass(r.annualized_pct)}">${fmtPct(r.annualized_pct, false)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// ============================================================================
// 07. MODULE D: TECHNICAL ANALYSIS, SETUP GENERATOR & 36-TICKER DASHBOARD
// ============================================================================
function formatCompactIndicatorValue(indName, valStr) {
  if (!valStr) return "N/A";
  if (indName.includes("EMA 200") && valStr.includes(";")) {
    return valStr.replace("; ", "<br><span style='color:var(--text-muted);font-size:10.5px;'>") + "</span>";
  }
  if (indName.includes("VWAP") && valStr.includes("|")) {
    return valStr.replace(" | ", "<br>");
  }
  return valStr;
}

async function renderTechnicalView(container) {
  const ticket = beginViewRender(container);
  const t = state.technical;
  let bodyHtml = "";

  if (t.subtab === "ideas_and_analyst") {
    const qsIdeas = new URLSearchParams({
      scope_or_sector: state.ideas.scope_or_sector,
      direction: state.ideas.direction,
      query: state.ideas.query,
      limit: "5",
    });
    const [ideasRes, filtersMeta, analystRes] = await Promise.all([
      apiGet(`/api/intelligence/trading-ideas?${qsIdeas.toString()}`),
      apiGet("/api/intelligence/filters"),
      apiGet(`/api/intelligence/automated-analyst/${encodeURIComponent(state.analyst.symbol)}?action=${encodeURIComponent(state.analyst.action)}`),
    ]);
    bodyHtml = `
      ${buildTradingIdeasCardHtml(ideasRes, filtersMeta)}
      ${buildAutomatedAnalystCardHtml(analystRes)}
    `;
  } else if (t.subtab === "core36" || t.subtab === "all531") {
    const scope = t.subtab === "core36" ? "core36" : "all";
    const qs = new URLSearchParams({ scope });
    if (t.signalFilter && t.signalFilter !== "ALL") qs.set("signal_filter", t.signalFilter);
    const uni = await apiGet(`/api/technical/universe?${qs.toString()}`);

    bodyHtml = `
      <div class="filter-bar">
        <div class="filter-group">
          <label>Search Ticker:</label>
          <input type="text" id="uniSearchInput" value="${t.search}" placeholder="Type full symbol freely — filters live, never auto-enters (e.g. ATRL, MLCF or MLF)..." style="width:230px;" oninput="onUniverseSearchInput(this.value)" />
          <span id="uniVisibleCount" style="color:var(--text-muted);font-size:11px;">${uni.count} / ${uni.count}</span>
        </div>
        <div class="filter-group">
          <label>Signal Filter:</label>
          <select onchange="state.technical.signalFilter=this.value;renderTechnicalView(document.getElementById('viewContainer'))">
            <option value="ALL" ${t.signalFilter === "ALL" ? "selected" : ""}>ALL SIGNALS (${uni.count})</option>
            <option value="BUY" ${t.signalFilter === "BUY" ? "selected" : ""}>BUY</option>
            <option value="HOLD / NEUTRAL" ${t.signalFilter === "HOLD / NEUTRAL" ? "selected" : ""}>HOLD / NEUTRAL</option>
            <option value="SELL" ${t.signalFilter === "SELL" ? "selected" : ""}>SELL</option>
            <option value="SHORT SELL" ${t.signalFilter === "SHORT SELL" ? "selected" : ""}>SHORT SELL</option>
          </select>
        </div>
        <div style="margin-left:auto;">
          <a class="btn btn-primary" href="/api/exports/generate/technical_xlsx" download>⬇ Export PSX_RSI_Pivot_Analysis.xlsx</a>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">${scope === "core36" ? "Core 36-Ticker Technical Matrix (with MLCF / MLF Alias)" : `Full PSX Cash Equity Screener (${uni.count} Symbols)`}</div>
            <div class="card-subtitle">Click any ticker row to open its full 9-Factor Signal Deep-Dive, Daily/Weekly Pivots &amp; Interactive Chart</div>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table" id="uniSummaryTable">
            <thead>
              <tr>
                <th>Symbol</th><th class="num">Close</th><th class="num">Chg %</th><th class="num">RSI(14)</th><th>RSI Zone</th>
                <th class="num">Pivot (P)</th><th class="num">R1</th><th class="num">S1</th>
                <th class="num">W-Pivot</th><th class="num">MACD</th><th class="num">MACD Sig</th>
                <th class="num">EMA 9/21/50</th><th class="num">ADX(14)</th><th class="num">Score</th><th>Action / Combined Signal</th>
              </tr>
            </thead>
            <tbody>
              ${uni.items.map((item) => {
                const dp = item.daily_pivots.classic;
                const wp = item.weekly_pivots?.pivots || {};
                const act = item.signal.action;
                const bCls = act === "BUY" ? "badge-green" : (act === "SELL" || act === "SHORT SELL" ? "badge-red" : "badge-amber");
                return `
                  <tr style="cursor:pointer" data-symbol="${item.symbol}" data-label="${item.display_label}" onclick="openTickerDeepDive('${item.symbol}')">
                    <td><b>${item.display_label}</b></td>
                    <td class="num">${fmtNum(item.close)}</td>
                    <td class="num ${pnlClass(item.change_pct)}">${fmtPct(item.change_pct, false)}</td>
                    <td class="num">${fmtNum(item.rsi14)}</td>
                    <td>${item.rsi_zone}</td>
                    <td class="num">${fmtNum(dp.P)}</td>
                    <td class="num">${fmtNum(dp.R1)}</td>
                    <td class="num">${fmtNum(dp.S1)}</td>
                    <td class="num">${fmtNum(wp.P)}</td>
                    <td class="num">${fmtNum(item.macd)}</td>
                    <td class="num">${fmtNum(item.macd_sig)}</td>
                    <td class="num">${fmtNum(item.ema9, 1)} / ${fmtNum(item.ema21, 1)} / ${fmtNum(item.ema50, 1)}</td>
                    <td class="num">${fmtNum(item.adx14)}</td>
                    <td class="num ${pnlClass(item.signal.score)}">${item.signal.score > 0 ? "+" : ""}${item.signal.score}/9</td>
                    <td><span class="badge ${bCls}">${item.signal.combined_signal}</span></td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (t.subtab === "deep_dive") {
    const [res, analystRes] = await Promise.all([
      apiGet(`/api/technical/ticker/${encodeURIComponent(t.selectedSymbol)}?tail_bars=100`),
      apiGet(`/api/intelligence/automated-analyst/${encodeURIComponent(t.selectedSymbol)}`),
    ]);
    const lat = res.latest;
    const sig = lat.signal;
    const dp = lat.daily_pivots;
    const wp = lat.weekly_pivots?.pivots || {};

    bodyHtml = `
      <div class="filter-bar">
        <div class="filter-group">
          <label>Type Any PSX Ticker (531 Symbols):</label>
          <input type="text" id="deepDiveSymbolInput" value="${t.selectedSymbol}" style="width:110px;font-weight:700;" onkeydown="if(event.key==='Enter')openTickerDeepDive(this.value)" />
          <button class="btn btn-primary" onclick="openTickerDeepDive(document.getElementById('deepDiveSymbolInput').value)">Load</button>
        </div>
        <div class="filter-group" style="flex-wrap:wrap;">
          <label title="Automatically ranks your most-searched symbols first!">Quick Select (Most Searched):</label>
          ${buildQuickSelectBarHtml(t.selectedSymbol, "openTickerDeepDive")}
        </div>
      </div>

      <div class="grid-4">
        <div class="kpi-box">
          <div class="kpi-label">${res.display_label} • Last Close (${fmtDate(lat.latest_date)})</div>
          <div class="kpi-value">${fmtNum(lat.close)} PKR</div>
          <div class="kpi-sub ${pnlClass(lat.change_pct)}">Day Change: ${fmtNum(lat.change_val)} (${fmtPct(lat.change_pct, false)})</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Composite Signal (${sig.score > 0 ? "+" : ""}${sig.score} / 9)</div>
          <div class="kpi-value ${sig.score > 0 ? "pos" : (sig.score < 0 ? "neg" : "")}">${sig.action}</div>
          <div class="kpi-sub">${sig.combined_signal} • Rule strength: ${sig.confidence}</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Entry / Stop-Loss / Target Reference</div>
          <div class="kpi-value" style="font-size:15px;">E: ${fmtNum(sig.entry_reference)} | SL: ${fmtNum(sig.stop_loss_reference)}</div>
          <div class="kpi-sub">Target: ${fmtNum(sig.target_reference)} PKR • R/R Ratio: ${sig.risk_reward}x</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">VWAP &amp; EMA-200 Methodology Note</div>
          <div class="kpi-value" style="font-size:14px;">Typ. Price: ${fmtNum(lat.vwap_typical_daily)} | 20d VWAP: ${fmtNum(lat.vwap_rolling20)}</div>
          <div class="kpi-sub">Bars: ${lat.bars_count} (Strict EMA200=N/A; Legacy Rec. EMA200=${fmtNum(lat.ema200_recursive)})</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">${res.display_label} — Price, Bollinger Bands (20,2), EMA 9/21/50 &amp; Wilder RSI(14) Chart</div>
            <div class="card-subtitle">Last ${res.series.length} sessions (${fmtDate(res.series[0]?.trade_date)} → ${fmtDate(lat.latest_date)}) • No future-data leakage</div>
          </div>
        </div>
        ${renderTechnicalSvgChart(res.series)}
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header"><div class="card-title">9-Factor Explainable Indicator Dashboard</div></div>
          <div class="table-wrap">
            <table class="data-table compact-table">
              <thead>
                <tr>
                  <th style="width:22%;">Indicator</th>
                  <th style="width:26%;">Value</th>
                  <th style="width:24%;">Signal</th>
                  <th style="width:20%;">Actionable Advice</th>
                  <th class="num" style="width:8%;">Vote</th>
                </tr>
              </thead>
              <tbody>
                ${sig.indicator_breakdown.map((b) => `
                  <tr>
                    <td><b>${b.indicator}</b></td>
                    <td style="font-family:var(--font-mono);font-size:11.2px;">${formatCompactIndicatorValue(b.indicator, b.value)}</td>
                    <td><span class="badge ${b.vote > 0 ? "badge-green" : (b.vote < 0 ? "badge-red" : "badge-amber")}">${b.signal}</span></td>
                    <td>${b.advice}</td>
                    <td class="num ${pnlClass(b.vote)}"><b>${b.vote > 0 ? "+1" : b.vote}</b></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
          <div style="margin-top:10px;font-size:12px;color:var(--text-muted);">
            <b>Invalidation Rule:</b> ${sig.invalidation} • <b>Horizon:</b> ${sig.holding_horizon}
          </div>
        </div>

        <div class="card">
          <div class="card-header"><div class="card-title">Daily &amp; Previous-Completed-Week Pivot Levels</div></div>
          <div class="table-wrap">
            <table class="data-table compact-table">
              <thead>
                <tr><th>Level</th><th class="num">Daily Classic</th><th class="num">Daily Fibonacci</th><th class="num">Daily Camarilla</th><th class="num">Weekly Classic (${lat.weekly_pivots?.week_key || "Prev Wk"})</th></tr>
              </thead>
              <tbody>
                ${["R3", "R2", "R1", "P", "S1", "S2", "S3"].map((lvl) => `
                  <tr ${lvl === "P" ? 'style="background:rgba(56,189,248,0.12);font-weight:700;"' : ""}>
                    <td><b>${lvl === "P" ? "PIVOT (P)" : lvl}</b></td>
                    <td class="num">${fmtNum(dp.classic[lvl])}</td>
                    <td class="num">${fmtNum(dp.fibonacci[lvl])}</td>
                    <td class="num">${fmtNum(dp.camarilla[lvl])}</td>
                    <td class="num">${fmtNum(wp[lvl])}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      ${buildAutomatedAnalystCardHtml(analystRes)}
    `;
  }

  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `
    <div class="subtabs">
      <button class="subtab-btn ${t.subtab === "core36" ? "active" : ""}" onclick="state.technical.subtab='core36';renderTechnicalView(document.getElementById('viewContainer'))">Core 36 watchlist</button>
      <button class="subtab-btn ${t.subtab === "ideas_and_analyst" ? "active" : ""}" onclick="state.technical.subtab='ideas_and_analyst';renderTechnicalView(document.getElementById('viewContainer'))">⚡ Trading Ideas Generator &amp; Automated Analyst</button>
      <button class="subtab-btn ${t.subtab === "deep_dive" ? "active" : ""}" onclick="state.technical.subtab='deep_dive';renderTechnicalView(document.getElementById('viewContainer'))">Ticker Deep-Dive &amp; Chart (${t.selectedSymbol})</button>
      <button class="subtab-btn ${t.subtab === "all531" ? "active" : ""}" onclick="state.technical.subtab='all531';renderTechnicalView(document.getElementById('viewContainer'))">All-symbol screener</button>
    </div>
    ${bodyHtml}
  `;
  if (t.subtab === "core36" || t.subtab === "all531") applyUniverseClientFilter();
}

// Live client-side ticker filtering — typing NEVER triggers a submit or page
// re-render, so the full symbol can always be typed without losing focus.
function onUniverseSearchInput(val) {
  state.technical.search = val;
  applyUniverseClientFilter();
}

function applyUniverseClientFilter() {
  const q = (state.technical.search || "").trim().toUpperCase();
  const rows = document.querySelectorAll("#uniSummaryTable tbody tr");
  let visible = 0;
  let total = 0;
  rows.forEach((r) => {
    total++;
    const sym = (r.getAttribute("data-symbol") || "").toUpperCase();
    const lbl = (r.getAttribute("data-label") || "").toUpperCase();
    const hit =
      !q ||
      sym.includes(q) ||
      lbl.includes(q) ||
      (q === "MLF" && sym === "MLCF");
    r.style.display = hit ? "" : "none";
    if (hit) visible++;
  });
  const cEl = document.getElementById("uniVisibleCount");
  if (cEl) cEl.textContent = `${visible} / ${total}`;
}

function openTickerDeepDive(sym) {
  const clean = (sym || "ATRL").toUpperCase().trim();
  recordSymbolSearch(clean);
  state.technical.selectedSymbol = clean;
  state.analyst.symbol = clean;
  state.technical.subtab = "deep_dive";
  if (state.currentView !== "technical") {
    switchView("technical");
  } else {
    renderTechnicalView(document.getElementById("viewContainer"));
  }
}

function renderTechnicalSvgChart(series) {
  if (!series || series.length < 2) return `<p>Insufficient bars to plot chart.</p>`;
  const w = 900, hPrice = 210, hRsi = 90, padL = 55, padR = 55, padT = 18;
  const totalH = hPrice + hRsi + 20;
  const plotW = w - padL - padR;
  const stepX = plotW / (series.length - 1);

  const highs = series.map((d) => d.bb_up || d.high);
  const lows = series.map((d) => d.bb_low || d.low);
  const minP = Math.min(...lows) * 0.985;
  const maxP = Math.max(...highs) * 1.015;
  const pH = hPrice - padT - 10;

  const yPrice = (val) => padT + pH - ((val - minP) / (maxP - minP || 1)) * pH;
  const linePts = (field) =>
    series
      .map((d, i) => (d[field] != null ? `${(padL + i * stepX).toFixed(1)},${yPrice(d[field]).toFixed(1)}` : null))
      .filter(Boolean)
      .join(" ");

  const rsiTop = hPrice + 10;
  const rsiH = hRsi - 25;
  const yRsi = (val) => rsiTop + rsiH - (val / 100) * rsiH;
  const rsiPts = series
    .map((d, i) => (d.rsi14 != null ? `${(padL + i * stepX).toFixed(1)},${yRsi(d.rsi14).toFixed(1)}` : null))
    .filter(Boolean)
    .join(" ");

  return `
    <svg viewBox="0 0 ${w} ${totalH}" style="width:100%;height:310px;background:#070c18;border-radius:7px;border:1px solid var(--border-color);">
      <polyline fill="none" stroke="rgba(148,163,184,0.45)" stroke-dasharray="3,3" stroke-width="1.2" points="${linePts("bb_up")}" />
      <polyline fill="none" stroke="rgba(148,163,184,0.45)" stroke-dasharray="3,3" stroke-width="1.2" points="${linePts("bb_low")}" />
      <polyline fill="none" stroke="#f59e0b" stroke-width="1.5" points="${linePts("ema50")}" />
      <polyline fill="none" stroke="#a855f7" stroke-width="1.5" points="${linePts("ema21")}" />
      <polyline fill="none" stroke="#38bdf8" stroke-width="2.2" points="${linePts("close")}" />
      <text x="${padL}" y="14" fill="#38bdf8" font-size="10">Close (Blue) • EMA21 (Purple) • EMA50 (Amber) • Bollinger Bands (Dashed) [${fmtNum(minP)} – ${fmtNum(maxP)} PKR]</text>

      <line x1="${padL}" y1="${yRsi(70)}" x2="${w - padR}" y2="${yRsi(70)}" stroke="rgba(244,63,94,0.4)" stroke-dasharray="3,3" />
      <line x1="${padL}" y1="${yRsi(30)}" x2="${w - padR}" y2="${yRsi(30)}" stroke="rgba(16,185,129,0.4)" stroke-dasharray="3,3" />
      <polyline fill="none" stroke="#10b981" stroke-width="1.8" points="${rsiPts}" />
      <text x="${padL}" y="${rsiTop + 10}" fill="#10b981" font-size="10">Wilder RSI(14) — Overbought 70 / Oversold 30</text>
    </svg>
  `;
}

// ============================================================================
// 08. DATA QUALITY & LEGACY RECONCILIATION
// ============================================================================
async function renderReconciliationView(container) {
  const ticket = beginViewRender(container);
  const data = await apiGet("/api/reconciliation");
  const leg = data.legacy_reconciliation;
  const dq = data.data_quality;

  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `
    <div class="section-heading"><div><h2>Data checks, with evidence</h2><p>Reference parity is limited to the historical workbook scope shown below. Missing references are not a pass.</p></div></div>
    <section class="card"><h3>Why keep Data Quality?</h3><p>SQLite integrity checks the database file—not whether dates or prices are correct. Date checks detect swapped-date duplicates; reconciliation compares imported records with available references.</p><button class="btn btn-secondary" onclick="switchView('settings')">Open date scan &amp; backups</button></section>
    <div class="check-grid">
      ${Object.entries(leg).map(([key,result])=>`<section class="card"><div class="eyebrow">${escapeHtml(key.replaceAll('_',' '))}</div><h3 class="${result.status==='MATCH'?'pos':result.status==='DISCREPANCY'?'neg':''}">${escapeHtml(result.status.replaceAll('_',' '))}</h3><p>${escapeHtml(result.scope || result.reason)}</p><p>${fmtInt(result.checked_rows || 0)} rows checked${result.mismatches_count!==undefined ? ` · ${fmtInt(result.mismatches_count)} differences` : ''}</p><details><summary>View comparison evidence</summary><pre class="doc-viewer">${escapeHtml(JSON.stringify(result,null,2))}</pre></details></section>`).join('')}
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Unmatched Futures Contracts (No Same-Date Cash Close)</div>
            <div class="card-subtitle">Total across dataset: ${dq.unmatched_futures_contracts.count} contract-date rows • Displayed as N/A without date backfilling</div>
          </div>
        </div>
        <div class="table-wrap" style="max-height:320px;overflow-y:auto;">
          <table class="data-table">
            <thead><tr><th>Date</th><th>Contract Symbol</th><th>Base Symbol</th><th>Contract</th><th class="num">Future Close</th><th>Current Cash Value</th></tr></thead>
            <tbody>
              ${dq.unmatched_futures_contracts.items.map((u) => `
                <tr>
                  <td>${fmtDate(u.trade_date)}</td><td><b>${u.contract_symbol}</b></td><td>${u.base_symbol}</td><td>${u.contract_month}</td>
                  <td class="num">${fmtNum(u.future_close)}</td><td><span class="badge badge-amber">N/A (No Same-Date Cash Row)</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Indicator History Sufficiency Check</div>
            <div class="card-subtitle">${dq.indicator_history_checks.note}</div>
          </div>
        </div>
        <div class="table-wrap" style="max-height:320px;overflow-y:auto;">
          <table class="data-table">
            <thead><tr><th>Symbol</th><th class="num">Sessions Count</th><th>First Date</th><th>Last Date</th><th>Status</th></tr></thead>
            <tbody>
              ${dq.indicator_history_checks.tickers_under_26_bars.map((t) => `
                <tr>
                  <td><b>${t.symbol}</b></td><td class="num">${t.bars_count}</td><td>${fmtDate(t.first_date)}</td><td>${fmtDate(t.last_date)}</td>
                  <td><span class="badge badge-amber">&lt; 26 Bars (Insufficient for MACD)</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

// ============================================================================
// 09. EXPORTS, REPORTS, DOCUMENTATION & VERIFIED SKILLS
// ============================================================================
async function renderExportsView(container) {
  const ticket = beginViewRender(container);
  const meta = await apiGet('/api/docs');
  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `<div class="section-heading"><div><h2>Export your work</h2><p>Generated from your current database. Accounts remain separate; futures use each worksheet’s saved filters.</p></div></div>
    <div class="workflow-grid">${[
      ['Top 5 volume register','Ranked rates, volumes and trades.','top5_xlsx'],
      ['Account 91404','Isolated account workbook and audit sheets.','account_91404_xlsx'],
      ['Account 91269','Isolated account workbook and audit sheets.','account_91269_xlsx'],
      ['Futures analysis','Seven visible worksheets plus hidden source data.','futures_xlsx'],
      ['Technical analysis','Indicators, pivots and ticker history.','technical_xlsx']
    ].map(([name,desc,key])=>`<section class="card workflow-card"><h3>${name}</h3><p>${desc}</p><a class="btn btn-primary" href="${key==='futures_xlsx'?futuresExportUrl():'/api/exports/generate/'+key}" download>Download Excel</a></section>`).join('')}</div>
    <section class="card"><details><summary>Documentation &amp; release notes</summary><div class="docs-links">${meta.docs.map(d=>`<button class="btn btn-secondary" onclick="loadReleaseDoc('${escapeHtml(d.name)}')">${escapeHtml(d.name)}</button>`).join('')}</div><pre id="releaseDoc" class="doc-viewer">Choose a document.</pre></details></section>`;
}
async function loadReleaseDoc(name) {
  const doc = await apiGet('/api/docs/'+encodeURIComponent(name));
  document.getElementById('releaseDoc').textContent = doc.content;
}

// ============================================================================
// 10. SETTINGS, RULE VERSIONING & SQLITE BACKUP
// ============================================================================
async function renderSettingsView(container) {
  const ticket = beginViewRender(container);
  const data = await apiGet("/api/settings", false);
  const s = data.settings;
  const rules = data.rule_versions || [];
  const cs = data.cloud_sync || {};

  if (!currentViewRender(container, ticket)) return;
  container.innerHTML = `
    <div class="card card-hero">
      <div class="card-header">
        <div>
          <div class="card-title">Cloud persistence &amp; sync</div>
          <div class="card-subtitle">Status: <b class="${cs.health === "ACTIVE" ? "pos" : "warn"}">${cs.provider || "Local Mode"}</b> ${cs.repo ? `• Repo: <b>${cs.repo}</b> (${cs.branch})` : ""}${cs.last_push ? ` • Last push: <span style="color:var(--text-muted);">${fmtDate(cs.last_push)}</span>` : ""}${cs.last_push_sha ? ` • SHA: <code>${String(cs.last_push_sha).slice(0, 7)}</code>` : ""}</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          ${renderSyncButtons(cs)}
        </div>
      </div>
      <div style="font-size:12px;color:var(--text-main);">
        ${cs.backend==='turso' ? 'Direct Turso persistence is enabled. Private connection credentials stay on the server. A successful import or settings response confirms a remote database commit—not a GitHub snapshot upload. For independent backups, open your database in Turso and select Download SQLite File. Keep original uploads separately.' : 'Local SQLite development mode. Serverless deployments require Turso connection settings.'}
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Configurable Financial &amp; Technical Parameters</div>
            <div class="card-subtitle">Active Rule Version: <b>v${s.rule_version || 1}</b> • Saving creates an immutable entry in calculation_rules</div>
          </div>
          <button class="btn btn-primary" onclick="saveSettings()">💾 Save Settings</button>
        </div>
        <table class="data-table">
          <tbody>
            <tr><td><label for="set_slab1_upper"><b>Commission Slab 1 Upper Rate (PKR)</b></label></td><td><input type="number" step="0.01" id="set_slab1_upper" value="${s.commission_slab1_upper}" /></td></tr>
            <tr><td><label for="set_slab1_paisa"><b>Commission Slab 1 Paisa / Share</b></label></td><td><input type="number" step="0.0001" id="set_slab1_paisa" value="${s.commission_slab1_paisa_per_share}" /></td></tr>
            <tr><td><label for="set_slab2_start"><b>Commission Slab 2 Starting Rate (PKR)</b></label></td><td><input type="number" step="0.01" id="set_slab2_start" value="${s.commission_slab2_start}" /></td></tr>
            <tr><td><label for="set_slab2_rate"><b>Commission Slab 2 Rate (Decimal, 0.000325 = 0.0325%)</b></label></td><td><input type="number" step="0.000001" id="set_slab2_rate" value="${s.commission_slab2_rate}" /></td></tr>
            <tr><td><label for="set_sst_rate"><b>Sindh Sales Tax (SST) Rate (Decimal, 0.13 = 13%)</b></label></td><td><input type="number" step="0.01" id="set_sst_rate" value="${s.sst_rate}" /></td></tr>
            <tr><td><label for="set_fut_days"><b>Default Futures Days to Expiry</b></label></td><td><input type="number" step="1" id="set_fut_days" value="${s.default_futures_days ?? s.futures_default_days ?? 30}" /></td></tr>
            <tr><td><label for="set_fut_months"><b>Futures Rolling Retention Window (Months)</b></label></td><td><input type="number" step="1" id="set_fut_months" value="${s.futures_rolling_months ?? s.futures_rolling_retention_months ?? 2}" /></td></tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Database Backup &amp; Restore</div>
            <div class="card-subtitle">${cs.backend==='turso' ? 'Database connection' : 'Database integrity'}: <b class="${data.db_integrity.ok ? "pos" : "neg"}">${data.db_integrity.ok ? (cs.backend==='turso' ? "Connected (not a full integrity audit)" : "PRAGMA integrity_check = OK") : "FAILED"}</b> • Path: ${data.db_integrity.db_path}</div>
          </div>
          ${cs.backend==='turso' ? '<a class="btn btn-success" href="https://app.turso.tech" target="_blank" rel="noopener noreferrer">Open Turso to download SQLite backup</a>' : '<button class="btn btn-success" onclick="createManualBackup()">+ Create New Backup (.zip)</button>'}
        </div>
        ${cs.backend==='turso' ? '<p style="white-space:normal;line-height:1.7;">Backups are downloaded outside Vercel. Use Turso → your database → Download SQLite File. To restore, import into a new database, verify it, then switch server credentials. Do not overwrite the active database.</p>' : ''}
        <div class="table-wrap" ${cs.backend==='turso' ? 'style="display:none"' : ''}>
          <table class="data-table">
            <thead><tr><th>Backup Archive</th><th>Created at (PKT)</th><th class="num">Size</th><th>Integrity</th><th>Actions</th></tr></thead>
            <tbody>
              ${data.backups.length===0?`<tr><td colspan="5">${cs.backend==='turso' ? 'Backups are downloaded outside Vercel. Use Turso → your database → Download SQLite File. To restore, import into a new database, verify it, then switch server credentials. This avoids overwriting the active database.' : 'No local backups yet. Create and download an independent backup.'}</td></tr>`:''}
              ${data.backups.map((b) => `
                <tr>
                  <td><b>${escapeHtml(b.zip_filename)}</b><br><span style="color:var(--text-muted);font-size:10.5px;">SHA256: ${(b.db_sha256 || "").slice(0, 16)}...</span></td>
                  <td>${fmtDate(b.created_at || "")}</td>
                  <td class="num">${fmtInt(b.zip_size_bytes)} B</td>
                  <td><span class="badge ${b.integrity_ok ? "badge-green" : "badge-red"}">${b.integrity_ok ? "VERIFIED" : "ERR"}</span></td>
                  <td>
                    <a class="btn btn-secondary" style="padding:3px 8px;font-size:11px;" href="/api/backups/download/${encodeURIComponent(b.zip_filename)}" download>Download</a>
                    <button class="btn btn-secondary" style="padding:3px 8px;font-size:11px;" onclick="restoreBackup('${b.zip_filename}')">Restore</button>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Date Normalization &amp; Integrity Scanner</div>
          <div class="card-subtitle">Proposes corrections for a limited class of day/month-swapped rows. Review the dry-run evidence first — nothing changes until you confirm. A clean scan does not prove every historical date is correct.</div>
        </div>
        <button class="btn btn-primary" onclick="scanDateNormalization()" ${cs.backend==='turso'?'disabled title="Full-history maintenance scans are disabled on serverless Turso mode"':''}>🔎 Scan for Swapped Dates</button>
      </div>
      <div id="dateRepairResults" style="color:var(--text-muted);font-size:12.5px;">
        ${cs.backend==='turso' ? 'Bulk heuristic scans/repairs are disabled in remote mode. Source-verified XLSX import date protection remains active. Download an independent backup before offline maintenance.' : 'Click Scan to inspect the supported canonical date tables.'} The scanner uses unambiguous dates as anchors to identify swap candidates and duplicate artifacts. Review the plan against source files before applying. A verified online backup and audit record are kept; changed data requires a fresh scan. Reapplying a completed plan makes no further changes.
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Calculation Rule Version History (calculation_rules)</div>
          <div class="card-subtitle">Audit trail of formula and threshold parameter changes</div>
        </div>
      </div>
      ${rules.length === 0 ? `<p style="color:var(--text-muted);">Using baseline v1 calculation rules. Any parameter changes saved above will be logged here with version numbers and timestamps.</p>` : `
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>ID</th><th>Version</th><th>Rule Note</th><th>Effective Date</th><th>Timestamp</th><th>Parameters</th></tr></thead>
            <tbody>
              ${rules.map((r) => `
                <tr>
                  <td class="num">#${r.id}</td>
                  <td><span class="badge badge-blue">v${r.version}</span></td>
                  <td><b>${r.rule_name}</b></td>
                  <td>${r.effective_from}</td>
                  <td>${fmtDate(r.created_at || "")}</td>
                  <td style="font-family:var(--font-mono);font-size:11px;">${r.parameters_json}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}

async function saveSettings() {
  const updates = {
    commission_slab1_upper: Number(document.getElementById("set_slab1_upper").value),
    commission_slab1_paisa_per_share: Number(document.getElementById("set_slab1_paisa").value),
    commission_slab2_start: Number(document.getElementById("set_slab2_start").value),
    commission_slab2_rate: Number(document.getElementById("set_slab2_rate").value),
    sst_rate: Number(document.getElementById("set_sst_rate").value),
    futures_default_days: Number(document.getElementById("set_fut_days").value),
    futures_rolling_retention_months: Number(document.getElementById("set_fut_months").value),
  };
  const saved = await checkedMutation("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updates, notes: "Updated via Settings UI" }),
  });
  clearClientCache();
  syncNotice(saved, "Settings saved; new rule version recorded.");
  renderSettingsView(document.getElementById("viewContainer"));
}

async function createManualBackup() {
  await checkedMutation("/api/backups/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label: "manual_snapshot", include_raw_archive: false }),
  });
  showToast("SQLite online backup created and verified with SHA-256.");
  renderSettingsView(document.getElementById("viewContainer"));
}

async function triggerCloudSyncNow() {
  const res = await fetch("/api/cloud-sync/sync-now", { method: "POST" });
  const out = await res.json();
  if (out.backend === "turso" && out.saved) {
    clearClientCache();
    showToast("Turso connection verified. Changes are committed directly to the remote database.");
  } else if (out.pushed) {
    clearClientCache();
    showToast(`✓ Synced latest_cloud_sync.db.gz (${fmtInt(out.size_bytes)} B) to GitHub (Commit ${out.commit_sha.slice(0, 7)}) — cloud save confirmed. Existing workers may need Reload cloud data; keep an independent backup.`);
  } else if (out.error) {
    showToast(`⚠ GitHub push failed: ${out.error}\n(Local snapshot saved — use 'Download Updated latest_cloud_sync.db.gz' if needed.)`, true);
  } else {
    showToast(out.message || "Local .db.gz snapshot created.", !out.local_snapshot_updated);
  }
  if (state.currentView === "settings") renderSettingsView(document.getElementById("viewContainer"));
  if (state.currentView === "import") renderImportCenter(document.getElementById("viewContainer"));
}

async function restoreBackup(zipFilename) {
  if (!confirm("Restore this backup? A safety backup is created first. The restored database must then be saved to the cloud.")) return;
  const res = await fetch("/api/backups/restore", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zip_filename: zipFilename }),
  });
  if (res.ok) {
    clearClientCache();
    syncNotice(await res.json(), `Database restored from ${zipFilename}; safety backup saved.`);
    renderSettingsView(document.getElementById("viewContainer"));
  } else {
    showToast((await res.json()).detail || "Backup restore failed.", true);
  }
}

let _dateRepairPlan = null;

async function scanDateNormalization() {
  const box = document.getElementById("dateRepairResults");
  box.innerHTML = `<span style="color:var(--text-muted);">Scanning all dated tables…</span>`;
  try {
    const res = await fetch("/api/admin/date-normalization/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const plan = await res.json();
    _dateRepairPlan = plan;
    const t = plan.totals;
    let html = `<div style="color:var(--text-main);font-weight:600;margin-bottom:6px;">${t.candidates === 0
      ? "✅ No repair candidates found by this scanner. This does not prove every date is correct."
      : `⚠ Found <b>${fmtInt(t.candidates)}</b> polluted row(s): ${fmtInt(t.move)} to flip to their true date, ${fmtInt(t.duplicate_drop)} duplicate-pollution row(s) to drop, ${fmtInt(t.conflict)} conflict(s) to resolve.`}</div>`;
    html += `<table class="data-table"><thead><tr><th>Table</th><th>Anchor window (day&gt;12 proofs)</th><th class="num">Rows</th><th class="num">Polluted</th><th class="num">Flip</th><th class="num">Drop dup</th><th class="num">Conflicts</th><th>Sample</th></tr></thead><tbody>`;
    for (const sec of plan.tables) {
      const sample = (sec.samples || []).slice(0, 2).map((s) => `${s.from} → ${s.to} <span style="color:var(--text-muted);">(${s.action})</span>`).join("<br>");
      html += `<tr><td><b>${sec.table}</b></td><td>${sec.anchors ? `${fmtDate(sec.anchors.min)} → ${fmtDate(sec.anchors.max)}` : "—"}</td><td class="num">${fmtInt(sec.total_rows)}</td><td class="num">${fmtInt(sec.candidates)}</td><td class="num">${fmtInt(sec.move)}</td><td class="num">${fmtInt(sec.duplicate_drop)}</td><td class="num">${fmtInt(sec.conflict)}</td><td style="font-size:10.5px;">${sample}</td></tr>`;
    }
    html += `</tbody></table>`;
    if (t.candidates > 0) {
      html += `<div style="margin-top:10px;"><button class="btn btn-success" onclick="applyDateNormalization()">✔ Apply Repair (${fmtInt(t.candidates)} rows)</button> <span style="font-size:11.5px;color:var(--text-muted);">One transaction • DB copy kept before applying • audit-logged • idempotent (re-scan afterwards shows 0)</span></div>`;
    }
    box.innerHTML = html;
  } catch (e) {
    console.error(e);
    box.innerHTML = `<span style="color:var(--neg-red);">Scan failed: ${e.message}</span>`;
  }
}

async function applyDateNormalization() {
  const t = _dateRepairPlan ? _dateRepairPlan.totals : null;
  const n = t ? fmtInt(t.candidates) : "?";
  if (!confirm(`Apply the date-normalization repair to ${n} polluted row(s)?\n• A copy of the database is saved first\n• Everything runs in one transaction, logged in the audit trail\n• You may re-upload the clean .xlsx yearbooks afterwards (optional) to re-verify values`)) return;
  const box = document.getElementById("dateRepairResults");
  box.innerHTML = `<span style="color:var(--text-muted);">Applying repair…</span>`;
  try {
    const res = await fetch("/api/admin/date-normalization/apply", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true, plan_token: _dateRepairPlan?.plan_token }) });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const out = await res.json();
    clearClientCache();
    syncNotice(out, `Date repair applied: ${fmtInt(out.applied_count)} rows fixed (${out.idempotent_check}).`);
    _dateRepairPlan = null;
    await scanDateNormalization();
  } catch (e) {
    console.error(e);
    box.innerHTML = `<span style="color:var(--neg-red);">Apply failed: ${e.message}</span>`;
  }
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

window.addEventListener("DOMContentLoaded", bootWorkspace);

// Password-free startup, accessibility, independent exports and mobile shell.
const viewTickets = new WeakMap();
function beginViewRender(container) { const token = {}; viewTickets.set(container, token); return token; }
function currentViewRender(container, token) { return container.isConnected && viewTickets.get(container) === token; }
function futuresExportUrl() {
  const keys = ['monthly_comparison','month_filter','symbol_filter','annualized_comparison','date_filter','future_symbol_summary','date_summary'];
  const filters = {apply_rolling: state.futures.apply_rolling};
  keys.forEach(key => { const {date_manual, ...values} = state.futures[key]; filters[key] = values; });
  filters.symbol_filter.selected_date = 'ALL';
  return '/api/exports/generate/futures_xlsx?sheet_filters='+encodeURIComponent(JSON.stringify(filters));
}
async function checkedMutation(url, options) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) { showToast(data.detail || 'Request failed.', true); throw new Error(data.detail || 'Request failed'); }
  return data;
}
function syncNotice(result, message) {
  const sync = result.cloud_sync;
  if (sync?.saved && sync?.backend==='turso') showToast(message+' Saved directly to Turso.');
  else if (sync?.pushed) showToast(message+' Cloud save confirmed.');
  else if (sync) showToast(message+' NOT confirmed in cloud. Download a snapshot from Settings. '+(sync.error || sync.message || ''), true);
  else showToast(message);
}
async function reloadCloudData() {
  if (!confirm('Refresh database views? In Turso mode this clears view caches without copying or replacing the database.')) return;
  try {
    const result = await checkedMutation('/api/cloud-sync/reload', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirm:true})});
    clearClientCache();
    showToast(result.backend==='turso' ? 'Turso views refreshed.' : (result.pulled ? 'Latest cloud snapshot loaded.' : (result.reason || 'No snapshot loaded.')), result.backend!=='turso' && !result.pulled);
    await refreshCurrentView();
  } catch (_) { /* checkedMutation displayed the reason */ }
}
function toggleMenu(force) {
  const open = force ?? !document.body.classList.contains('menu-open');
  document.body.classList.toggle('menu-open',open);
  document.getElementById('menuToggle').setAttribute('aria-expanded',String(open));
  document.querySelector('.drawer-backdrop').hidden = !open;
  if (open) document.querySelector('.sidebar-nav button.active')?.focus();
}
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.body.classList.contains('menu-open')) { toggleMenu(false); document.getElementById('menuToggle').focus(); }
  if (event.key === 'Tab' && document.body.classList.contains('menu-open')) {
    const buttons = [...document.querySelectorAll('.sidebar button')];
    if (event.shiftKey && document.activeElement===buttons[0]) {event.preventDefault();buttons.at(-1).focus();}
    else if (!event.shiftKey && document.activeElement===buttons.at(-1)) {event.preventDefault();buttons[0].focus();}
  }
});
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.getElementById('themeToggle').textContent = theme==='dark' ? 'Light mode' : 'Dark mode';
}
function toggleTheme() {
  const theme = document.documentElement.dataset.theme==='dark'?'light':'dark';
  localStorage.setItem('psx_theme',theme); setTheme(theme);
}
async function bootWorkspace() {
  setTheme(localStorage.getItem('psx_theme') || (matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
  await verifyWorkspaceFreshness(false);
  await switchView('overview');
  updateSystemStatus();
  setInterval(() => { if (!document.hidden && !state.commitInFlight && !state.stagedBatch) refreshIfCloudChanged(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden && !state.commitInFlight && !state.stagedBatch) refreshIfCloudChanged(); });
}
async function updateSystemStatus() {
  try {
    const result = await apiGet('/api/system/status', false);
    const integrity = result.database_integrity.ok;
    document.getElementById('sidebarDbStatus').textContent = result.cloud_sync.backend === 'turso' ? (integrity ? 'Turso: connected' : 'Turso: unavailable') : (integrity ? 'SQLite integrity: OK' : 'SQLite integrity: FAILED');
    document.getElementById('sidebarLastImport').textContent = 'Cloud: '+result.cloud_sync.health+' · Reference parity checked separately';
  } catch (_) {document.getElementById('sidebarDbStatus').textContent='Status unavailable';}
}
// Add accessible names to existing legacy controls; date input locale is supplemented by a fixed-format readout.
let enhancementQueued = false;
const observer = new MutationObserver(() => {
  if (enhancementQueued) return;
  enhancementQueued = true;
  requestAnimationFrame(() => { enhanceWorkspace(); enhancementQueued=false; });
});
observer.observe(document.getElementById('appShell'), {childList:true,subtree:true});
function enhanceWorkspace() {
  const root = document.getElementById('viewContainer');
  if (!root) return;
  root.querySelectorAll('input,select,textarea').forEach((el,index)=> {
    if (!el.id) el.id='control-'+index;
    const group = el.closest('.filter-group');
    const label = group?.querySelector('label') || el.closest('tr')?.querySelector('label');
    if (label && !label.querySelector('input')) label.htmlFor=el.id;
    if (!el.getAttribute('aria-label') && !document.querySelector(`label[for="${CSS.escape(el.id)}"]`) && !el.closest('label')) el.setAttribute('aria-label', el.placeholder || (el.closest('tr')?.cells[0]?.textContent.trim()) || (el.type==='file'?'Choose files':'Worksheet filter'));
    if (el.type==='date' && !group?.querySelector('.date-readout') && !el.nextElementSibling?.classList.contains('date-readout')) {
      const readout=document.createElement('span'); readout.className='date-readout'; readout.textContent=fmtDate(el.value); el.after(readout);
    }
  });
  root.querySelectorAll('.table-wrap').forEach(el=>{el.tabIndex=0;el.setAttribute('role','region');el.setAttribute('aria-label','Scrollable data table');});
  root.querySelectorAll('table:not(.table-wrap table)').forEach(table=>{
    if (table.querySelector('#set_slab1_upper')) {table.classList.add('settings-table');return;}
    const wrapper=document.createElement('div');wrapper.className='table-wrap';table.replaceWith(wrapper);wrapper.append(table);
  });
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  let node;const edits=[];
  while ((node=walker.nextNode())) {
    if (node.parentElement.closest('pre,code,script,style,textarea')) continue;
    if (/\d{4}-\d{2}-\d{2}/.test(node.nodeValue)) {
      const text=node.nodeValue.replace(/\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))?\b/g,fmtDate);
      if (text!==node.nodeValue) edits.push([node,text]);
    }
  }
  edits.forEach(([n,text])=>n.nodeValue=text);
}

async function renderLatestBadge(view) {
  const dates = await apiGet('/api/data-dates');
  if (state.currentView !== view) return;
  const key = ({top5:'top5',futures:'futures',technical:'cash',acc91404:'acc91404',acc91269:'acc91269'})[view] || 'latest';
  let badge = document.getElementById('moduleLatestBadge');
  if (!badge) {badge = document.createElement('span');badge.id='moduleLatestBadge';badge.className='badge badge-green';document.getElementById('viewTitle').after(badge);}
  badge.textContent = dates[key] ? 'Auto → Latest: '+fmtDate(dates[key]) : 'No imported data';
  badge.title = 'Latest imported date for this module (not the computer date). Each dataset retains its own coverage.';
}

async function verifyWorkspaceFreshness(force=false) {
  if (state.freshnessInFlight) return state.freshnessInFlight;
  state.freshnessInFlight = (async () => {
    let result;
    try {
      const response = await fetch('/api/system/freshness?force='+force, {cache:'no-store'});
      if (!response.ok) throw new Error('HTTP '+response.status);
      result = await response.json();
    } catch (error) { result = {status:'UNVERIFIED',changed:false,message:'Cloud freshness could not be checked. Displayed data may be old. '+error.message}; }
    result.browserChanged = !!result.changed || (state.lastSnapshotId !== null && result.snapshot_id && state.lastSnapshotId !== result.snapshot_id);
    if (result.browserChanged) state.apiCache = {};
    if (result.snapshot_id) state.lastSnapshotId = result.snapshot_id;
    state.freshnessStatus = result.status;
    const notice = document.getElementById('dataFreshnessNotice');
    const versionChanged = result.version && result.version !== '1.3.6';
    if (notice) {
      notice.classList.toggle('hidden', ['CURRENT','LOCAL'].includes(result.status) && !versionChanged);
      notice.textContent = versionChanged ? 'A newer dashboard build is deployed. Reload this page to update the interface.' : (result.message || '');
    }
    return result;
  })();
  try { return await state.freshnessInFlight; } finally { state.freshnessInFlight = null; }
}
async function refreshIfCloudChanged() {
  const result = await verifyWorkspaceFreshness(false);
  if (result.browserChanged && !state.commitInFlight && !state.stagedBatch) {
    clearClientCache();
    await switchView(state.currentView);
    updateSystemStatus();
    showToast('Cloud data changed. Dates and analysis were refreshed; historical pins were preserved.');
  }
}
function exportCurrentModule() {
  const account = state.currentView === 'acc91404' ? '91404' : state.currentView === 'acc91269' ? '91269' : null;
  const key = account ? 'account_'+account+'_xlsx' : ({top5:'top5_xlsx',technical:'technical_xlsx'})[state.currentView];
  if (state.currentView === 'futures') {window.location.href=futuresExportUrl();return;}
  if (key) {window.location.href='/api/exports/generate/'+key;return;}
  showToast('Download from the Top 5, Account, Futures or Technical module. Full database backups are in Settings and Backup.');
}
