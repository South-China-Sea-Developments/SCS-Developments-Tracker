"""Canonical schema: tables, columns and code sets. See docs/spec.md and CONTEXT.md.

The MATS packed codes (Domains, Issues, Locations) are not stored; they are derived
from the flag columns by the functions at the bottom and checked by the validator.
"""

CLAIMANTS = [
    ("CN", "China"),
    ("VN", "Vietnam"),
    ("PH", "Philippines"),
    ("MY", "Malaysia"),
    ("ID", "Indonesia"),
    ("TW", "Taiwan"),
]
CLAIMANT_CODES = [c for c, _ in CLAIMANTS]

TYPE_FLAGS = ["declarative", "demonstrative", "coercive", "force"]
DOMAIN_FLAGS = ["domestic", "diplomatic", "physical"]
ISSUE_FLAGS = ["military", "administrative", "energy", "fisheries", "politics"]
SUBREGION_FLAGS = [
    "loc01_tonkin",
    "loc02_paracels",
    "loc03_central_west",
    "loc04_central_east",
    "loc05_spratly_nw",
    "loc06_spratly_ne",
    "loc07_spratly_se",
    "loc08_spratly_sw",
    "loc09_nam_con_son",
    "loc10_far_south",
]
SUBREGION_NAMES = [
    "Gulf of Tonkin", "Paracels", "Central-West", "Central-East", "Spratly NW",
    "Spratly NE", "Spratly SE", "Spratly SW", "Nam Con Son", "Far South",
]
FLAG_COLUMNS = TYPE_FLAGS + DOMAIN_FLAGS + ISSUE_FLAGS + SUBREGION_FLAGS

# Dyad codes: actor first, target second (MATS). R=ROC, C=PRC, P=Philippines,
# V=Vietnam, M=Malaysia, B=Brunei, I=Indonesia, A=all states, U=unclear.
# A single letter (e.g. "A") occurs in MATS 1.02 (CN200001 "CV A") and is allowed.
DYAD_LETTERS = set("RCPVMBIAU")

MOVE_STATUS = ["accepted", "pending"]
CODED_BY = ["chubb", "project"]
INTENSIFICATION_CRITERIA = ["", "novelty", "frequency", "scope"]

EVENT_STATUS = ["candidate", "accepted", "rejected", "merged"]
DATE_PRECISION = ["day", "month", "year"]
LOCATION_PRECISION = ["point", "feature", "subregion", "unknown"]

TABLES = {
    "claimants": ["code", "name"],
    "moves": [
        "move_id", "claimant", "year", "instance_no",
        *TYPE_FLAGS, *DOMAIN_FLAGS, *ISSUE_FLAGS, *SUBREGION_FLAGS,
        "dyads", "description",
        "ongoing_through", "ongoing_through_notes",
        "diminished_notes", "other_possible_cases",
        "intensification_criterion", "org_case_no",
        "coded_by", "coder", "coding_date", "data_version", "status",
    ],
    "events": [
        "event_id", "move_id", "claimant",
        "date_start", "date_end", "date_precision",
        "lat", "lon", "location_name", "location_precision", "subregion",
        "summary", "actors", "status",
        "harvest_run_id", "extractor",
        "suggested_move_id", "suggested_type", "suggested_domains", "suggested_issues",
        "suggested_dyads", "suggestion_reasoning",
        "reviewer", "review_date", "review_note",
    ],
    "sources": [
        "source_id", "event_id", "url", "title", "publisher", "pub_date", "language",
        "accessed_date", "archive_url", "excerpt",
    ],
    "corrections": ["move_id", "field", "new_value", "date", "by", "reason"],
}

ID_COLUMN = {"claimants": "code", "moves": "move_id", "events": "event_id", "sources": "source_id"}


def _packed(move, flags, digits):
    code = "".join(d for f, d in zip(flags, digits) if str(move[f]) == "1")
    return int(code) if code else 0


def packed_domains(move) -> int:
    """MATS 'Domains': digits 1-3 for Domestic, Diplomatic, Physical, e.g. 13."""
    return _packed(move, DOMAIN_FLAGS, "123")


def packed_issues(move) -> int:
    """MATS 'Issues': digits 1-5 for Military, Administrative, Energy, Fisheries, Politics."""
    return _packed(move, ISSUE_FLAGS, "12345")


def packed_locations(move) -> int:
    """MATS 'Locations': digits 1-9 for sub-regions 1-9 and 0 for Far South (10), e.g. 258."""
    return _packed(move, SUBREGION_FLAGS, "1234567890")
