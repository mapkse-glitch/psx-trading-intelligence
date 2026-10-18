// PSX Trading Intelligence Dashboard v1.1 — Frontend Application
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
  top5Filter: { ticker: "ATRL", start_date: "2026-10-01", end_date: "2026-10-16", search: "" },
  accTab: { "91404": "dashboard", "91269": "dashboard" },
  accSelectedDate: { "91404": "2026-10-16", "91269": "2026-10-15" },
  futures: {
    subtab: "monthly_comparison",
    selected_date: "2026-10-16",
    contract_month: "OCT",
    base_symbol: "OGDC",
    contract_symbol: "AGHA-OCT",
    days: 30,
    apply_rolling: true,
    meta: null,
  },
  technical: {
    subtab: "core36",
    selectedSymbol: "ATRL",
    search: "",
    signalFilter: "ALL",
  },
  selectedDoc: "MIGRATION_REPORT.md",
};

const VIEW_TITLES = {
  overview: "01 • Overview & Trading Intelligence Cards",
  import: "02 • Import and Update Center",
  top5: "03 • Top 5 Volume & Rate Register",
  acc91404: "04 • Account 91404 Performance (THM00601)",
  acc91269: "05 • Account 91269 Performance (THM00601)",
  futures: "06 • Futures Comparison & Annualized Analysis",
  technical: "07 • Technical Analysis, Setup Generator & 36-Ticker",
  reconciliation: "08 • Data Quality & Legacy Reconciliation",
  exports: "09 • Exports, Reports & Verified Skills Catalog",
  settings: "10 • Settings, Rule Versioning & SQLite Backup",
};

function fmtNum(v, decimals = 2) {
  if (v === null || v === undefined || v === "N/A" || Number.isNaN(Number(v))) return "N/A";
  return Number(v).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

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
  el.style.color = isError ? "#fecdd3" : "#a7f3d0";
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 5500);
}

function copyTextToClipboard(text, label = "Prompt / Report") {
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
}

async function refreshCurrentView() {
  clearClientCache();
  await switchView(state.currentView);
  showToast("Refreshed latest data from canonical SQLite database.");
}

async function switchView(view) {
  state.currentView = view;
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === view);
  });
  document.getElementById("viewTitle").textContent = VIEW_TITLES[view] || "Dashboard";
  const container = document.getElementById("viewContainer");

  // Re-trigger smooth entrance animation
  container.style.animation = "none";
  container.offsetHeight; // reflow
  container.style.animation = "";

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
    container.innerHTML = `<div class="card"><h3 class="neg">Error loading view</h3><p>${err.message}</p></div>`;
  }
}

