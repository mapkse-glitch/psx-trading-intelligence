# Financial Formulas, Commission Rules & Technical Signal Specifications

This document provides the complete mathematical specification for all calculations across Modules A, B, C, and D.

---

## 1. Module A — Daily Top 5 Volume & Rate Register

Given a daily ticker price summary file containing rows $(r_i, t_i, v_i, \text{val}_i)$ where:
- $r_i$ = Rate (PKR)
- $t_i$ = Trades count
- $v_i$ = Volume (shares)

1. **Validation**: Verify $r_i > 0$, $v_i \ge 0$, $t_i \ge 0$.
2. **Sorting**: Sort all valid rows for `(trade_date, ticker)` by:
   $$v_i \text{ DESC}, \quad t_i \text{ DESC}, \quad r_i \text{ DESC}$$
3. **Selection**: Select up to the first 5 rows ($k \in \{1, \dots, \min(5, N)\}$). If $N < 5$, retain only the $N$ valid rows without fabricating dummy rows.
4. **Tie Detection**: If any adjacent rows around the top-5 boundary share identical $v_i$, log a `VOLUME_TIE` warning in `import_issues`.

---

## 2. Module B — Multi-Account Trading, Commission, SST & P&L

### 2.1 Transaction Classification
- `Buy` $\rightarrow$ `BUY`
- `Sell` $\rightarrow$ `SELL`
- `Short Sell` $\rightarrow$ `SELL` (for all buy/sell flow summaries; original classification preserved in `raw_side`).

### 2.2 Sell-Side Commission Slabs (Per Execution)
Commission applies strictly to **SELL** executions (`Sell` and `Short Sell`). For each sell execution $j$ with quantity $q_j$, sell price $p_j$, and sell value $V_j = q_j \times p_j$:
- **Slab 1 ($0 \le p_j < 54.00\text{ PKR}$)**:
  $$\text{Commission}_j = q_j \times \frac{0.0175}{100}\text{ PKR} = q_j \times 0.000175\text{ PKR}$$
  *(0.0175 paisa per share, where 100 paisa = 1 PKR).*
- **Slab 2 ($p_j \ge 54.00\text{ PKR}$)**:
  $$\text{Commission}_j = V_j \times 0.000325\text{ PKR}$$
  *(0.0325% of sell value).*

For mixed-rate executions within the same symbol and date, commission is calculated for each execution $j$ individually and summed:
$$\text{Commission} = \sum_{j \in \text{SELL}} \text{Commission}_j$$

### 2.3 SST & Total Charges
$$\text{SST} = \text{Commission} \times 0.13 \quad (13\%)$$
$$\text{Total Charges} = \text{Commission} + \text{SST} = \text{Commission} \times 1.13$$

### 2.4 Symbol, Daily, MTD, QTD, YTD, Monthly & Yearly Aggregations
For any aggregation scope $S$ (a single symbol on a date, an entire trading day, MTD, QTD, YTD, Month, or Year):
- $\text{Buy Qty}_S = \sum_{i \in \text{BUY}_S} q_i$, $\quad \text{Buy Value}_S = \sum_{i \in \text{BUY}_S} V_i$
- $\text{Sell Qty}_S = \sum_{j \in \text{SELL}_S} q_j$, $\quad \text{Sell Value}_S = \sum_{j \in \text{SELL}_S} V_j$
- $\text{Avg Buy Price}_S = \begin{cases} \frac{\text{Buy Value}_S}{\text{Buy Qty}_S} & \text{if } \text{Buy Qty}_S > 0 \\ \text{N/A} & \text{if } \text{Buy Qty}_S = 0 \end{cases}$
- $\text{Avg Sell Price}_S = \begin{cases} \frac{\text{Sell Value}_S}{\text{Sell Qty}_S} & \text{if } \text{Sell Qty}_S > 0 \\ \text{N/A} & \text{if } \text{Sell Qty}_S = 0 \end{cases}$
- $\text{Price Difference}_S = \begin{cases} \text{Avg Sell Price}_S - \text{Avg Buy Price}_S & \text{if both Buy Qty}_S > 0 \text{ and Sell Qty}_S > 0 \\ \text{N/A} & \text{otherwise} \end{cases}$
- $\text{Net Quantity}_S = \text{Buy Qty}_S - \text{Sell Qty}_S$
- $\text{Gross P\&L}_S = \text{Sell Value}_S - \text{Buy Value}_S$
- $\text{Net P\&L}_S = \text{Gross P\&L}_S - \text{Total Charges}_S$
- $\text{Return on Buy}_S = \begin{cases} \frac{\text{Net P\&L}_S}{\text{Buy Value}_S} & \text{if } \text{Buy Value}_S > 0 \\ \text{N/A} & \text{if } \text{Buy Value}_S = 0 \end{cases}$

