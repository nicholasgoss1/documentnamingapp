"""
Settings persistence using JSON stored in Windows AppData.
"""
import json
import os
import sys
from pathlib import Path
from copy import deepcopy

APP_NAME = "ClaimFileRenamer"
APP_VERSION = "1.0.0"


def get_app_data_dir() -> Path:
    """Return per-user app data directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    app_dir = base / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_logs_dir() -> Path:
    d = get_app_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_exports_dir() -> Path:
    d = get_app_data_dir() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_rollback_dir() -> Path:
    d = get_app_data_dir() / "rollback"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULT_SETTINGS = {
    "dark_mode": True,
    "confidence_threshold": 60,
    "strip_annexure_prefix": True,
    "preserve_annexure_metadata": True,
    "photo_schedule_date_mode": "conservative",
    "duplicate_handling": "flag_for_review",
    "last_who": "FF",
    "last_entity": "",
    "last_directory": "",
    "who_mapping": {
        "complainant_keywords": [
            "claimsco", "client", "complainant", "authority", "engagement",
            "acb", "ruca", "balmoral", "patcol", "auscoast"
        ],
        "afca_keywords": [
            "afca", "australian financial complaints"
        ],
        "ff_keywords": [
            "sedgwick", "campbell", "morse", "qbe", "insurer",
            "idr", "fdl", "panel", "loss adjuster",
            "allianz", "suncorp", "iag", "cgu", "hollard",
            "youi", "zurich", "chubb", "aig", "aami",
            "gio", "nrma", "bupa", "medibank", "nib",
            "budget direct", "racv", "racq"
        ],
        "complainant_entities": ["ACB", "AusCoast", "RUCA", "Balmoral", "Patcol"],
        "ff_entities": [
            "Sedgwick", "Campbell Constructions", "Morse Building Consultants",
            "QBE", "WeatherWatch", "BoM",
            # General insurers
            "AAI", "Suncorp", "IAG", "Insurance Australia Limited",
            "CGU", "Allianz", "Allianz Australia",
            "QBE Australia", "Hollard", "Auto & General",
            "Youi", "Zurich Australian Insurance", "Zurich",
            "Chubb", "Chubb Insurance Australia",
            "AIG", "AIG Australia",
            "RAA Insurance", "RACQ Insurance", "RAC Insurance",
            "RACT Insurance", "Guild Insurance", "Ansvar Insurance",
            "Eric Insurance", "Pacific International Insurance",
            "Aioi Nissay Dowa", "Tokio Marine", "MSIG",
            "Sompo Japan", "Liberty Specialty",
            "Berkshire Hathaway Specialty", "HDI Global",
            "Great Lakes Insurance", "AXA XL", "XL Insurance",
            "Swiss Re", "CNA Insurance", "Berkley Insurance",
            "Arch Insurance", "Munich Re", "SCOR",
            "Atradius Credit", "Coface", "Allianz Trade",
            "Euler Hermes", "QBE LMI", "Helia", "Genworth",
            "Avant Insurance", "MIGA", "MDA National Insurance",
            "Lloyd's Underwriters",
            # Life insurers
            "AIA Australia", "AIA", "TAL Life", "TAL",
            "MLC Life", "MLC", "Zurich Life", "OnePath",
            "Resolution Life", "MetLife", "MetLife Australia",
            "Challenger Life", "Challenger",
            "ClearView Life", "ClearView",
            "Integrity Life", "NobleOak", "NobleOak Life",
            "HCF Life", "Swiss Re Life",
            "RGA Australia", "Hannover Life Re",
            "Australian Unity Friendly Society",
            "Foresters Friendly Society",
            # Health insurers
            "Bupa", "Medibank", "ahm",
            "nib", "HCF", "HBF",
            "Australian Unity Health", "Australian Unity",
            "GMHBA", "Frank",
            "Teachers Health", "CBHS", "CBHS Corporate",
            "Defence Health", "Police Health",
            "Emergency Services Health", "Health Partners",
            "St.LukesHealth", "Westfund", "Mildura Health",
            "Queensland Country Health", "HIF",
            "Peoplecare", "TUH", "Navy Health",
            "Latrobe Health", "Reserve Bank Health",
            "AIA Health",
            # White-label / retail brands
            "Everyday Insurance", "Coles Insurance",
            "ALDI Insurance", "Kogan Insurance",
            "Australia Post Insurance",
            "Commonwealth Bank Insurance",
            "Qantas Insurance", "Virgin Money Insurance",
            "ING Insurance",
            "Bank of Queensland", "Honey Home",
            "AAMI", "GIO", "Apia", "Shannons", "Bingle",
            "CIL", "Terri Scheer", "NRMA Insurance", "NRMA",
            "CGU Insurance", "SGIO", "SGIC",
            "RACV Insurance", "RACV",
            "Elders Insurance", "Australian Seniors",
            "Real Insurance",
            "Pet Insurance Australia", "RSPCA Pet Insurance",
            "Bow Wow Meow",
            "Cover-More", "Flight Centre Travel Insurance",
            "Allianz Direct", "Worldcare Travel Insurance",
            "Budget Direct", "Ozicare",
            "Qantas Insurance Health",
            "Huddle Insurance", "Honey Insurance", "Trov",
            "Strata Community Insurance", "CHU Insurance",
            "Catholic Church Insurance",
        ],
        "afca_entities": ["AFCA"]
    },
    "entity_aliases": {
        "Campbell Construction": "Campbell Constructions",
        "Campbell Construction Co": "Campbell Constructions",
        "CCC": "Campbell Constructions",
        "Morse Building Consultant": "Morse Building Consultants",
        "Morse Building Consultancy": "Morse Building Consultants",
        "Morse Consultants": "Morse Building Consultants",
        "Morse": "Morse Building Consultants",
        "AusCoast Builders": "AusCoast",
        "Aus Coast": "AusCoast",
        "Allianz Australia Insurance": "Allianz",
        "Allianz Australia Insurance Limited": "Allianz",
        "Allianz Insurance": "Allianz",
        "Suncorp Group": "Suncorp",
        "AAI Limited": "AAI",
        "Insurance Australia Group": "IAG",
        "IAG Limited": "IAG",
        "CGU Insurance Limited": "CGU",
        "QBE Insurance": "QBE",
        "QBE Insurance (Australia) Limited": "QBE",
        "Chubb Insurance Australia Limited": "Chubb",
        "AIG Australia Limited": "AIG",
        "Zurich Australian Insurance Limited": "Zurich",
        "Zurich Insurance": "Zurich",
        "Auto and General": "Auto & General",
        "Auto and General Insurance": "Auto & General",
        "NRMA Insurance Limited": "NRMA",
        "RACV Insurance": "RACV",
        "Budget Direct Insurance": "Budget Direct",
        "Hollard Insurance": "Hollard",
        "Hollard Insurance Company": "Hollard",
        "MLC Life Insurance": "MLC Life",
        "TAL Life Limited": "TAL Life",
        "TAL Life Insurance": "TAL Life",
        "AIA Australia Limited": "AIA",
        "MetLife Insurance Limited": "MetLife",
        "Genworth Financial": "Genworth",
        "Helia Group": "Helia",
        "OnePath Life": "OnePath",
        "OnePath Insurance": "OnePath",
        "Resolution Life Australasia": "Resolution Life",
        "Cover More": "Cover-More",
        "CoverMore": "Cover-More"
    },
    "preferred_entities": [
        "Campbell Constructions", "Sedgwick", "Morse Building Consultants",
        "QBE", "AFCA", "ACB", "AusCoast", "RUCA", "Balmoral", "Patcol",
        "WeatherWatch", "BoM", "COI"
    ],
    "preferred_doc_labels": [
        "Site Report", "Photo Schedule", "Assessment Report",
        "Progress Report 1", "Progress Report 2", "Roof Report",
        "Initial Claims Advice", "Claim Lodgement Email",
        "Claim Lodgement Form", "Policy Schedule",
        "Certificate of Insurance", "PDS", "IDR FDL",
        "Notice of Response", "Notice of Response from QBE",
        "AFCA Submission", "Letter of Engagement", "Building Report",
        "Supplementary Report", "Supplementary Technical Assessment Report",
        "Hail Report", "Quote", "Weather Pack", "AAF to be signed",
        "Request for Information", "Written Preliminary Assessment"
    ],
    "doc_type_keywords": {
        "Site Report": ["site report", "site inspection"],
        "Photo Schedule": ["photo schedule", "photo report", "photographs", "photo appendix"],
        "Assessment Report": ["assessment report", "loss assessment"],
        "Progress Report": ["progress report"],
        "Roof Report": ["roof report", "roof inspection", "roof assessment"],
        "Initial Claims Advice": ["initial claims advice", "initial advice"],
        "Claim Lodgement Email": ["claim lodgement email", "lodgement email"],
        "Claim Lodgement Form": ["claim lodgement form", "claim form", "lodgement form"],
        "Policy Schedule": ["policy schedule", "schedule of insurance"],
        "Certificate of Insurance": ["certificate of insurance", "coi"],
        "PDS": ["product disclosure statement", "pds"],
        "IDR FDL": [
            "idr", "final decision letter", "internal dispute resolution",
            "idr response", "final decision", "complaint"
        ],
        "Notice of Response": ["notice of response"],
        "AFCA Submission": ["afca submission", "submission to afca"],
        "Letter of Engagement": ["letter of engagement", "engagement letter"],
        "Building Report": ["building report", "building inspection"],
        "Supplementary Report": ["supplementary report", "supplementary assessment"],
        "Supplementary Technical Assessment Report": [
            "supplementary technical assessment",
            "supplementary technical report"
        ],
        "Hail Report": ["hail report", "hail damage", "hail assessment"],
        "Quote": ["quote", "quotation", "estimate"],
        "Weather Pack": ["weather pack", "weather report", "weather data"],
        "AAF to be signed": ["authority and access form", "aaf"],
        "Request for Information": ["request for information", "rfi"],
        "Written Preliminary Assessment": [
            "written preliminary assessment", "preliminary assessment"
        ]
    },
    "entity_include_rules": {
        "Site Report": True,
        "Photo Schedule": True,
        "Assessment Report": True,
        "Progress Report 1": True,
        "Progress Report 2": True,
        "Roof Report": True,
        "Building Report": True,
        "Supplementary Report": True,
        "Supplementary Technical Assessment Report": True,
        "Hail Report": True,
        "Quote": True,
        "IDR FDL": False,
        "Notice of Response": False,
        "Notice of Response from QBE": False,
        "AFCA Submission": False,
        "Letter of Engagement": False,
        "Policy Schedule": False,
        "Certificate of Insurance": True,
        "PDS": False,
        "Weather Pack": False,
        "AAF to be signed": False,
        "Request for Information": False,
        "Written Preliminary Assessment": False,
        "Claim Lodgement Email": False,
        "Claim Lodgement Form": False,
        "Initial Claims Advice": False
    },
    "presets": {}
}


class Settings:
    """Manage application settings with JSON persistence."""

    def __init__(self):
        self._path = get_app_data_dir() / "settings.json"
        self._data = deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._deep_merge(self._data, saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    @property
    def data(self):
        return self._data

    def save_preset(self, name: str, preset_data: dict):
        presets = self._data.get("presets", {})
        presets[name] = preset_data
        self._data["presets"] = presets
        self.save()

    def load_preset(self, name: str) -> dict:
        return self._data.get("presets", {}).get(name, {})

    def delete_preset(self, name: str):
        presets = self._data.get("presets", {})
        presets.pop(name, None)
        self._data["presets"] = presets
        self.save()

    def _deep_merge(self, base: dict, override: dict):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