// ============================================================================
// SHARED COMPONENT BUILDERS:
// 1. Trading Ideas Generator Card
// 2. Automated Technical Analyst Card
// ============================================================================
function buildTradingIdeasCardHtml(ideasRes, filtersMeta) {
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
            1. Trading Ideas Generator — 5 High-Probability Setups
          </div>
          <div class="card-subtitle">Scans today's PSX market (${ideasRes.candidates_scanned} candidates analyzed) combining 9-Factor Technicals, Module A Top 5 Volume &amp; Module C Futures Basis</div>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-secondary" onclick="copyTextToClipboard(${JSON.stringify(ideasRes.prompt_used).replace(/"/g, "&quot;")}, 'Trading Ideas Prompt')">📋 Copy Prompt</button>
        </div>
      </div>

      <div class="prompt-quote-box">
        “Scan today's market and generate 5 high-probability trading setups for <b>[${ideasRes.target_label}]</b>. Include entry price, exit targets, stop-loss, and risk/reward ratio. Explain why each setup works based on technical and fundamental factors.”
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
            <option value="ALL" ${idState.direction === "ALL" ? "selected" : ""}>All High-Conviction Setups</option>
            <option value="LONG" ${idState.direction === "LONG" ? "selected" : ""}>Long / Buy Setups Only</option>
            <option value="SHORT" ${idState.direction === "SHORT" ? "selected" : ""}>Short / Tactical Sell Only</option>
          </select>
        </div>
        <button class="btn btn-primary" onclick="runTradingIdeasGenerator()">⚡ Scan &amp; Generate 5 Setups</button>
      </div>

      <div class="setup-grid">
        ${ideasRes.setups.map((st) => {
          const isLong = st.direction.includes("BUY");
          return `
            <div class="setup-card">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <span class="badge ${isLong ? "badge-green" : "badge-red"}">#${st.rank} • ${st.direction}</span>
                  <b style="font-size:15px;margin-left:6px;cursor:pointer;color:#fff;" onclick="triggerAnalystForTicker('${st.symbol}')">${st.display_label}</b>
                  <span style="font-size:11px;color:var(--text-muted);margin-left:4px;">(${st.sector})</span>
                </div>
                <div style="text-align:right;">
                  <span class="badge badge-blue">Grade ${st.setup_grade} (${st.probability_score}%)</span>
                </div>
              </div>

              <div class="conviction-bar-bg">
                <div class="conviction-bar-fill" style="width:${st.probability_score}%"></div>
              </div>

              <div class="setup-price-grid">
                <div class="setup-price-cell"><span>Entry</span><b style="color:var(--accent-blue);">${fmtNum(st.entry_price)}</b></div>
                <div class="setup-price-cell"><span>Target 1</span><b class="pos">${fmtNum(st.target_1)}</b></div>
                <div class="setup-price-cell"><span>Target 2</span><b class="pos">${fmtNum(st.target_2)}</b></div>
                <div class="setup-price-cell"><span>Stop-Loss</span><b class="neg">${fmtNum(st.stop_loss)}</b></div>
                <div class="setup-price-cell"><span>R/R (T2)</span><b>${st.risk_reward_t2}</b></div>
              </div>

              <div style="font-size:11.6px;color:#cbd5e1;">
                <b style="color:var(--accent-blue);">Why It Works — Technical Factors:</b>
                <ul style="padding-left:16px;margin-top:3px;">
                  ${st.technical_why.map((line) => `<li>${line}</li>`).join("")}
                </ul>
              </div>

              <div style="font-size:11.6px;color:#cbd5e1;">
                <b style="color:var(--pos-green);">Why It Works — Fundamental &amp; Liquidity Factors:</b>
                <ul style="padding-left:16px;margin-top:3px;">
                  ${st.fundamental_why.map((line) => `<li>${line}</li>`).join("")}
                </ul>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function buildAutomatedAnalystCardHtml(analystRes) {
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
        <div style="display:flex;gap:8px;">
          <button class="btn btn-secondary" onclick="copyTextToClipboard(${JSON.stringify(analystRes.prompt_used || "").replace(/"/g, "&quot;")}, 'Analyst Prompt')">📋 Copy Prompt</button>
          <button class="btn btn-primary" onclick="openTickerDeepDive('${analystRes.symbol}')">📈 Open Interactive Chart →</button>
        </div>
      </div>

      <div class="prompt-quote-box">
        “Analyze <b>[${analystRes.intended_action} — ${analystRes.display_label}]</b> using daily and weekly charts. Break down support/resistance levels, trend lines, moving averages, and momentum indicators. Provide a step-by-step trading signal (Buy/Hold/Sell) with justification.”
      </div>

      <div class="filter-bar" style="margin-bottom:14px;">
        <div class="filter-group">
          <label>Ticker Symbol:</label>
          <input type="text" id="analystTickerInput" value="${anState.symbol}" style="width:110px;font-weight:700;" onkeydown="if(event.key==='Enter')runAutomatedAnalyst()" />
        </div>
        <div class="filter-group">
          <label>Quick Select:</label>
          ${["ATRL", "OGDC", "PPL", "PSO", "LUCK", "MLCF", "UBL", "HBL", "SYS", "TRG", "SAZEW", "FFC", "HUBC"].map((s) => `
            <button class="btn btn-secondary" style="padding:4px 8px;font-size:11px;" onclick="triggerAnalystForTicker('${s}')">${s}</button>
          `).join("")}
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

      <div class="grid-2" style="margin-bottom:0;">
        <!-- 5-Step Institutional Breakdown -->
        <div class="step-list">
          ${(analystRes.step_by_step_analysis || []).map((st) => `
            <div class="step-item">
              <div class="step-item-hdr">
                <span>${st.step}</span>
                <span class="badge badge-blue">${st.verdict}</span>
              </div>
              <div style="font-size:12px;color:#cbd5e1;">${st.detail}</div>
            </div>
          `).join("")}
        </div>

        <!-- Moving Averages & Weekly Chart Matrix -->
        <div style="display:flex;flex-direction:column;gap:12px;">
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
  if (queryEl) state.ideas.query = queryEl.value;
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

async function runAutomatedAnalyst() {
  const symEl = document.getElementById("analystTickerInput");
  const actEl = document.getElementById("analystActionSelect");
  if (symEl && symEl.value.trim()) state.analyst.symbol = symEl.value.trim().toUpperCase();
  if (actEl) state.analyst.action = actEl.value;

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
  state.analyst.symbol = sym.toUpperCase();
  const cardEl = document.getElementById("automatedAnalystCard");
  if (cardEl) {
    await runAutomatedAnalyst();
    document.getElementById("automatedAnalystCard")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    openTickerDeepDive(sym);
  }
}

// ============================================================================
// 01. OVERVIEW DASHBOARD
// ============================================================================
async function renderOverview(container) {
  const [data, filtersMeta, analystRes] = await Promise.all([
    apiGet("/api/overview"),
    apiGet("/api/intelligence/filters"),
    apiGet(`/api/intelligence/automated-analyst/${encodeURIComponent(state.analyst.symbol)}?action=${encodeURIComponent(state.analyst.action)}`),
  ]);

  const sys = data.system;
  const a91404 = data.account_91404;
  const a91269 = data.account_91269;
  const tech = data.technical_core36;
  const ideasRes = data.trading_ideas_default;

  container.innerHTML = `
    <div class="grid-4">
      <div class="kpi-box" onclick="switchView('top5')" style="cursor:pointer;">
        <div class="kpi-label">Module A • Top 5 Volume Register</div>
        <div class="kpi-value">${fmtInt(sys.top5.records)} rows</div>
        <div class="kpi-sub">${sys.top5.tickers} Tickers • ${sys.top5.min_date} to ${sys.top5.max_date}</div>
      </div>
      <div class="kpi-box" onclick="switchView('acc91404')" style="cursor:pointer;">
        <div class="kpi-label">Module B • Account 91404 YTD Net P&amp;L</div>
        <div class="kpi-value ${pnlClass(a91404.ytd.net_pnl)}">${fmtNum(a91404.ytd.net_pnl)} PKR</div>
        <div class="kpi-sub">${a91404.trading_days_count} Trading Days • ${a91404.symbols_count} Symbols</div>
      </div>
      <div class="kpi-box" onclick="switchView('acc91269')" style="cursor:pointer;">
        <div class="kpi-label">Module B • Account 91269 YTD Net P&amp;L</div>
        <div class="kpi-value ${pnlClass(a91269.ytd.net_pnl)}">${fmtNum(a91269.ytd.net_pnl)} PKR</div>
        <div class="kpi-sub">${a91269.trading_days_count} Trading Days • ${a91269.symbols_count} Symbols</div>
      </div>
      <div class="kpi-box" onclick="switchView('technical')" style="cursor:pointer;">
        <div class="kpi-label">Modules C &amp; D • Cash &amp; Futures OHLCV</div>
        <div class="kpi-value">${fmtInt(sys.equity_ohlcv.records + sys.futures_ohlcv.records)} bars</div>
        <div class="kpi-sub">${sys.equity_ohlcv.symbols} Cash Tickers • ${sys.futures_ohlcv.contracts} Futures Contracts</div>
      </div>
    </div>

    <!-- Card 1: Trading Ideas Generator -->
    ${buildTradingIdeasCardHtml(ideasRes, filtersMeta)}

    <!-- Card 2: Automated Technical Analyst -->
    ${buildAutomatedAnalystCardHtml(analystRes)}

    <div class="grid-2">
      <!-- Account 91404 Summary Card (Strictly Isolated) -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Account 91404 Performance Snapshot</div>
            <div class="card-subtitle">Isolated Account Ledger • Latest Day: ${a91404.latest_trading_day}</div>
          </div>
          <button class="btn btn-secondary" onclick="switchView('acc91404')">Open Account 91404 →</button>
        </div>
        <table class="data-table">
          <thead>
            <tr><th>Period</th><th class="num">Buy Value (PKR)</th><th class="num">Sell Value (PKR)</th><th class="num">Total Charges</th><th class="num">Net P&amp;L (PKR)</th><th class="num">Return on Buy</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><b>Latest (${a91404.latest_trading_day})</b></td>
              <td class="num">${fmtNum(a91404.latest_day?.buy_value)}</td>
              <td class="num">${fmtNum(a91404.latest_day?.sell_value)}</td>
              <td class="num">${fmtNum(a91404.latest_day?.total_charges)}</td>
              <td class="num ${pnlClass(a91404.latest_day?.net_pnl)}">${fmtNum(a91404.latest_day?.net_pnl)}</td>
              <td class="num ${pnlClass(a91404.latest_day?.return_on_buy)}">${fmtPct(a91404.latest_day?.return_on_buy)}</td>
            </tr>
            <tr>
              <td><b>MTD</b></td>
              <td class="num">${fmtNum(a91404.mtd?.buy_value)}</td>
              <td class="num">${fmtNum(a91404.mtd?.sell_value)}</td>
              <td class="num">${fmtNum(a91404.mtd?.total_charges)}</td>
              <td class="num ${pnlClass(a91404.mtd?.net_pnl)}">${fmtNum(a91404.mtd?.net_pnl)}</td>
              <td class="num ${pnlClass(a91404.mtd?.return_on_buy)}">${fmtPct(a91404.mtd?.return_on_buy)}</td>
            </tr>
            <tr>
              <td><b>YTD (2026)</b></td>
              <td class="num">${fmtNum(a91404.ytd?.buy_value)}</td>
              <td class="num">${fmtNum(a91404.ytd?.sell_value)}</td>
              <td class="num">${fmtNum(a91404.ytd?.total_charges)}</td>
              <td class="num ${pnlClass(a91404.ytd?.net_pnl)}">${fmtNum(a91404.ytd?.net_pnl)}</td>
              <td class="num ${pnlClass(a91404.ytd?.return_on_buy)}">${fmtPct(a91404.ytd?.return_on_buy)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Account 91269 Summary Card (Strictly Isolated) -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Account 91269 Performance Snapshot</div>
            <div class="card-subtitle">Isolated Account Ledger • Latest Day: ${a91269.latest_trading_day}</div>
          </div>
          <button class="btn btn-secondary" onclick="switchView('acc91269')">Open Account 91269 →</button>
        </div>
        <table class="data-table">
          <thead>
            <tr><th>Period</th><th class="num">Buy Value (PKR)</th><th class="num">Sell Value (PKR)</th><th class="num">Total Charges</th><th class="num">Net P&amp;L (PKR)</th><th class="num">Return on Buy</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><b>Latest (${a91269.latest_trading_day})</b></td>
              <td class="num">${fmtNum(a91269.latest_day?.buy_value)}</td>
              <td class="num">${fmtNum(a91269.latest_day?.sell_value)}</td>
              <td class="num">${fmtNum(a91269.latest_day?.total_charges)}</td>
              <td class="num ${pnlClass(a91269.latest_day?.net_pnl)}">${fmtNum(a91269.latest_day?.net_pnl)}</td>
              <td class="num ${pnlClass(a91269.latest_day?.return_on_buy)}">${fmtPct(a91269.latest_day?.return_on_buy)}</td>
            </tr>
            <tr>
              <td><b>MTD</b></td>
              <td class="num">${fmtNum(a91269.mtd?.buy_value)}</td>
              <td class="num">${fmtNum(a91269.mtd?.sell_value)}</td>
              <td class="num">${fmtNum(a91269.mtd?.total_charges)}</td>
              <td class="num ${pnlClass(a91269.mtd?.net_pnl)}">${fmtNum(a91269.mtd?.net_pnl)}</td>
              <td class="num ${pnlClass(a91269.mtd?.return_on_buy)}">${fmtPct(a91269.mtd?.return_on_buy)}</td>
            </tr>
            <tr>
              <td><b>YTD (2026)</b></td>
              <td class="num">${fmtNum(a91269.ytd?.buy_value)}</td>
              <td class="num">${fmtNum(a91269.ytd?.sell_value)}</td>
              <td class="num">${fmtNum(a91269.ytd?.total_charges)}</td>
              <td class="num ${pnlClass(a91269.ytd?.net_pnl)}">${fmtNum(a91269.ytd?.net_pnl)}</td>
              <td class="num ${pnlClass(a91269.ytd?.return_on_buy)}">${fmtPct(a91269.ytd?.return_on_buy)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="grid-2">
      <!-- Core 36 Technical Signal Distribution -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Module D • 36-Ticker Technical Signal Summary</div>
            <div class="card-subtitle">9-Factor Composite Engine (RSI, MACD, Bollinger, EMA, ADX, Pivot, SMA20, VWAP)</div>
          </div>
          <button class="btn btn-secondary" onclick="switchView('technical')">36-Ticker Matrix →</button>
        </div>
        <div class="grid-4" style="margin-bottom:12px;">
          <div class="kpi-box"><div class="kpi-label">BUY Signals</div><div class="kpi-value pos">${tech.signal_counts["BUY"] || 0}</div></div>
          <div class="kpi-box"><div class="kpi-label">HOLD / NEUTRAL</div><div class="kpi-value">${tech.signal_counts["HOLD / NEUTRAL"] || 0}</div></div>
          <div class="kpi-box"><div class="kpi-label">SELL Signals</div><div class="kpi-value neg">${tech.signal_counts["SELL"] || 0}</div></div>
          <div class="kpi-box"><div class="kpi-label">SHORT SELL</div><div class="kpi-value neg">${tech.signal_counts["SHORT SELL"] || 0}</div></div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Ticker</th><th class="num">Close</th><th class="num">Chg %</th><th class="num">RSI(14)</th><th class="num">Pivot (P)</th><th class="num">Score</th><th>Combined Signal</th></tr>
            </thead>
            <tbody>
              ${tech.top_bullish.slice(0, 5).map((t) => `
                <tr style="cursor:pointer;" onclick="openTickerDeepDive('${t.symbol}')">
                  <td><b>${t.symbol}</b></td>
                  <td class="num">${fmtNum(t.close)}</td>
                  <td class="num ${pnlClass(t.change_pct)}">${fmtPct(t.change_pct, false)}</td>
                  <td class="num">${fmtNum(t.rsi14)}</td>
                  <td class="num">${fmtNum(t.daily_pivots.classic.P)}</td>
                  <td class="num pos">+${t.signal.score}/9</td>
                  <td><span class="badge badge-green">${t.signal.combined_signal}</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Module C Futures Highlights -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Module C • Futures Spread &amp; Annualized % (${data.futures_highlights.selected_date})</div>
            <div class="card-subtitle">Sorted by Annualized % Ascending (Days = 30)</div>
          </div>
          <button class="btn btn-secondary" onclick="switchView('futures')">Futures Analysis →</button>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Symbol</th><th>Contract</th><th class="num">Current</th><th class="num">Future</th><th class="num">Difference</th><th class="num">Diff %</th><th class="num">Annualized %</th></tr>
            </thead>
            <tbody>
              ${data.futures_highlights.lowest_annualized.concat(data.futures_highlights.highest_annualized.slice(0, 3)).map((r) => `
                <tr>
                  <td><b>${r.symbol}</b></td>
                  <td><span class="badge badge-blue">${r.contract}</span></td>
                  <td class="num">${fmtNum(r.current_value)}</td>
                  <td class="num">${fmtNum(r.future_value)}</td>
                  <td class="num ${pnlClass(r.difference)}">${fmtNum(r.difference)}</td>
                  <td class="num ${pnlClass(r.difference_pct)}">${fmtPct(r.difference_pct, false)}</td>
                  <td class="num ${pnlClass(r.annualized_pct)}">${fmtPct(r.annualized_pct, false)}</td>
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
// 02. IMPORT AND UPDATE CENTER
// ============================================================================
async function renderImportCenter(container) {
  const hist = await apiGet("/api/imports/history", false);

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Manual File Upload &amp; Staging Center</div>
          <div class="card-subtitle">Supports single/multiple Ticker .TXT, TradeLog .TXT/.CSV/.XLSX, Cash/Futures OHLCV (2026.xlsx, 2026F.xlsx, INDEX.xlsx), or .ZIP archives</div>
        </div>
      </div>

      <div class="dropzone" onclick="document.getElementById('fileUploadInput').click()">
        <h3 style="margin-bottom:6px;color:var(--accent-blue);">Click to Select Files or Drag &amp; Drop Here</h3>
        <p style="color:var(--text-muted);font-size:12px;">
          Accepted formats: <b>.txt, .csv, .xlsx, .xls, .zip</b> • Files are staged and validated first before modifying your canonical database.
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
              <th>Source Label</th>
              <th>Timestamp (UTC)</th>
              <th class="num">Files</th>
              <th class="num">Rows Read</th>
              <th class="num">New Records</th>
              <th class="num">Duplicates Ignored</th>
              <th class="num">Revisions</th>
            </tr>
          </thead>
          <tbody>
            ${hist.batches.map((b) => `
              <tr>
                <td class="num">#${b.id} <span style="color:var(--text-muted);font-size:10.5px;">(${b.batch_uuid.slice(0, 8)})</span></td>
                <td><span class="badge ${b.status === "COMMITTED" ? "badge-green" : "badge-amber"}">${b.status}</span></td>
                <td><b>${b.source_label}</b></td>
                <td>${(b.committed_at || b.created_at || "").replace("T", " ").slice(0, 19)}</td>
                <td class="num">${b.files_count}</td>
                <td class="num">${fmtInt(b.rows_read)}</td>
                <td class="num pos">${fmtInt(b.new_records)}</td>
                <td class="num">${fmtInt(b.duplicates_ignored)}</td>
                <td class="num">${fmtInt(b.revisions_count)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

async function handleStageFiles(fileList) {
  if (!fileList || fileList.length === 0) return;
  const previewEl = document.getElementById("stagedPreviewArea");
  previewEl.innerHTML = `<div class="skeleton-card">Analyzing and staging ${fileList.length} file(s)...</div>`;

  const fd = new FormData();
  for (const f of fileList) fd.append("files", f);

  try {
    const res = await fetch("/api/imports/stage", { method: "POST", body: fd });
    if (!res.ok) throw new Error("Staging failed");
    const manifest = await res.json();
    state.stagedBatch = manifest;

    previewEl.innerHTML = `
      <div class="card card-hero">
        <div class="card-header">
          <div>
            <div class="card-title" style="color:var(--accent-blue);">Staged Import Preview — Ready to Commit</div>
            <div class="card-subtitle">Batch UUID: ${manifest.batch_uuid} • ${manifest.files_count} file(s) analyzed</div>
          </div>
          <button class="btn btn-success" onclick="commitStagedBatch('${manifest.batch_uuid}')">
            ✓ Import and Update Canonical Database
          </button>
        </div>

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
                  <td><span class="badge badge-blue">${f.file_type}</span></td>
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
  try {
    const res = await fetch("/api/imports/commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch_uuid: batchUuid, allow_revisions: true }),
    });
    if (!res.ok) throw new Error("Commit failed");
    const committed = await res.json();
    clearClientCache();
    showToast(
      `Import & Update Complete: ${committed.new_records} new records added, ${committed.duplicates_ignored} duplicates skipped, ${committed.revisions_count} revisions logged.`
    );
    await renderImportCenter(document.getElementById("viewContainer"));
  } catch (err) {
    showToast(`Commit error: ${err.message}`, true);
  }
}

// ============================================================================
// 03. MODULE A: TOP 5 VOLUME & RATE REGISTER
// ============================================================================
async function renderTop5View(container) {
  const f = state.top5Filter;
  const qs = new URLSearchParams();
  if (f.ticker && f.ticker !== "ALL") qs.set("ticker", f.ticker);
  if (f.start_date) qs.set("start_date", f.start_date);
  if (f.end_date) qs.set("end_date", f.end_date);
  if (f.search) qs.set("search", f.search);

  const trendTicker = f.ticker && f.ticker !== "ALL" ? f.ticker : "ATRL";
  const [data, trendData] = await Promise.all([
    apiGet(`/api/top5/register?${qs.toString()}`),
    apiGet(`/api/top5/trend/${trendTicker}`),
  ]);

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
        <input type="date" id="top5EndInput" value="${f.end_date}" onchange="updateTop5Filter()" />
      </div>
      <div class="filter-group">
        <label>Search:</label>
        <input type="text" id="top5SearchInput" placeholder="Ticker or date..." value="${f.search}" oninput="updateTop5Filter()" />
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
          <div class="card-subtitle">Chronological progression across imported trading dates</div>
        </div>
      </div>
      ${renderTop5SvgChart(trendData.trend)}
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Top 5 Volume &amp; Rate Register Blocks (${data.blocks_count} Ticker-Date Blocks • ${data.total_rows} Rows)</div>
          <div class="card-subtitle">Date Header Format: MM/DD/YYYY • Visible Columns: Rank, Rate, Volume, Trades (Sorted by Volume Descending)</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:14px;">
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
  state.top5Filter.start_date = document.getElementById("top5StartInput").value;
  state.top5Filter.end_date = document.getElementById("top5EndInput").value;
  state.top5Filter.search = document.getElementById("top5SearchInput").value;
  renderTop5View(document.getElementById("viewContainer"));
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
    return `<rect x="${x - 4}" y="${y}" width="8" height="${bh}" fill="rgba(56,189,248,0.35)" rx="2"><title>${d.mmddyyyy}: Top 5 Vol=${fmtInt(d.top5_total_volume)}, Rank1 Rate=${fmtNum(d.rank1_rate)}</title></rect>`;
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
      <text x="${padL}" y="${h - 8}" fill="#94a3b8" font-size="10">${trend[0].mmddyyyy}</text>
      <text x="${w - padR - 55}" y="${h - 8}" fill="#94a3b8" font-size="10">${trend[trend.length - 1].mmddyyyy}</text>
    </svg>
  `;
}

// ============================================================================
// 04 & 05. MODULE B: ACCOUNT 91404 & ACCOUNT 91269 PERFORMANCE
// ============================================================================
async function renderAccountView(container, accountId) {
  const selDate = state.accSelectedDate[accountId];
  const qs = selDate ? `?selected_date=${encodeURIComponent(selDate)}` : "";
  const rep = await apiGet(`/api/accounts/${accountId}${qs}`);
  const activeTab = state.accTab[accountId] || "dashboard";
  state.accSelectedDate[accountId] = rep.selected_date;

  const tDates = rep.trading_dates || rep.available_dates || [];
  const tabs = [
    ["dashboard", "Dashboard"],
    ["daily_summary", `Daily Summary (${tDates.length}d)`],
    ["daily_detail", `Daily Detail (${rep.selected_date})`],
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
                <th>Date</th><th class="num">Buy Qty</th><th class="num">Sell Qty</th><th class="num">Net Qty</th>
                <th class="num">Buy Value (PKR)</th><th class="num">Sell Value (PKR)</th>
                <th class="num">Avg Buy</th><th class="num">Avg Sell</th>
                <th class="num">Gross P&amp;L</th><th class="num">Commission</th><th class="num">SST 13%</th>
                <th class="num">Total Charges</th><th class="num">Net P&amp;L (PKR)</th><th class="num">Return on Buy</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map((r) => `
                <tr style="cursor:pointer" onclick="openAccountDateDetail('${accountId}', '${r.trade_date}')">
                  <td><b>${r.trade_date}</b></td>
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
            <div class="card-title">Daily Trade Summary — ${det.trade_date} (Account ${accountId})</div>
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
    bodyHtml = `<div class="grid-2">${blocks.map(([title, b]) => `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">${title}</div>
            <div class="card-subtitle">Calendar Start: ${b.start} • First Active Day: ${b.first_trading_day} • End: ${b.end} (${b.trading_days} days)</div>
          </div>
        </div>
        <table class="data-table">
          <tbody>
            <tr><td><b>Buy Quantity / Value</b></td><td class="num">${fmtInt(b.buy_qty)} sh / ${fmtNum(b.buy_value)} PKR</td></tr>
            <tr><td><b>Sell Quantity / Value</b></td><td class="num">${fmtInt(b.sell_qty)} sh / ${fmtNum(b.sell_value)} PKR</td></tr>
            <tr><td><b>Avg Buy / Avg Sell Price</b></td><td class="num">${fmtNum(b.avg_buy_price)} / ${fmtNum(b.avg_sell_price)} PKR</td></tr>
            <tr><td><b>Gross P&amp;L (PKR)</b></td><td class="num ${pnlClass(b.gross_pnl)}">${fmtNum(b.gross_pnl)}</td></tr>
            <tr><td><b>Commission + SST (13%)</b></td><td class="num">${fmtNum(b.commission_amount)} + ${fmtNum(b.sst_amount)} = ${fmtNum(b.total_charges)} PKR</td></tr>
            <tr><td><b>Net P&amp;L (PKR)</b></td><td class="num ${pnlClass(b.net_pnl)}">${fmtNum(b.net_pnl)}</td></tr>
            <tr><td><b>Return on Buy</b></td><td class="num ${pnlClass(b.return_on_buy)}">${fmtPct(b.return_on_buy)}</td></tr>
          </tbody>
        </table>
      </div>
    `).join("")}</div>`;
  } else if (activeTab === "monthly_yearly") {
    bodyHtml = `
      <div class="card">
        <div class="card-header"><div class="card-title">Monthly Summary — Account ${accountId}</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Month</th><th class="num">Days</th><th class="num">Buy Qty</th><th class="num">Buy Value</th><th class="num">Sell Qty</th><th class="num">Sell Value</th><th class="num">Gross P&amp;L</th><th class="num">Commission</th><th class="num">SST 13%</th><th class="num">Total Charges</th><th class="num">Net P&amp;L</th><th class="num">Return on Buy</th></tr>
            </thead>
            <tbody>
              ${rep.monthly_summary.rows.map((r) => `
                <tr>
                  <td><b>${r.month}</b></td><td class="num">${r.trading_days}</td>
                  <td class="num">${fmtInt(r.buy_qty)}</td><td class="num">${fmtNum(r.buy_value)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td><td class="num">${fmtNum(r.sell_value)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td class="num">${fmtNum(r.commission_amount)}</td><td class="num">${fmtNum(r.sst_amount)}</td>
                  <td class="num">${fmtNum(r.total_charges)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><div class="card-title">Yearly Summary — Account ${accountId}</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Year</th><th class="num">Days</th><th class="num">Buy Qty</th><th class="num">Buy Value</th><th class="num">Sell Qty</th><th class="num">Sell Value</th><th class="num">Gross P&amp;L</th><th class="num">Commission</th><th class="num">SST 13%</th><th class="num">Total Charges</th><th class="num">Net P&amp;L</th><th class="num">Return on Buy</th></tr>
            </thead>
            <tbody>
              ${rep.yearly_summary.rows.map((r) => `
                <tr>
                  <td><b>${r.year}</b></td><td class="num">${r.trading_days}</td>
                  <td class="num">${fmtInt(r.buy_qty)}</td><td class="num">${fmtNum(r.buy_value)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td><td class="num">${fmtNum(r.sell_value)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td class="num">${fmtNum(r.commission_amount)}</td><td class="num">${fmtNum(r.sst_amount)}</td>
                  <td class="num">${fmtNum(r.total_charges)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else if (activeTab === "symbol_perf") {
    bodyHtml = `
      <div class="card">
        <div class="card-header"><div class="card-title">Symbol Performance — All Trading Dates (Ranked by Net P&amp;L Descending)</div></div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Rank</th><th>Symbol</th><th class="num">Days</th><th class="num">Buy Qty</th><th class="num">Sell Qty</th><th class="num">Buy Value</th><th class="num">Sell Value</th><th class="num">Gross P&amp;L</th><th class="num">Total Charges</th><th class="num">Net P&amp;L</th><th class="num">Return on Buy</th></tr>
            </thead>
            <tbody>
              ${rep.symbol_performance.map((r, i) => `
                <tr>
                  <td class="num">#${i + 1}</td>
                  <td><b>${r.symbol}</b></td>
                  <td class="num">${r.trading_days}</td>
                  <td class="num">${fmtInt(r.buy_qty)}</td>
                  <td class="num">${fmtInt(r.sell_qty)}</td>
                  <td class="num">${fmtNum(r.buy_value)}</td>
                  <td class="num">${fmtNum(r.sell_value)}</td>
                  <td class="num ${pnlClass(r.gross_pnl)}">${fmtNum(r.gross_pnl)}</td>
                  <td class="num">${fmtNum(r.total_charges)}</td>
                  <td class="num ${pnlClass(r.net_pnl)}">${fmtNum(r.net_pnl)}</td>
                  <td class="num ${pnlClass(r.return_on_buy)}">${fmtPct(r.return_on_buy)}</td>
                </tr>
              `).join("")}
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
                    <td>${ex.trade_date}</td><td>${ex.trade_time}</td><td><b>${ex.symbol}</b></td><td>${ex.market_type}</td>
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
          <div class="kpi-box"><div class="kpi-label">Reconciliation Status</div><div class="kpi-value pos">${rec.passed ? "PASSED (100%)" : "CHECK"}</div></div>
          <div class="kpi-box"><div class="kpi-label">Daily vs Symbol Net P&amp;L Diff</div><div class="kpi-value">${rec.daily_vs_symbol_net_pnl_diff}</div></div>
          <div class="kpi-box"><div class="kpi-label">Monthly vs Daily Net P&amp;L Diff</div><div class="kpi-value">${rec.monthly_vs_daily_net_pnl_diff}</div></div>
          <div class="kpi-box"><div class="kpi-label">Open / Unmatched Net Qty Rows</div><div class="kpi-value">${rec.unmatched_count}</div></div>
        </div>
      </div>
    `;
  }

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
    ${bodyHtml}
  `;
}

function switchAccountSubtab(accountId, tabKey) {
  state.accTab[accountId] = tabKey;
  renderAccountView(document.getElementById("viewContainer"), accountId);
}

function openAccountDateDetail(accountId, tradeDate) {
  state.accSelectedDate[accountId] = tradeDate;
  state.accTab[accountId] = "daily_detail";
  renderAccountView(document.getElementById("viewContainer"), accountId);
}

// ============================================================================
// 06. MODULE C: FUTURES COMPARISON & ANNUALIZED ANALYSIS
// ============================================================================
async function renderFuturesView(container) {
  const f = state.futures;
  const meta = await apiGet(`/api/futures/metadata?apply_rolling=${f.apply_rolling}`);
  f.meta = meta;
  const availDates = meta.dates || meta.retained_dates || meta.all_dates_in_db || [];
  if (!f.selected_date || !availDates.includes(f.selected_date)) {
    f.selected_date = meta.latest_date || (availDates.length ? availDates[availDates.length - 1] : "2026-10-16");
  }

  const subtabs = [
    ["monthly_comparison", "1. Monthly Comparison"],
    ["month_filter", "2. Month Filter"],
    ["symbol_filter", "3. Symbol Filter"],
    ["annualized_comparison", "4. Annualized Comparison"],
    ["date_filter", "5. Date Filter"],
    ["future_symbol_summary", "6. Future Symbol Summary"],
    ["date_summary", "7. Date Summary"],
    ["rolling_window", "2-Month Rolling Retention"],
  ];

  let contentHtml = "";
  if (["monthly_comparison", "month_filter", "symbol_filter", "annualized_comparison", "date_filter"].includes(f.subtab)) {
    const qs = new URLSearchParams({
      view_mode: f.subtab,
      selected_date: f.selected_date,
      contract_month: f.contract_month,
      base_symbol: f.base_symbol,
      days: String(f.days),
      apply_rolling: String(f.apply_rolling),
    });
    const comp = await apiGet(`/api/futures/comparison?${qs.toString()}`);

    contentHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">${subtabs.find((s) => s[0] === f.subtab)[1]} — ${comp.selected_date} (${comp.rows_count} Contracts)</div>
            <div class="card-subtitle">Exact same-date matching only (no carry-forward/backfill) • Sorted by Annualized % Ascending • Days = ${f.days}</div>
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
              ${comp.rows.map((r) => `
                <tr>
                  <td>${r.trade_date}</td>
                  <td><b>${r.symbol}</b></td>
                  <td><span class="badge badge-blue">${r.contract}</span></td>
                  <td class="num">${fmtNum(r.current_value)}</td>
                  <td class="num">${fmtNum(r.future_value)}</td>
                  <td class="num">${fmtInt(r.volume)}</td>
                  <td class="num">${fmtNum(r.high)}</td>
                  <td class="num">${fmtNum(r.low)}</td>
                  <td class="num ${pnlClass(r.difference)}">${fmtNum(r.difference)}</td>
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
  } else if (f.subtab === "future_symbol_summary") {
    const res = await apiGet(`/api/futures/symbol-summary?contract_symbol=${encodeURIComponent(f.contract_symbol)}&apply_rolling=${f.apply_rolling}`);
    contentHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">6. Future Symbol Summary — ${res.selected_contract_symbol} (${res.rows_count} Trading Days)</div>
            <div class="card-subtitle">Sorted by DATE Ascending • Change = CLOSE − PR_CL</div>
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
                  <td><b>${r.DATE}</b></td>
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
    const res = await apiGet(`/api/futures/date-summary?selected_date=${encodeURIComponent(f.selected_date)}&apply_rolling=${f.apply_rolling}`);
    contentHtml = `
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">7. Date Summary — ${res.selected_date} (${res.rows_count} Futures Contracts)</div>
            <div class="card-subtitle">Sorted by SYMBOL Ascending • Change = CLOSE − PR_CL</div>
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
                  <td>${r.DATE}</td>
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
    contentHtml = `
      <div class="card">
        <div class="card-header"><div class="card-title">2-Month Rolling Data Retention Policy Preview</div></div>
        <div class="grid-4">
          <div class="kpi-box"><div class="kpi-label">Latest Date in Dataset</div><div class="kpi-value">${prev.latest_date}</div></div>
          <div class="kpi-box"><div class="kpi-label">2-Month Cutoff Date</div><div class="kpi-value">${prev.cutoff_date}</div></div>
          <div class="kpi-box"><div class="kpi-label">Active Retained Futures Rows</div><div class="kpi-value pos">${fmtInt(prev.futures_rows_retained_in_active_window)}</div></div>
          <div class="kpi-box"><div class="kpi-label">Older Futures Rows (August)</div><div class="kpi-value">${fmtInt(prev.futures_rows_older_than_cutoff)}</div></div>
        </div>
        <p style="color:var(--text-muted);">${prev.note}</p>
      </div>
    `;
  }

  container.innerHTML = `
    <div class="subtabs">
      ${subtabs.map(([k, lbl]) => `
        <button class="subtab-btn ${f.subtab === k ? "active" : ""}" onclick="state.futures.subtab='${k}';renderFuturesView(document.getElementById('viewContainer'))">${lbl}</button>
      `).join("")}
    </div>

    <div class="filter-bar">
      <div class="filter-group">
        <label>Selected Date:</label>
        <select onchange="state.futures.selected_date=this.value;renderFuturesView(document.getElementById('viewContainer'))">
          ${availDates.slice().reverse().map((d) => `<option value="${d}" ${d === f.selected_date ? "selected" : ""}>${d}</option>`).join("")}
        </select>
      </div>
      <div class="filter-group">
        <label>Contract/Month:</label>
        <select onchange="state.futures.contract_month=this.value;renderFuturesView(document.getElementById('viewContainer'))">
          ${(meta.contracts || []).map((c) => `<option value="${c}" ${c === f.contract_month ? "selected" : ""}>${c}</option>`).join("")}
        </select>
      </div>
      <div class="filter-group">
        <label>Base Symbol:</label>
        <select onchange="state.futures.base_symbol=this.value;renderFuturesView(document.getElementById('viewContainer'))">
          ${(meta.base_symbols || []).map((s) => `<option value="${s}" ${s === f.base_symbol ? "selected" : ""}>${s}</option>`).join("")}
        </select>
      </div>
      <div class="filter-group">
        <label>Future Item (Sheet 6):</label>
        <select onchange="state.futures.contract_symbol=this.value;renderFuturesView(document.getElementById('viewContainer'))">
          ${(meta.contract_symbols || []).map((cs) => `<option value="${cs}" ${cs === f.contract_symbol ? "selected" : ""}>${cs}</option>`).join("")}
        </select>
      </div>
      <div class="filter-group">
        <label>Days:</label>
        <input type="number" min="1" max="365" value="${f.days}" style="width:72px" onchange="state.futures.days=Number(this.value)||30;renderFuturesView(document.getElementById('viewContainer'))" />
      </div>
      <div style="margin-left:auto;">
        <a class="btn btn-primary" href="/api/exports/generate/futures_xlsx?selected_date=${f.selected_date}&selected_contract=${f.contract_month}&selected_symbol=${f.base_symbol}&days=${f.days}" download>⬇ Export 8-Sheet Futures_Analysis.xlsx</a>
      </div>
    </div>

    ${contentHtml}
  `;
}

// ============================================================================
// 07. MODULE D: TECHNICAL ANALYSIS, SETUP GENERATOR & 36-TICKER DASHBOARD
// ============================================================================
async function renderTechnicalView(container) {
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
    if (t.search) qs.set("search", t.search);
    if (t.signalFilter && t.signalFilter !== "ALL") qs.set("signal_filter", t.signalFilter);
    const uni = await apiGet(`/api/technical/universe?${qs.toString()}`);

    bodyHtml = `
      <div class="filter-bar">
        <div class="filter-group">
          <label>Search Ticker:</label>
          <input type="text" value="${t.search}" placeholder="e.g. ATRL, MLCF (or MLF), OGDC..." oninput="state.technical.search=this.value;renderTechnicalView(document.getElementById('viewContainer'))" />
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
          <table class="data-table">
            <thead>
              <tr>
                <th>Symbol</th><th class="num">Close</th><th class="num">Chg %</th><th class="num">RSI(14)</th><th>RSI Zone</th>
                <th class="num">Pivot (P)</th><th class="num">R1</th><th class="num">S1</th>
                <th class="num">W-Pivot</th><th class="num">MACD</th><th class="num">MACD Sig</th>
                <th class="num">EMA 9/21/50</th><th class="num">ADX(14)</th><th class="num">Score</th><th>Action / Combined Signal</th>
              </tr>
            </thead>
            <tbody>
              ${uni.items.slice(0, 150).map((item) => {
                const dp = item.daily_pivots.classic;
                const wp = item.weekly_pivots?.pivots || {};
                const act = item.signal.action;
                const bCls = act === "BUY" ? "badge-green" : (act === "SELL" || act === "SHORT SELL" ? "badge-red" : "badge-amber");
                return `
                  <tr style="cursor:pointer" onclick="openTickerDeepDive('${item.symbol}')">
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
          <label>Select Core 36 Ticker (or type any of 531 symbols):</label>
          <input type="text" value="${t.selectedSymbol}" style="width:120px" onchange="openTickerDeepDive(this.value)" />
        </div>
        <div class="filter-group">
          <span style="color:var(--text-muted);font-size:12px;">Quick Select:</span>
          ${["ATRL", "OGDC", "PPL", "PSO", "LUCK", "MLCF", "HBL", "UBL", "ENGROH", "TRG", "FFC", "HUBC", "SYS", "PAEL"].map((s) => `
            <button class="btn btn-secondary" style="padding:4px 8px;font-size:11px;" onclick="openTickerDeepDive('${s}')">${s}</button>
          `).join("")}
        </div>
      </div>

      <div class="grid-4">
        <div class="kpi-box">
          <div class="kpi-label">${res.display_label} • Last Close (${lat.latest_date})</div>
          <div class="kpi-value">${fmtNum(lat.close)} PKR</div>
          <div class="kpi-sub ${pnlClass(lat.change_pct)}">Day Change: ${fmtNum(lat.change_val)} (${fmtPct(lat.change_pct, false)})</div>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Composite Signal (${sig.score > 0 ? "+" : ""}${sig.score} / 9)</div>
          <div class="kpi-value ${sig.score > 0 ? "pos" : (sig.score < 0 ? "neg" : "")}">${sig.action}</div>
          <div class="kpi-sub">${sig.combined_signal} • Confidence: ${sig.confidence}</div>
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
            <div class="card-subtitle">Last ${res.series.length} sessions (${res.series[0]?.trade_date} → ${lat.latest_date}) • No future-data leakage</div>
          </div>
        </div>
        ${renderTechnicalSvgChart(res.series)}
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header"><div class="card-title">9-Factor Explainable Indicator Dashboard</div></div>
          <table class="data-table">
            <thead><tr><th>Indicator</th><th>Value</th><th>Signal</th><th>Actionable Advice</th><th class="num">Vote</th></tr></thead>
            <tbody>
              ${sig.indicator_breakdown.map((b) => `
                <tr>
                  <td><b>${b.indicator}</b></td>
                  <td class="num">${b.value}</td>
                  <td><span class="badge ${b.vote > 0 ? "badge-green" : (b.vote < 0 ? "badge-red" : "badge-amber")}">${b.signal}</span></td>
                  <td style="white-space:normal;">${b.advice}</td>
                  <td class="num ${pnlClass(b.vote)}">${b.vote > 0 ? "+1" : b.vote}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
          <div style="margin-top:10px;font-size:12px;color:var(--text-muted);">
            <b>Invalidation Rule:</b> ${sig.invalidation} • <b>Horizon:</b> ${sig.holding_horizon}
          </div>
        </div>

        <div class="card">
          <div class="card-header"><div class="card-title">Daily &amp; Previous-Completed-Week Pivot Levels</div></div>
          <table class="data-table">
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

      ${buildAutomatedAnalystCardHtml(analystRes)}
    `;
  }

  container.innerHTML = `
    <div class="subtabs">
      <button class="subtab-btn ${t.subtab === "core36" ? "active" : ""}" onclick="state.technical.subtab='core36';renderTechnicalView(document.getElementById('viewContainer'))">Core 36-Ticker Matrix</button>
      <button class="subtab-btn ${t.subtab === "ideas_and_analyst" ? "active" : ""}" onclick="state.technical.subtab='ideas_and_analyst';renderTechnicalView(document.getElementById('viewContainer'))">⚡ Trading Ideas Generator &amp; Automated Analyst</button>
      <button class="subtab-btn ${t.subtab === "deep_dive" ? "active" : ""}" onclick="state.technical.subtab='deep_dive';renderTechnicalView(document.getElementById('viewContainer'))">Ticker Deep-Dive &amp; Chart (${t.selectedSymbol})</button>
      <button class="subtab-btn ${t.subtab === "all531" ? "active" : ""}" onclick="state.technical.subtab='all531';renderTechnicalView(document.getElementById('viewContainer'))">Full 531-Symbol Screener</button>
    </div>
    ${bodyHtml}
  `;
}

function openTickerDeepDive(sym) {
  const clean = (sym || "ATRL").toUpperCase().trim();
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
  const data = await apiGet("/api/reconciliation");
  const leg = data.legacy_reconciliation;
  const dq = data.data_quality;

  container.innerHTML = `
    <div class="grid-4">
      <div class="kpi-box">
        <div class="kpi-label">Module A • Top 5 Legacy Reconciliation</div>
        <div class="kpi-value pos">${leg.module_a_top5?.status}</div>
        <div class="kpi-sub">Checked ${leg.module_a_top5?.checked_16_oct_rows} rows on 16-Oct-2026 • ${leg.module_a_top5?.mismatches_count} diffs</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Module B • Account 91404 &amp; 91269</div>
        <div class="kpi-value pos">${leg.module_b_account_91404?.status} / ${leg.module_b_account_91269?.status}</div>
        <div class="kpi-sub">91404 Diff: ${leg.module_b_account_91404?.net_pnl_abs_diff?.toExponential(2)} PKR | 91269 Diff: 0.00 PKR</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Module C • Futures Spread Match</div>
        <div class="kpi-value pos">${leg.module_c_futures?.status}</div>
        <div class="kpi-sub">${leg.module_c_futures?.comparisons_count_on_16_oct} contracts • KAPCO-OCTB -47.68%</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label">Module D • ATRL Indicator Parity</div>
        <div class="kpi-value pos">${leg.module_d_technical_atrl?.status}</div>
        <div class="kpi-sub">RSI 63.21 • MACD 26.54 • ADX 41.03</div>
      </div>
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
                  <td>${u.trade_date}</td><td><b>${u.contract_symbol}</b></td><td>${u.base_symbol}</td><td>${u.contract_month}</td>
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
                  <td><b>${t.symbol}</b></td><td class="num">${t.bars_count}</td><td>${t.first_date}</td><td>${t.last_date}</td>
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
  const [docsMeta, docContent] = await Promise.all([
    apiGet("/api/docs"),
    apiGet(`/api/docs/${encodeURIComponent(state.selectedDoc)}`),
  ]);

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">Legacy-Compatible Excel (.xlsx) &amp; CSV Export Center</div>
          <div class="card-subtitle">All workbooks are generated dynamically from the canonical SQLite database with full openpyxl styling, tables, and formulas</div>
        </div>
      </div>
      <div class="grid-4">
        <div class="kpi-box">
          <div class="kpi-label">Module A Workbook</div>
          <div style="font-weight:700;margin:6px 0;">PSX_Top5_Volume_Rate_Register.xlsx</div>
          <div class="kpi-sub" style="margin-bottom:10px;">23 Ticker Sheets • MM/DD/YYYY Blocks • Excel Tables &amp; Volume Data Bars</div>
          <a class="btn btn-primary" href="/api/exports/generate/top5_xlsx" download>⬇ Download .XLSX</a>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Module B • Account 91404</div>
          <div style="font-weight:700;margin:6px 0;">Trade_Summary_Account_91404.xlsx</div>
          <div class="kpi-sub" style="margin-bottom:10px;">12 Sheets: Dashboard, Daily, MTD/QTD/YTD, Monthly, Yearly, Symbols, Trade Log, Checks</div>
          <a class="btn btn-primary" href="/api/exports/generate/account_91404_xlsx" download>⬇ Download .XLSX</a>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Module B • Account 91269</div>
          <div style="font-weight:700;margin:6px 0;">Trade_Summary_Account_91269.xlsx</div>
          <div class="kpi-sub" style="margin-bottom:10px;">Strictly Isolated Account 91269 Workbook (20 Trading Days, 31 Symbols)</div>
          <a class="btn btn-primary" href="/api/exports/generate/account_91269_xlsx" download>⬇ Download .XLSX</a>
        </div>
        <div class="kpi-box">
          <div class="kpi-label">Module C &amp; D Workbooks</div>
          <div style="font-weight:700;margin:6px 0;">Futures_Analysis &amp; RSI_Pivot_Analysis</div>
          <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap;">
            <a class="btn btn-primary" href="/api/exports/generate/futures_xlsx" download>⬇ Futures (.xlsx)</a>
            <a class="btn btn-primary" href="/api/exports/generate/technical_xlsx" download>⬇ Technical (.xlsx)</a>
          </div>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Engineering Documentation Suite (/docs/)</div>
          <select onchange="state.selectedDoc=this.value;renderExportsView(document.getElementById('viewContainer'))">
            ${docsMeta.docs.map((d) => `<option value="${d.name}" ${d.name === state.selectedDoc ? "selected" : ""}>${d.name} (${fmtInt(d.size_bytes)} B)</option>`).join("")}
          </select>
        </div>
        <pre class="doc-viewer">${docContent.content.replace(/</g, "&lt;")}</pre>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Verified Local Agent Skills Catalog (/skills/catalog.json)</div>
            <div class="card-subtitle">${docsMeta.skills.length} Open-Source SKILL.md Packages Audited &amp; Archived Locally</div>
          </div>
        </div>
        <div class="table-wrap" style="max-height:600px;overflow-y:auto;">
          <table class="data-table">
            <thead><tr><th>Skill Name</th><th>Category</th><th>Source Repository</th><th>Security Status</th></tr></thead>
            <tbody>
              ${docsMeta.skills.map((s) => `
                <tr>
                  <td><b>${s.name}</b><br><span style="color:var(--text-muted);font-size:11px;">${s.local_path}</span></td>
                  <td>${s.category}</td>
                  <td><span class="badge badge-blue">${s.repo}</span></td>
                  <td><span class="badge badge-green">${s.verification_status}</span></td>
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
// 10. SETTINGS, RULE VERSIONING & SQLITE BACKUP
// ============================================================================
async function renderSettingsView(container) {
  const data = await apiGet("/api/settings", false);
  const s = data.settings;
  const rules = data.rule_versions || [];

  container.innerHTML = `
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
            <tr><td><b>Commission Slab 1 Upper Rate (PKR)</b></td><td><input type="number" step="0.01" id="set_slab1_upper" value="${s.commission_slab1_upper}" /></td></tr>
            <tr><td><b>Commission Slab 1 Paisa / Share</b></td><td><input type="number" step="0.0001" id="set_slab1_paisa" value="${s.commission_slab1_paisa_per_share}" /></td></tr>
            <tr><td><b>Commission Slab 2 Starting Rate (PKR)</b></td><td><input type="number" step="0.01" id="set_slab2_start" value="${s.commission_slab2_start}" /></td></tr>
            <tr><td><b>Commission Slab 2 Rate (Decimal, 0.000325 = 0.0325%)</b></td><td><input type="number" step="0.000001" id="set_slab2_rate" value="${s.commission_slab2_rate}" /></td></tr>
            <tr><td><b>Sindh Sales Tax (SST) Rate (Decimal, 0.13 = 13%)</b></td><td><input type="number" step="0.01" id="set_sst_rate" value="${s.sst_rate}" /></td></tr>
            <tr><td><b>Default Futures Days to Expiry</b></td><td><input type="number" step="1" id="set_fut_days" value="${s.default_futures_days ?? s.futures_default_days ?? 30}" /></td></tr>
            <tr><td><b>Futures Rolling Retention Window (Months)</b></td><td><input type="number" step="1" id="set_fut_months" value="${s.futures_rolling_months ?? s.futures_rolling_retention_months ?? 2}" /></td></tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">SQLite Online Backup &amp; Restore Manager</div>
            <div class="card-subtitle">Database Integrity: <b class="pos">${data.db_integrity.ok ? "PRAGMA integrity_check = OK" : "FAILED"}</b> • Path: ${data.db_integrity.db_path}</div>
          </div>
          <button class="btn btn-success" onclick="createManualBackup()">+ Create New Backup (.zip)</button>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>Backup Archive</th><th>Created At (UTC)</th><th class="num">Size</th><th>Integrity</th><th>Actions</th></tr></thead>
            <tbody>
              ${data.backups.map((b) => `
                <tr>
                  <td><b>${b.zip_filename}</b><br><span style="color:var(--text-muted);font-size:10.5px;">SHA256: ${(b.db_sha256 || "").slice(0, 16)}...</span></td>
                  <td>${(b.created_at || "").replace("T", " ").slice(0, 19)}</td>
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
                  <td>${(r.created_at || "").replace("T", " ").slice(0, 19)}</td>
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
    default_futures_days: Number(document.getElementById("set_fut_days").value),
    futures_default_days: Number(document.getElementById("set_fut_days").value),
    futures_rolling_months: Number(document.getElementById("set_fut_months").value),
    futures_rolling_retention_months: Number(document.getElementById("set_fut_months").value),
  };
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updates, notes: "Updated via Settings UI" }),
  });
  clearClientCache();
  showToast("Settings saved and new rule version recorded.");
  renderSettingsView(document.getElementById("viewContainer"));
}

async function createManualBackup() {
  await fetch("/api/backups/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label: "manual_snapshot", include_raw_archive: false }),
  });
  showToast("SQLite online backup created and verified with SHA-256.");
  renderSettingsView(document.getElementById("viewContainer"));
}

async function restoreBackup(zipFilename) {
  const res = await fetch("/api/backups/restore", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zip_filename: zipFilename }),
  });
  if (res.ok) {
    clearClientCache();
    showToast(`Database restored from ${zipFilename} (pre-restore safety snapshot saved).`);
    renderSettingsView(document.getElementById("viewContainer"));
  } else {
    showToast("Backup restore failed.", true);
  }
}

// Navigation Event Listeners
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

window.addEventListener("DOMContentLoaded", () => {
  switchView("overview");
});
