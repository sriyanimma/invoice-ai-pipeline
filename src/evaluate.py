"""Compare pipeline output to the ground-truth answer keys. This produces your real resume numbers.

    python -m src.evaluate
"""
import csv
import json
from collections import defaultdict

from src.config import OUT_DIR, TRUTH_DIR

SCALAR = ["vendor_name", "invoice_number", "invoice_date", "due_date", "subtotal", "tax",
          "total_amount", "currency", "payment_terms"]
FIELDS = SCALAR + ["line_items"]
NUMERIC = {"subtotal", "tax", "total_amount"}
EXPECTED_CODE = {  # injected problem -> validator code that should catch it
    "total_mismatch": "total_mismatch", "line_sum_mismatch": "line_sum_mismatch",
    "missing_invoice_number": "missing_invoice_number", "missing_due_date": "missing_due_date",
    "due_before_invoice": "due_before_invoice", "amount_outlier": "amount_outlier",
    "foreign_currency": "unexpected_currency",
}


def _lines_equal(t, p):
    t, p = t or [], p or []
    if len(t) != len(p):
        return False
    return all(abs(a["quantity"] - b["quantity"]) < 0.01 and abs(a["unit_price"] - b["unit_price"]) < 0.01
               and abs(a["total"] - b["total"]) < 0.01 for a, b in zip(t, p))


def field_correct(field, truth, pred):
    if field == "line_items":
        return _lines_equal(truth.get("line_items"), pred.get("line_items"))
    t, p = truth.get(field), pred.get(field)
    if t is None or p is None:
        return t is None and p is None
    if field in NUMERIC:
        return abs(float(t) - float(p)) < 0.01
    return str(t).strip().casefold() == str(p).strip().casefold()


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def main():
    results = json.loads((OUT_DIR / "results.json").read_text())
    rows, per_field, per_method = [], defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    exact_docs = 0
    det = defaultdict(lambda: [0, 0])   # issue type -> [caught, injected]
    clean_docs = clean_flagged = 0
    status_counts, auto_total, auto_clean_extraction = defaultdict(int), 0, 0
    auto_with_injected_issue = 0

    for r in results:
        truth = json.loads((TRUTH_DIR / (r["filename"].rsplit(".", 1)[0] + ".json")).read_text())
        pred = r["extraction"] or {}
        correct = {f: field_correct(f, truth, pred) for f in FIELDS}
        n_ok = sum(correct.values())
        for f, ok in correct.items():
            per_field[f][0] += ok
            per_field[f][1] += 1
            per_method[r["method"]][0] += ok
            per_method[r["method"]][1] += 1
        all_ok = n_ok == len(FIELDS)
        exact_docs += all_ok

        injected = truth["_meta"]["issues"]
        flagged = {i["code"] for i in r["issues"]}
        for inj in injected:
            det[inj][1] += 1
            det[inj][0] += EXPECTED_CODE[inj] in flagged
        if not injected:
            clean_docs += 1
            clean_flagged += bool(r["issues"])

        status_counts[r["status"]] += 1
        if r["status"] == "auto_approved":
            auto_total += 1
            auto_clean_extraction += all_ok
            auto_with_injected_issue += bool(injected)

        rows.append({"filename": r["filename"], "method": r["method"], "status": r["status"],
                     "confidence": r["confidence"], "fields_correct": f"{n_ok}/{len(FIELDS)}",
                     "injected_issues": ";".join(injected), "flagged_codes": ";".join(sorted(flagged)),
                     "wrong_fields": ";".join(f for f, ok in correct.items() if not ok)})

    n = len(results)
    tot_ok = sum(v[0] for v in per_field.values())
    tot = sum(v[1] for v in per_field.values())
    inj_caught = sum(v[0] for v in det.values())
    inj_total = sum(v[1] for v in det.values())

    out = ["# Evaluation summary", "", f"Documents evaluated: **{n}**", "",
           "## Extraction accuracy",
           f"- Field-level accuracy: **{pct(tot_ok, tot)}** ({tot_ok}/{tot} fields)",
           f"- Documents with every field correct: **{pct(exact_docs, n)}** ({exact_docs}/{n})", "",
           "| Field | Accuracy |", "|---|---|"]
    out += [f"| {f} | {pct(*per_field[f])} |" for f in FIELDS]
    out += ["", "| Input type | Field accuracy | Fields |", "|---|---|---|"]
    out += [f"| {m} | {pct(*v)} | {v[1]} |" for m, v in sorted(per_method.items())]
    out += ["", "## Validation engine (injected problems)",
            f"- Injected problems caught: **{pct(inj_caught, inj_total)}** ({inj_caught}/{inj_total})",
            f"- Clean documents wrongly flagged (false positives): **{pct(clean_flagged, clean_docs)}** "
            f"({clean_flagged}/{clean_docs})", "", "| Problem type | Caught |", "|---|---|"]
    out += [f"| {k} | {v[0]}/{v[1]} |" for k, v in sorted(det.items())]
    out += ["", "## Routing",
            f"- Auto-approved: **{pct(status_counts['auto_approved'], n)}** ({status_counts['auto_approved']}/{n})",
            f"- Fast review: {status_counts['review_fast']}   Detailed review: {status_counts['review_detailed']}",
            f"- Accuracy of auto-approved documents (all fields correct): **{pct(auto_clean_extraction, auto_total)}**",
            f"- Auto-approved documents that contained an injected problem: **{auto_with_injected_issue}** (should be 0)"]
    report = "\n".join(out)
    print(report)
    (OUT_DIR / "evaluation_summary.md").write_text(report)
    with open(OUT_DIR / "evaluation_per_document.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved: {OUT_DIR/'evaluation_summary.md'} and evaluation_per_document.csv")


if __name__ == "__main__":
    main()
