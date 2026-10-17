"""Central settings. Everything tunable lives here."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
TRUTH_DIR = ROOT / "data" / "ground_truth"
OUT_DIR = ROOT / "outputs"
EXTRACT_DIR = OUT_DIR / "extractions"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Vendors + the items they sell: (description, min unit price, max unit price).
# Used by the data generator AND as the "known vendor list" business rule.
CATALOG = {
    "Lone Star Office Supply": [
        ("Copy paper (case)", 35, 55), ("Ink cartridges", 60, 120), ("Desk organizers", 12, 30),
        ("Printer toner", 90, 160), ("Whiteboard markers", 8, 20)],
    "Brightwave Logistics": [
        ("Freight - regional", 220, 480), ("Pallet wrapping", 15, 40), ("Last-mile delivery", 45, 95),
        ("Warehouse storage (week)", 120, 260), ("Fuel surcharge", 30, 70)],
    "Northgate IT Services": [
        ("Help desk support (hr)", 65, 110), ("Server maintenance", 300, 600), ("Software license", 80, 220),
        ("Network audit", 400, 900), ("Cloud backup (month)", 50, 150)],
    "Cedar Ridge Facilities": [
        ("Janitorial service", 150, 320), ("HVAC inspection", 180, 360), ("Window cleaning", 90, 200),
        ("Pest control", 70, 140), ("Landscaping", 120, 280)],
    "Summit Industrial Parts": [
        ("Hydraulic hose", 40, 95), ("Bearing set", 25, 80), ("Safety gloves (box)", 18, 35),
        ("Steel fasteners (bag)", 12, 45), ("Conveyor belt", 200, 480)],
    "Harborview Catering": [
        ("Lunch buffet (per person)", 14, 28), ("Coffee service", 60, 120), ("Boxed lunches", 11, 19),
        ("Dessert tray", 35, 75), ("Beverage package", 40, 90)],
}
KNOWN_VENDORS = list(CATALOG)

# Validation / routing thresholds (you will tune these on Sunday)
EXPECTED_CURRENCY = "USD"
OUTLIER_MULTIPLIER = 3.0          # flag if total > 3x the vendor's median invoice
AUTO_APPROVE_MIN_CONF = 0.80      # at/above this (and no issues) -> auto-approve
REVIEW_DETAILED_MAX_CONF = 0.50   # below this -> detailed human review
MIN_NATIVE_TEXT_CHARS = 50        # fewer chars than this in a PDF -> treat as scanned, use OCR
