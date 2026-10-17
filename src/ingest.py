"""Turn a PDF or image into text. Native PDF text first; OCR as the fallback."""
from pathlib import Path

import pymupdf  # PyMuPDF
import pytesseract
from PIL import Image

from src.config import MIN_NATIVE_TEXT_CHARS

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
DOC_EXTS = IMAGE_EXTS | {".pdf"}


def _ocr(img):
    """Return (text, mean_confidence_0_to_100) for a PIL image."""
    text = pytesseract.image_to_string(img)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    confs = [float(c) for c in data["conf"] if float(c) >= 0]
    return text, (sum(confs) / len(confs) if confs else 0.0)


def read_document(path):
    """Return {filename, text, method ('native'|'ocr'), ocr_confidence (None for native)}."""
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        doc = pymupdf.open(path)
        text = "\n".join(page.get_text() for page in doc)
        if len(text.strip()) >= MIN_NATIVE_TEXT_CHARS:
            return {"filename": path.name, "text": text, "method": "native", "ocr_confidence": None}
        texts, confs = [], []
        for page in doc:  # scanned PDF: render each page and OCR it
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            t, c = _ocr(img)
            texts.append(t)
            confs.append(c)
        return {"filename": path.name, "text": "\n".join(texts), "method": "ocr",
                "ocr_confidence": sum(confs) / len(confs) if confs else 0.0}

    if ext in IMAGE_EXTS:
        text, conf = _ocr(Image.open(path).convert("RGB"))
        return {"filename": path.name, "text": text, "method": "ocr", "ocr_confidence": conf}

    raise ValueError(f"Unsupported file type: {path.name}")
