"""Run the whole pipeline:  ingest -> extract (LLM) -> validate -> route -> load to Postgres.

    python run_pipeline.py --limit 5     # try a few documents first (cheap)
    python run_pipeline.py               # all documents
    python run_pipeline.py --force       # ignore cached LLM results and re-extract everything
    python run_pipeline.py --no-db       # skip the database load
"""
import argparse
import json
from collections import Counter

from src.config import EXTRACT_DIR, OUT_DIR, RAW_DIR
from src.extract import confidence_score, extract_invoice
from src.ingest import DOC_EXTS, read_document
from src.validate import route, validate_invoice, vendor_medians


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="re-run the LLM even if a cached result exists")
    ap.add_argument("--no-db", action="store_true")
    args = ap.parse_args()

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in RAW_DIR.glob("*") if p.suffix.lower() in DOC_EXTS)
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit("No documents found. Run:  python -m src.generate_data")

    records = []
    for n, path in enumerate(files, 1):
        doc = read_document(path)
        cache = EXTRACT_DIR / f"{path.stem}.json"
        error, ext = None, None
        if cache.exists() and not args.force:
            ext = json.loads(cache.read_text())
        else:
            try:
                ext = extract_invoice(doc["text"]).model_dump(mode="json")
                cache.write_text(json.dumps(ext, indent=2))
            except Exception as exc:  # keep going; one bad document must not stop the batch
                error = f"{type(exc).__name__}: {exc}"
        print(f"[{n}/{len(files)}] {path.name}  ({doc['method']})" + (f"  ERROR: {error[:80]}" if error else ""))
        records.append({"doc": doc, "ext": ext, "error": error})

    medians = vendor_medians([r["ext"] for r in records])
    results = []
    for r in records:
        doc, ext = r["doc"], r["ext"]
        if ext is None:
            issues = [{"code": "extraction_failed", "severity": "critical", "message": r["error"] or "unknown"}]
            conf, llm_conf = 0.0, 0
        else:
            issues = validate_invoice(ext, medians)
            conf, llm_conf = confidence_score(ext, doc["text"], doc["ocr_confidence"]), ext["confidence"]
        results.append({
            "filename": doc["filename"], "method": doc["method"], "ocr_confidence": doc["ocr_confidence"],
            "extraction": ext, "llm_confidence": llm_conf, "confidence": conf,
            "issues": issues, "status": route(issues, conf), "error": r["error"],
        })

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2))
    print("\nStatus counts:", dict(Counter(x["status"] for x in results)))

    if not args.no_db:
        from src.load import load_results
        inv, lines, iss = load_results(results)
        print(f"Loaded into PostgreSQL: {inv} invoices, {lines} line items, {iss} validation issues")


if __name__ == "__main__":
    main()
