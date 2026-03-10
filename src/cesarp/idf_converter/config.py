"""
config.py
Project paths. Name mappings are auto-detected from IDF content.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CESARP_DIR = os.path.join(BASE_DIR, "IDFs", "CESARP")
NESTLI_IDF = os.path.join(BASE_DIR, "IDFs", "NESTLI", "Foursquare_nestli.idf")
OUTPUT_DIR = os.path.join(BASE_DIR, "results")

TARGET_EP_VERSION = "23.1.0.002"

# Category codes found in CESAR-P URIs -> readable prefixes
# Pattern: {year}_{code}{N}_L{layer}
# Gr = Ground, Wa = Wall, Ro = Roof, Wi = Window
CATEGORY_LABELS = {
    "Gr": "Ground",
    "Wa": "Wall",
    "Ro": "Roof",
    "Wi": "Window",
    "Fl": "Floor",
    "Ce": "Ceiling",
    "In": "Insulation",
}

# Construction URI path segments -> readable prefixes
CONSTRUCTION_LABELS = {
    "grounds": "Ground",
    "walls": "Wall",
    "roofs": "Roof",
    "windows": "Window",
    "floors": "Floor",
}
