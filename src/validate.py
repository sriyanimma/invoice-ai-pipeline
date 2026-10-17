"""Business-rule validation, anomaly detection, and confidence-based routing."""
import statistics
from collections import defaultdict
from datetime import date

from src.config import (AUTO_APPROVE_MIN_CONF, EXPECTED_CURRENCY, KNOWN_VENDORS, OUTLIER_MULTIPLIER,
                        REVIEW_DETAILED_MAX_CONF)

TOL = 0.01
_KNOWN = {v.casefold() for v in KNOWN_VENDORS}


def _issue(code, severity, message):
    return {"code": code, "severity": severity, "message": message}


def vendor_medians(extractions, min_samples=4):
    """Median invoice total per vendor across the whole batch (the 'historical' baseline)."""
    by_vendor = defaultdict(list)
    for e in extractions:
        if e and e.get("vendor_name") and e.get("total_amount") is not None:
            by_vendor[e["vendor_name"].strip().casefold()].append(e["total_amount"])
    return {v: statistics.median(x) for v, x in by_vendor.items() if len(x) >= min_samples}


def validate_invoice(e, medians=None):
    """Return a list of issues. severity 'critical' = block auto-approval, 'warning' = needs a look."""
    medians = medians or {}
    issues = []

    # --- required fields ---
    if not e.get("vendor_name"):
        issues.append(_issue("missing_vendor", "critical", "Vendor name is missing"))
    if not e.get("invoice_number"):
        issues.append(_issue("missing_invoice_number", "critical", "Invoice number is missing"))
    if not e.get("invoice_date"):
        issues.append(_issue("missing_invoice_date", "critical", "Invoice date is missing"))
    if e.get("total_amount") is None:
        issues.append(_issue("missing_total", "critical", "Total amount is missing"))
    if not e.get("due_date"):
        issues.append(_issue("missing_due_date", "warning", "Due date is missing"))

    # --- date logic ---
    if e.get("invoice_date") and e.get("due_date"):
        if date.fromisoformat(e["due_date"]) < date.fromisoformat(e["invoice_date"]):
            issues.append(_issue("due_before_invoice", "critical",
                                 f"Due date {e['due_date']} is before invoice date {e['invoice_date']}"))

    # --- cross-field arithmetic ---
    lines = e.get("line_items") or []
    for n, li in enumerate(lines, 1):
        if abs(li["quantity"] * li["unit_price"] - li["total"]) > TOL + 0.005 * li["total"]:
            issues.append(_issue("line_math_mismatch", "warning",
                                 f"Line {n}: {li['quantity']} x {li['unit_price']} != {li['total']}"))
    if lines and e.get("subtotal") is not None:
        s = round(sum(li["total"] for li in lines), 2)
        if abs(s - e["subtotal"]) > TOL:
            issues.append(_issue("line_sum_mismatch", "critical",
                                 f"Line items sum to {s} but subtotal is {e['subtotal']}"))
    if e.get("subtotal") is not None and e.get("total_amount") is not None:
        expected = round(e["subtotal"] + (e.get("tax") or 0.0), 2)
        if abs(expected - e["total_amount"]) > TOL:
            issues.append(_issue("total_mismatch", "critical",
                                 f"Subtotal + tax = {expected} but total is {e['total_amount']}"))

    # --- business rules ---
    vendor = (e.get("vendor_name") or "").strip().casefold()
    if vendor and vendor not in _KNOWN:
        issues.append(_issue("unknown_vendor", "warning", f"Vendor '{e['vendor_name']}' not in known vendor list"))
    if e.get("currency") and e["currency"] != EXPECTED_CURRENCY:
        issues.append(_issue("unexpected_currency", "warning",
                             f"Currency {e['currency']} (expected {EXPECTED_CURRENCY})"))

    # --- anomaly detection: compare to the vendor's typical invoice ---
    med = medians.get(vendor)
    if med and e.get("total_amount") is not None and e["total_amount"] > OUTLIER_MULTIPLIER * med:
        issues.append(_issue("amount_outlier", "warning",
                             f"Total {e['total_amount']} is over {OUTLIER_MULTIPLIER}x the vendor median ({med:.2f})"))
    return issues


def route(issues, confidence):
    """auto_approved | review_fast | review_detailed"""
    if any(i["severity"] == "critical" for i in issues) or confidence < REVIEW_DETAILED_MAX_CONF:
        return "review_detailed"
    if issues or confidence < AUTO_APPROVE_MIN_CONF:
        return "review_fast"
    return "auto_approved"
