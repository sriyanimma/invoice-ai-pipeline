"""LLM extraction: document text -> validated Invoice object (Pydantic + Instructor)."""
import re

import anthropic
import instructor

from src.config import ANTHROPIC_API_KEY, MODEL
from src.schemas import InvoiceExtraction

SYSTEM_PROMPT = """You are a precise data-extraction engine for invoices.

Rules:
1. Extract ONLY values that appear in the text. Never infer, guess, calculate, or fill in defaults.
   If a field is not present, return null.
2. Dates must be ISO format YYYY-MM-DD. Numeric dates like 03/14/2026 are US format (month/day/year).
3. Amounts are plain numbers: no currency symbols, no thousands separators.
4. currency is the 3-letter code printed on the invoice (for example USD or EUR).
5. Copy numbers exactly as printed, even if they look wrong or do not add up. Never correct them.
6. line_items: one entry per row of the item table, in the order shown. The text may come from OCR, so
   columns can be scrambled: use the values and the arithmetic (quantity x unit price = line total) to
   match each description to its numbers.
7. confidence: integer 1-5 for how confident you are that the extraction is complete and correct
   (5 = clear text and every field found or clearly absent; 1 = garbled or ambiguous text).

Example input:
Acme Tools
INVOICE
Invoice #: A-77
Invoice Date: 2026-02-01
Terms: Net 30
Currency: USD
Hammer 2 $10.00 $20.00
Subtotal: $20.00
Tax: $1.65
Total: $21.65

Example output:
vendor_name="Acme Tools", invoice_number="A-77", invoice_date=2026-02-01, due_date=null,
line_items=[{description:"Hammer", quantity:2, unit_price:10.0, total:20.0}], subtotal=20.0, tax=1.65,
total_amount=21.65, currency="USD", payment_terms="Net 30", confidence=4
(due_date is null because no due date is printed; it is NOT calculated from the terms.)
"""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = instructor.from_anthropic(anthropic.Anthropic(api_key=ANTHROPIC_API_KEY))
    return _client


def extract_invoice(text):
    """Send document text to the LLM; returns an InvoiceExtraction (schema-enforced, auto-retried)."""
    return _get_client().messages.create(
        model=MODEL,
        max_tokens=2000,
        max_retries=2,          # if the output fails schema validation, Instructor re-asks the model
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Invoice text:\n\n{text}"}],
        response_model=InvoiceExtraction,
    )


def _norm(s):
    return re.sub(r"\s+", " ", str(s)).strip().casefold()


def grounding_score(data, text):
    """Fraction of key extracted values that literally appear in the source text (0..1)."""
    t, checks = _norm(text), []
    if data.get("vendor_name"):
        checks.append(_norm(data["vendor_name"]) in t)
    if data.get("invoice_number"):
        checks.append(_norm(data["invoice_number"]) in t)
    if data.get("total_amount") is not None:
        a = data["total_amount"]
        checks.append(any(s in text for s in (f"{a:,.2f}", f"{a:.2f}")))
    return sum(checks) / len(checks) if checks else 0.0


def confidence_score(data, text, ocr_confidence):
    """Blend three signals into one 0..1 score:
       50% the LLM's self-reported confidence, 30% grounding in the source text, 20% OCR quality."""
    llm = data.get("confidence", 1) / 5
    ocr = 1.0 if ocr_confidence is None else ocr_confidence / 100
    return round(0.5 * llm + 0.3 * grounding_score(data, text) + 0.2 * ocr, 3)
