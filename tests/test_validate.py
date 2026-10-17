from src.validate import route, validate_invoice, vendor_medians


def good():
    return {
        "vendor_name": "Lone Star Office Supply", "invoice_number": "INV-1", "invoice_date": "2026-03-01",
        "due_date": "2026-03-31", "currency": "USD", "subtotal": 100.0, "tax": 8.25, "total_amount": 108.25,
        "line_items": [{"description": "x", "quantity": 2, "unit_price": 50.0, "total": 100.0}],
    }


def codes(e, medians=None):
    return {i["code"] for i in validate_invoice(e, medians)}


def test_clean_invoice_has_no_issues():
    assert codes(good()) == set()


def test_total_mismatch():
    e = good(); e["total_amount"] = 150.0
    assert "total_mismatch" in codes(e)


def test_line_sum_mismatch():
    e = good(); e["subtotal"] = 130.0; e["total_amount"] = 138.25
    assert "line_sum_mismatch" in codes(e)


def test_missing_invoice_number_is_critical():
    e = good(); e["invoice_number"] = None
    issues = validate_invoice(e)
    assert any(i["code"] == "missing_invoice_number" and i["severity"] == "critical" for i in issues)


def test_due_before_invoice():
    e = good(); e["due_date"] = "2026-02-01"
    assert "due_before_invoice" in codes(e)


def test_unexpected_currency_and_unknown_vendor():
    e = good(); e["currency"] = "EUR"; e["vendor_name"] = "Mystery Co"
    assert {"unexpected_currency", "unknown_vendor"} <= codes(e)


def test_amount_outlier_uses_vendor_median():
    meds = vendor_medians([dict(good(), total_amount=t) for t in (100, 110, 95, 105, 1000)])
    e = good(); e["total_amount"] = 1000.0; e["subtotal"] = 923.8; e["tax"] = 76.2
    assert "amount_outlier" in codes(e, meds)


def test_routing():
    assert route([], 0.95) == "auto_approved"
    assert route([], 0.70) == "review_fast"
    assert route([{"severity": "warning"}], 0.95) == "review_fast"
    assert route([{"severity": "critical"}], 0.95) == "review_detailed"
    assert route([], 0.30) == "review_detailed"
