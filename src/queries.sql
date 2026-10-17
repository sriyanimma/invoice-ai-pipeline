-- Run all of these:   psql "$DATABASE_URL" -f src/queries.sql
-- (or paste them one at a time into psql / pgAdmin / DBeaver)

-- 1. How did documents get routed?
SELECT status, COUNT(*) AS documents,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM invoices GROUP BY status ORDER BY documents DESC;

-- 2. Which validation problems are most common?
SELECT code, severity, COUNT(*) AS occurrences
FROM validation_results GROUP BY code, severity ORDER BY occurrences DESC;

-- 3. Native PDF vs OCR: volume and average confidence
SELECT method, COUNT(*) AS documents, ROUND(AVG(confidence)::numeric, 3) AS avg_confidence
FROM invoices GROUP BY method;

-- 4. Spend and review burden per vendor
SELECT vendor_name, COUNT(*) AS invoices, ROUND(SUM(total_amount)::numeric, 2) AS total_spend,
       SUM((status <> 'auto_approved')::int) AS needing_review
FROM invoices GROUP BY vendor_name ORDER BY total_spend DESC;

-- 5. Invoices flagged as critical, with the reason
SELECT i.filename, i.vendor_name, v.code, v.message
FROM invoices i JOIN validation_results v USING (filename)
WHERE v.severity = 'critical' ORDER BY i.filename;
