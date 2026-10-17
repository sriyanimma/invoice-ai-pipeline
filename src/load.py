"""Load pipeline results into PostgreSQL (three tables) with SQLAlchemy + pandas."""
from datetime import date

import pandas as pd
from sqlalchemy import Date, create_engine

from src.config import DATABASE_URL


def get_engine(url=None):
    url = url or DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
    return create_engine(url)


def _d(s):
    return date.fromisoformat(s) if s else None


def load_results(results, url=None):
    inv_rows, line_rows, issue_rows = [], [], []
    for r in results:
        e = r.get("extraction") or {}
        issues = r["issues"]
        inv_rows.append({
            "filename": r["filename"], "method": r["method"], "ocr_confidence": r["ocr_confidence"],
            "vendor_name": e.get("vendor_name"), "invoice_number": e.get("invoice_number"),
            "invoice_date": _d(e.get("invoice_date")), "due_date": _d(e.get("due_date")),
            "subtotal": e.get("subtotal"), "tax": e.get("tax"), "total_amount": e.get("total_amount"),
            "currency": e.get("currency"), "payment_terms": e.get("payment_terms"),
            "llm_confidence": r["llm_confidence"], "confidence": r["confidence"], "status": r["status"],
            "issue_count": len(issues), "critical_count": sum(i["severity"] == "critical" for i in issues),
        })
        for n, li in enumerate(e.get("line_items") or [], 1):
            line_rows.append({"filename": r["filename"], "line_no": n, **li})
        for i in issues:
            issue_rows.append({"filename": r["filename"], **i})

    invoices = pd.DataFrame(inv_rows)
    lines = pd.DataFrame(line_rows, columns=["filename", "line_no", "description", "quantity", "unit_price", "total"])
    issues_df = pd.DataFrame(issue_rows, columns=["filename", "code", "severity", "message"])

    engine = get_engine(url)
    invoices.to_sql("invoices", engine, if_exists="replace", index=False,
                    dtype={"invoice_date": Date(), "due_date": Date()})
    lines.to_sql("line_items", engine, if_exists="replace", index=False)
    issues_df.to_sql("validation_results", engine, if_exists="replace", index=False)
    return len(invoices), len(lines), len(issues_df)
