"""Checks your machine is ready.  Run:  python -m src.check_setup"""
import sys

from src.config import ANTHROPIC_API_KEY, DATABASE_URL, MODEL


def check(name, fn):
    try:
        print(f"PASS  {name}" + (f"  ({r})" if (r := fn()) else ""))
        return True
    except Exception as e:
        print(f"FAIL  {name}: {type(e).__name__}: {str(e)[:200]}")
        return False


def python_ok():
    assert sys.version_info >= (3, 10), f"need Python 3.10+, found {sys.version.split()[0]}"
    return sys.version.split()[0]


def tesseract_ok():
    import pytesseract
    return f"tesseract {pytesseract.get_tesseract_version()}"


def api_ok():
    assert ANTHROPIC_API_KEY and "paste" not in ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY missing in .env"
    import anthropic
    anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
        model=MODEL, max_tokens=10, messages=[{"role": "user", "content": "Reply with OK"}])
    return f"model {MODEL}"


def db_ok():
    from sqlalchemy import text
    from src.load import get_engine
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return DATABASE_URL.split("@")[-1]


if __name__ == "__main__":
    results = [check("Python version", python_ok), check("Tesseract OCR", tesseract_ok),
               check("Anthropic API key", api_ok), check("PostgreSQL connection", db_ok)]
    print("\nAll good!" if all(results) else "\nFix the FAIL lines above, then re-run this script.")
