import csv
import io
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import openpyxl

VALID_MONTH_PREFIXES = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"
)


def split_futures_contract_symbol(raw_symbol: str) -> Tuple[str, str]:
    """
    Dynamically split a PSX futures symbol into (base_symbol, contract_month).
    Supports 'OGDC-AUG', 'ATRL-AUGB', 'OGDC AUG', 'ATRL SEPB', etc.
    Never merges AUG with AUGB or SEP with SEPB.
    """
    s = raw_symbol.strip().upper()
    if "-" in s:
        parts = s.rsplit("-", 1)
        return parts[0].strip(), parts[1].strip()
    if " " in s:
        parts = s.rsplit(None, 1)
        return parts[0].strip(), parts[1].strip()
    # Regex fallback if attached
    m = re.match(r"^([A-Z0-9]+?)[-_ ]?((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z0-9]*)$", s)
    if m:
        return m.group(1), m.group(2)
    return s, "UNKNOWN"


_NUMERIC_DATE_RE = re.compile(r"^(\d{1,2})([/-])(\d{1,2})(?:\2|[/-])(\d{4})(?:\s.*)?$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T\s].*)?$")


def _try_order(y: int, m: int, d: int) -> Optional[str]:
    try:
        return date(y, m, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_any_date(val: Any, prefer: Optional[str] = None) -> Optional[str]:
    """Parse a raw date cell into an ISO 'YYYY-MM-DD' string with PINNED semantics.

    Rules (deterministic, no guessing):
    - real datetime/date objects pass through unchanged;
    - ISO 'YYYY-MM-DD[...]' passes through unchanged;
    - purely numeric 'A/B/YYYY' texts are resolved by separator *policy*:
        * slash-separated  -> 'M/D/YYYY' (US format; Google Sheets US-locale CSV
          exports and every PSX ticker/daily txt feed observed);
        * dash-separated   -> 'DD-MM-YYYY' (the workbook/Google-Sheets DMY
          convention used throughout the Drive mirror);
      `prefer='MDY'` or `prefer='DMY'` overrides the separator policy (used by
      the file-level orientation detector for fully-ambiguous columns);
    - on day/month ambiguity the FIRST interpretation is tried and the other is
      used only if the first is impossible (month > 12);
    - 'dd-MMM-yyyy' ('12-Oct-2026') and 'yyyy/MM/dd' are also accepted.
    """
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    m_iso = _ISO_DATE_RE.match(s)
    if m_iso:
        return _try_order(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))

    m_num = _NUMERIC_DATE_RE.match(s)
    if m_num:
        a = int(m_num.group(1))
        sep = m_num.group(2)
        b = int(m_num.group(3))
        y = int(m_num.group(4))
        if prefer == "DMY":
            orders = [(y, b, a), (y, a, b)]
        elif prefer == "MDY":
            orders = [(y, a, b), (y, b, a)]
        elif sep == "/":
            orders = [(y, a, b), (y, b, a)]  # M/D/YYYY first
        else:
            orders = [(y, b, a), (y, a, b)]  # DD-MM-YYYY first
        for oy, om, od in orders:
            out = _try_order(oy, om, od)
            if out:
                return out
        return None

    for fmt in ("%d-%b-%Y", "%d %b %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:11] if "%b" in fmt else s[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def detect_date_orientation(raw_values: List[Any]) -> Dict[str, Any]:
    """File-level orientation detection for an entire date column.

    Inspects every numeric-looking date text and decides MDY vs DMY using the
    *impossible month* test: an interpretation that would need a month > 12 for
    some rows cannot be the producer's convention. Returns {"prefer":..., ...}.
    Fully ambiguous columns fall back to the separator policy (slash=MDY,
    dash=DMY), which matches every feed observed for this workbook family.
    """
    numeric = []
    non_numeric = 0
    for v in raw_values:
        if v is None:
            continue
        if isinstance(v, (datetime, date)):
            non_numeric += 1
            continue
        m = _NUMERIC_DATE_RE.match(str(v).strip())
        if m:
            numeric.append((int(m.group(1)), m.group(2), int(m.group(3))))
        else:
            non_numeric += 1
    total = len(numeric)
    if total == 0:
        return {"prefer": None, "numeric": 0, "non_numeric": non_numeric,
                "mdy_rejects": 0, "dmy_rejects": 0, "ambiguous": 0, "decision": "n/a"}

    mdy_rejects = sum(1 for a, _s, _b in numeric if a > 12)  # MDY reads month from first num
    dmy_rejects = sum(1 for _a, _s, b in numeric if b > 12)  # DMY reads month from second num
    ambiguous = sum(1 for a, _s, b in numeric if a <= 12 and b <= 12)

    if mdy_rejects == 0 and dmy_rejects > 0:
        prefer, decision = "MDY", "mdy-forced-by-data"
    elif dmy_rejects == 0 and mdy_rejects > 0:
        prefer, decision = "DMY", "dmy-forced-by-data"
    else:
        prefer = None
        decision = "separator-policy-default"
    return {"prefer": prefer, "numeric": total, "non_numeric": non_numeric,
            "mdy_rejects": mdy_rejects, "dmy_rejects": dmy_rejects,
            "ambiguous": ambiguous, "decision": decision}


def _safe_float(v: Any, default: Optional[float] = 0.0) -> Optional[float]:
    if v is None or v == "":
        return default
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(round(float(str(v).replace(",", "").strip())))
    except Exception:
        return default


def parse_ohlcv_file(file_path: Path, mode: str = "CASH", original_filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse daily OHLCV records from .xlsx or .csv for:
    - mode='CASH': 2026.xlsx, 2026_YEAR.xlsx, 2026_compare.csv
    - mode='FUTURES': 2026F.xlsx, 2026F.csv
    - mode='INDEX': INDEX.xlsx
    """
    fname = original_filename or file_path.name
    lower = fname.lower()
    raw_rows: List[Tuple[Any, ...]] = []

    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        for r in ws.iter_rows(values_only=True):
            if r and any(x is not None for x in r):
                raw_rows.append(tuple(r))
        wb.close()
    else:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        for r in reader:
            if r and any(c.strip() for c in r):
                raw_rows.append(tuple(r))

    if not raw_rows:
        return {"filename": fname, "mode": mode, "rows_read": 0, "records": [], "issues": []}

    # Find header row
    hdr_idx = 0
    col_map: Dict[str, int] = {}
    for idx in range(min(5, len(raw_rows))):
        candidates = [str(c or "").strip().upper() for c in raw_rows[idx]]
        if "DATE" in candidates and ("CLOSE" in candidates or "SYMBOL" in candidates):
            hdr_idx = idx
            col_map = {name: i for i, name in enumerate(candidates) if name}
            break

    def col_val(row: Tuple[Any, ...], *names: str) -> Any:
        for n in names:
            if n in col_map and col_map[n] < len(row):
                return row[col_map[n]]
        return None

    records: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    rows_read = 0
    dates_seen = set()
    symbols_seen = set()

    # --- File-level date-orientation detection (anti day/month swap) ---------
    # Never let a single ambiguous parse guess the convention: inspect the
    # WHOLE column first, then pin every row to the winning convention.
    date_candidates: List[Any] = []
    for row in raw_rows[hdr_idx + 1:]:
        v = col_val(row, "DATE") if col_map else (row[0] if len(row) > 0 else None)
        if v is not None and str(v).strip() != "":
            date_candidates.append(v)
    orient = detect_date_orientation(date_candidates)
    if orient["numeric"]:
        issues.append({
            "severity": "INFO",
            "issue_type": "DATE_FORMAT_PINNED",
            "row_number": None,
            "message": (
                f"Date format pinned for {fname}: prefer={orient['prefer'] or 'separator-policy'} "
                f"({orient['decision']}); numeric dates={orient['numeric']}, "
                f"ambiguous day<=12 rows={orient['ambiguous']}, "
                f"mdy-rejects={orient['mdy_rejects']}, dmy-rejects={orient['dmy_rejects']}."
            ),
        })
    prefer = orient["prefer"]

    for r_idx, row in enumerate(raw_rows[hdr_idx + 1:], start=hdr_idx + 2):
        d_raw = col_val(row, "DATE") if col_map else (row[0] if len(row) > 0 else None)
        if d_raw is None or str(d_raw).strip() == "":
            continue
        rows_read += 1
        trade_date = parse_any_date(d_raw, prefer=prefer)
        if not trade_date:
            issues.append({
                "severity": "WARNING",
                "issue_type": "INVALID_DATE",
                "row_number": r_idx,
                "message": f"Invalid date '{d_raw}' on row {r_idx} in {fname}.",
            })
            continue

        if mode == "INDEX":
            pr_cl = _safe_float(col_val(row, "PR-CLOSE", "PR_CL", "PR_CLOSE"))
            open_p = _safe_float(col_val(row, "OPEN"))
            high_p = _safe_float(col_val(row, "HIGH"))
            low_p = _safe_float(col_val(row, "LOW", "LOW "))
            close_p = _safe_float(col_val(row, "CLOSE"))
            if close_p is None:
                continue
            dates_seen.add(trade_date)
            records.append({
                "trade_date": trade_date,
                "pr_close": pr_cl,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "source_filename": fname,
            })
            continue

        sym_raw = col_val(row, "SYMBOL", "ITEM", "SCRIP") if col_map else (row[1] if len(row) > 1 else None)
        if not sym_raw or not str(sym_raw).strip():
            continue
        sym_clean = str(sym_raw).strip().upper()
        vol = _safe_int(col_val(row, "VOLUME", "VOL"))
        pr_cl = _safe_float(col_val(row, "PR-CLOSE", "PR_CL", "PR_CLOSE", "PREV_CLOSE"))
        high_p = _safe_float(col_val(row, "HIGH"))
        low_p = _safe_float(col_val(row, "LOW", "LOW "))
        open_p = _safe_float(col_val(row, "OPEN"))
        close_p = _safe_float(col_val(row, "CLOSE", "CURRENT", "FUTURE"))
        avg_p = _safe_float(col_val(row, "AVG", "AVERAGE"))

        if close_p is None:
            issues.append({
                "severity": "WARNING",
                "issue_type": "MISSING_CLOSE",
                "symbol": sym_clean,
                "trade_date": trade_date,
                "row_number": r_idx,
                "message": f"Missing CLOSE price for {sym_clean} on {trade_date}.",
            })
            continue

        dates_seen.add(trade_date)
        symbols_seen.add(sym_clean)

        if mode == "FUTURES":
            base_sym, contract_month = split_futures_contract_symbol(sym_clean)
            canonical_contract_sym = f"{base_sym}-{contract_month}" if contract_month != "UNKNOWN" else sym_clean
            change_val = (close_p - pr_cl) if (close_p is not None and pr_cl is not None) else None
            records.append({
                "trade_date": trade_date,
                "contract_symbol": canonical_contract_sym,
                "base_symbol": base_sym,
                "contract_month": contract_month,
                "volume": vol,
                "pr_close": pr_cl,
                "high": high_p,
                "low": low_p,
                "open": open_p,
                "close": close_p,
                "avg_price": avg_p,
                "change_val": change_val,
                "source_filename": fname,
            })
        else:
            records.append({
                "trade_date": trade_date,
                "symbol": sym_clean,
                "volume": vol,
                "pr_close": pr_cl,
                "high": high_p,
                "low": low_p,
                "open": open_p,
                "close": close_p,
                "avg_price": avg_p,
                "source_filename": fname,
            })

    return {
        "filename": fname,
        "mode": mode,
        "rows_read": rows_read,
        "records": records,
        "dates": sorted(dates_seen),
        "symbols_count": len(symbols_seen),
        "issues": issues,
    }