---

## 3. Module C — Futures Comparison & Annualized Analysis

For a selected date $d$, base symbol $B$, contract $C$ (e.g. `AUG`, `AUGB`, `SEP`, `SEPB`, `OCT`, `OCTB`), and user-specified $\text{Days} > 0$ (default $30$):
- $\text{Current Value} = \text{CLOSE}_{\text{cash}}(d, B)$ from `equity_ohlcv` on exact date $d$ (or `N/A` if missing on date $d$).
- $\text{Future Value} = \text{CLOSE}_{\text{futures}}(d, B\text{-}C)$ from `futures_ohlcv` on exact date $d$ (or `N/A` if missing on date $d$).
- If either $\text{Current Value}$ or $\text{Future Value}$ is missing, or $\text{Current Value} \le 0$: display `N/A` for all derived fields.
- Otherwise:
  $$\text{Difference} = \text{Future Value} - \text{Current Value}$$
  $$\text{Difference \%} = \left(\frac{\text{Difference}}{\text{Current Value}}\right) \times 100$$
  $$\text{Annualized \%} = \left(\frac{\text{Difference}}{\text{Current Value}}\right) \times \frac{365}{\text{Days}} \times 100$$
- For **Future Symbol Summary** and **Date Summary**:
  $$\text{Change} = \text{CLOSE} - \text{PR\_CL}$$

---

## 4. Module D — Technical Indicators, Pivots & Explainable Signal Engine

### 4.1 Technical Indicators
1. **Wilder's RSI (14)**:
   - $\Delta_t = C_t - C_{t-1}$, $U_t = \max(\Delta_t, 0)$, $D_t = \max(-\Delta_t, 0)$.
   - Initial 14-period average at index $t=14$: $\overline{U}_{14} = \frac{1}{14}\sum_{i=1}^{14} U_i$, $\overline{D}_{14} = \frac{1}{14}\sum_{i=1}^{14} D_i$.
   - Wilder smoothing for $t > 14$: $\overline{U}_t = \frac{13\overline{U}_{t-1} + U_t}{14}$, $\overline{D}_t = \frac{13\overline{D}_{t-1} + D_t}{14}$.
   - $\text{RS}_t = \frac{\overline{U}_t}{\overline{D}_t}$, $\quad \text{RSI}_{14,t} = 100 - \frac{100}{1 + \text{RS}_t}$.
2. **EMA ($N \in \{9, 21, 50, 200\}$)**:
   - Multiplier $\alpha = \frac{2}{N + 1}$, recursive $\text{EMA}_t = \alpha C_t + (1 - \alpha)\text{EMA}_{t-1}$.
   - Data sufficiency flag: `is_sufficient = (bar_count >= N)`. When `strict_indicator_sufficiency = True` and `bar_count < 200`, `EMA 200` displays `N/A (Insufficient History: 196/200)` alongside the recursive warm-up value for reference.
3. **MACD (12, 26, 9)**:
   - $\text{MACD}_t = \text{EMA}_{12,t} - \text{EMA}_{26,t}$
   - $\text{Signal}_t = \text{EMA}_9(\text{MACD}_t)$
   - $\text{Histogram}_t = \text{MACD}_t - \text{Signal}_t$
4. **Bollinger Bands (20, 2)**:
   - $\text{MID}_t = \text{SMA}_{20}(C)_t$, $\quad \sigma_t = \sqrt{\frac{1}{20}\sum_{i=t-19}^{t}(C_i - \text{MID}_t)^2}$
   - $\text{UP}_t = \text{MID}_t + 2\sigma_t$, $\quad \text{LOW}_t = \text{MID}_t - 2\sigma_t$
   - $\%B_t = \frac{C_t - \text{LOW}_t}{\text{UP}_t - \text{LOW}_t}$, $\quad \text{Bandwidth}_t = \frac{\text{UP}_t - \text{LOW}_t}{\text{MID}_t}$
