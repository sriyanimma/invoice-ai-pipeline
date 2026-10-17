"""Generate synthetic invoices (PDFs + a few noisy 'scans') with ground-truth answer keys.

Run:  python -m src.generate_data
"""
import json
import random
from datetime import date, timedelta

import pymupdf  # PyMuPDF
import numpy as np
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from src.config import CATALOG, RAW_DIR, TRUTH_DIR

N_INVOICES = 45
N_SCANNED = 10
N_WITH_ISSUES = 14          # 2 of each issue type
SEED = 42
TAX_RATE = 0.0825

ISSUE_TYPES = [
    "total_mismatch", "line_sum_mismatch", "missing_invoice_number", "missing_due_date",
    "due_before_invoice", "amount_outlier", "foreign_currency",
]

LABELS = {
    "A": dict(num="Invoice #:", date="Invoice Date:", due="Due Date:", terms="Payment Terms:",
              cols=("Description", "Qty", "Unit Price", "Total"),
              sub="Subtotal:", tax="Tax (8.25%):", total="Total:"),
    "B": dict(num="INVOICE NO.", date="Issued", due="Payment due", terms="Terms",
              cols=("Item", "Quantity", "Rate", "Amount"),
              sub="Sub-total", tax="Sales tax", total="Amount Due"),
    "C": dict(num="Ref:", date="Invoice Date", due="Due By", terms="Terms of payment",
              cols=("Details", "Units", "Price per unit", "Line total"),
              sub="Net amount", tax="Tax", total="Grand Total"),
}


def fmt_date(iso, style):
    d = date.fromisoformat(iso)
    return {"A": d.isoformat(), "B": d.strftime("%b %d, %Y"), "C": d.strftime("%m/%d/%Y")}[style]


def money(x, cur):
    return f"${x:,.2f}" if cur == "USD" else f"EUR {x:,.2f}"


def build_invoice(i, issues):
    """Return the ground-truth dict: exactly what is PRINTED on the document."""
    vendor = random.choice(list(CATALOG))
    inv_date = date(2026, 1, 1) + timedelta(days=random.randint(0, 270))
    terms = random.choice(["Net 15", "Net 30", "Net 45"])
    due = inv_date + timedelta(days=int(terms.split()[1]))

    items = []
    for desc, lo, hi in random.sample(CATALOG[vendor], k=random.randint(2, 5)):
        qty = random.randint(1, 12)
        if "amount_outlier" in issues:
            qty *= 10
        price = round(random.uniform(lo, hi), 2)
        items.append({"description": desc, "quantity": qty, "unit_price": price,
                      "total": round(qty * price, 2)})

    subtotal = round(sum(it["total"] for it in items), 2)
    if "line_sum_mismatch" in issues:
        subtotal = round(subtotal + random.choice([25.00, 40.00, -30.00]), 2)
    tax = round(subtotal * TAX_RATE, 2)
    total = round(subtotal + tax, 2)
    if "total_mismatch" in issues:
        total = round(total + random.choice([50.00, 75.00, -60.00, 120.00]), 2)

    inv_no = f"INV-{10000 + i}"
    if "missing_invoice_number" in issues:
        inv_no = None
    if "missing_due_date" in issues:
        due = None
    elif "due_before_invoice" in issues:
        due = inv_date - timedelta(days=random.randint(5, 20))

    return {
        "vendor_name": vendor,
        "invoice_number": inv_no,
        "invoice_date": inv_date.isoformat(),
        "due_date": due.isoformat() if due else None,
        "line_items": items,
        "subtotal": subtotal,
        "tax": tax,
        "total_amount": total,
        "currency": "EUR" if "foreign_currency" in issues else "USD",
        "payment_terms": terms,
    }


def render_pdf(path, inv, style):
    L = LABELS[style]
    cur = inv["currency"]
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 60

    if style == "C":
        c.setFont("Helvetica", 9)
        c.drawString(50, y + 18, "Bill From:")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, inv["vendor_name"])
    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(width - 50, y, "INVOICE")
    y -= 50

    meta = []
    if inv["invoice_number"]:
        meta.append((L["num"], inv["invoice_number"]))
    meta.append((L["date"], fmt_date(inv["invoice_date"], style)))
    if inv["due_date"]:
        meta.append((L["due"], fmt_date(inv["due_date"], style)))
    meta.append((L["terms"], inv["payment_terms"]))
    meta.append(("Currency:", cur))
    for label, value in meta:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(170, y, str(value))
        y -= 16
    y -= 20

    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, L["cols"][0])
    c.drawRightString(330, y, L["cols"][1])
    c.drawRightString(440, y, L["cols"][2])
    c.drawRightString(540, y, L["cols"][3])
    c.line(50, y - 4, 540, y - 4)
    y -= 22
    c.setFont("Helvetica", 10)
    for it in inv["line_items"]:
        c.drawString(50, y, it["description"])
        c.drawRightString(330, y, f"{it['quantity']}")
        c.drawRightString(440, y, money(it["unit_price"], cur))
        c.drawRightString(540, y, money(it["total"], cur))
        y -= 18
    c.line(50, y + 6, 540, y + 6)
    y -= 12

    for label, value, bold in [(L["sub"], inv["subtotal"], False), (L["tax"], inv["tax"], False),
                               (L["total"], inv["total_amount"], True)]:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        c.drawString(380, y, label)
        c.drawRightString(540, y, money(value, cur))
        y -= 16

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 60, "Thank you for your business. Please remit payment by the due date.")
    c.save()


def pdf_to_noisy_png(pdf_path, png_path):
    """Simulate a mediocre scan: render, rotate slightly, blur, add noise."""
    doc = pymupdf.open(pdf_path)
    pix = doc[0].get_pixmap(dpi=200)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img = img.rotate(random.uniform(-1.5, 1.5), expand=True, fillcolor="white")
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    arr = np.array(img).astype(np.int16)
    arr += np.random.normal(0, 10, arr.shape).astype(np.int16)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("L").save(png_path, optimize=True)


def main():
    random.seed(SEED)
    np.random.seed(SEED)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    for p in list(RAW_DIR.glob("*")) + list(TRUTH_DIR.glob("*")):
        if p.is_file():
            p.unlink()

    order = list(range(N_INVOICES))
    random.shuffle(order)
    issues_for = {i: [] for i in range(N_INVOICES)}
    for k, i in enumerate(order[:N_WITH_ISSUES]):
        issues_for[i] = [ISSUE_TYPES[k % len(ISSUE_TYPES)]]
    scanned = set(random.sample(range(N_INVOICES), N_SCANNED))

    for i in range(N_INVOICES):
        style = random.choice(["A", "B", "C"])
        inv = build_invoice(i, issues_for[i])
        stem = f"invoice_{i + 1:03d}"
        pdf_path = RAW_DIR / f"{stem}.pdf"
        render_pdf(pdf_path, inv, style)
        is_scan = i in scanned
        if is_scan:
            pdf_to_noisy_png(pdf_path, RAW_DIR / f"{stem}.png")
            pdf_path.unlink()
        truth = dict(inv)
        truth["_meta"] = {"issues": issues_for[i], "style": style, "scanned": is_scan}
        (TRUTH_DIR / f"{stem}.json").write_text(json.dumps(truth, indent=2))

    print(f"Generated {N_INVOICES} invoices in {RAW_DIR} "
          f"({N_SCANNED} scanned PNGs, {N_WITH_ISSUES} with injected problems).")
    print(f"Answer keys are in {TRUTH_DIR}")


if __name__ == "__main__":
    main()