5. **VWAP Proxy (Daily Typical Price & 20-Day Rolling VWAP Proxy)**:
   - Single-Bar Typical Price Proxy: $\text{TP}_t = \frac{H_t + L_t + C_t}{3}$ (matches legacy `ATRL_DATA` column `VWAP`).
   - 20-Day Rolling Volume-Weighted Typical Price: $\text{VWAP}_{20,t} = \frac{\sum_{i=t-19}^{t} \text{TP}_i \cdot V_i}{\sum_{i=t-19}^{t} V_i}$.
6. **ADX (14) with $+DI_{14}$ and $-DI_{14}$**:
   - True Range $\text{TR}_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$.
   - Directional movement $+DM_t$, $-DM_t$ Wilder-smoothed over 14 bars to yield $+DI_{14}$, $-DI_{14}$, $\text{DX}_t = 100 \cdot \frac{|+DI_{14} - -DI_{14}|}{+DI_{14} + -DI_{14}}$, and Wilder-smoothed $\text{ADX}_{14}$.
7. **Daily & Previous-Completed-Week Pivot Points**:
   - **Classic**: $P = \frac{H + L + C}{3}$, $R_1 = 2P - L$, $S_1 = 2P - H$, $R_2 = P + (H - L)$, $S_2 = P - (H - L)$, $R_3 = H + 2(P - L)$, $S_3 = L - 2(H - P)$.
   - **Fibonacci**: $R_1 = P + 0.382(H-L)$, $R_2 = P + 0.618(H-L)$, $R_3 = P + 1.000(H-L)$, $S_1 = P - 0.382(H-L)$, $S_2 = P - 0.618(H-L)$, $S_3 = P - 1.000(H-L)$.
   - **Camarilla**: $R_1..R_4 = C + (H-L)\times \frac{1.1}{12, 6, 4, 2}$, $S_1..S_4 = C - (H-L)\times \frac{1.1}{12, 6, 4, 2}$.
   - **Weekly Pivots**: Computed from the **previous completed trading week's** aggregate High ($\max H$), Low ($\min L$), and final Close ($C_{\text{week}}$).

### 4.2 Explainable 9-Factor Signal Engine & Reference Levels
Each available indicator contributes $\{-1, 0, +1\}$ to a transparent Composite Score (out of active indicators, up to $\pm 9$):
1. **MACD**: $+1$ if $\text{MACD} > \text{Signal}$ and $\text{Hist} > 0$; $-1$ if $\text{MACD} < \text{Signal}$ and $\text{Hist} < 0$; else $0$.
2. **RSI(14)**: $+1$ if $\text{RSI} < 30$ (oversold bounce) or ($50 < \text{RSI} < 70$ in uptrend); $-1$ if $\text{RSI} > 70$ (overbought) or ($30 < \text{RSI} < 45$ in downtrend); else $0$.
3. **Bollinger**: $+1$ if $\%B > 0.55$ (upper half momentum) or $\%B < 0.05$ (mean-reversion support); $-1$ if $\%B < 0.45$ and falling; else $0$.
4. **EMA 9**: $+1$ if $C > \text{EMA}_9$ else $-1$.
5. **EMA 21**: $+1$ if $C > \text{EMA}_{21}$ else $-1$.
6. **EMA 50**: $+1$ if $C > \text{EMA}_{50}$ else $-1$.
7. **EMA 200**: $+1$ if $C > \text{EMA}_{200}$ else $-1$ (or $0$ if insufficient history under strict mode).
8. **Typical-Price / Pivot Bias**: $+1$ if $C \ge P$ else $-1$.
9. **ADX(14) Trend Strength**: $+1$ if $\text{ADX} \ge 20$ and $+DI > -DI$; $-1$ if $\text{ADX} \ge 20$ and $-DI > +DI$; else $0$.

**Action Classification**:
- `Insufficient Data` if `< 26` bars of valid OHLCV exist.
- `Buy` if $\text{Score} \ge +3$ and trend confirmation ($C > \text{EMA}_{21}$).
- `Sell` if $\text{Score} \le -2$ and $C < \text{EMA}_{21}$.
- `Short Sell` (analytical reference only — restricted to futures-eligible PSX securities) if $\text{Score} \le -5$ and $\text{ADX} \ge 20$ with $-DI > +DI$.
- `Hold / Neutral` otherwise.
