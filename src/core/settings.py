"""
Settings persistence using JSON stored in Windows AppData.
"""
import json
import os
import sys
from pathlib import Path
from copy import deepcopy

APP_NAME = "ClaimsCo Document Tools"
APP_VERSION = "2.1.2"


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
            "budget direct", "racv", "racq",
            "engineering services", "clear engineering",
            "australian building & construction", "australian building and construction",
            "tomkat roofing", "mcs group",
            "certified building inspection",
            "live electrical", "aizer insurance builders", "aizer insurance",
            "aizer group", "salt water roofing", "saltwater roofing",
            "imparta engineers", "imparta",
            "aj grant"
        ],
        "complainant_entities": ["ClaimsCo", "ACB", "AusCoast", "RUCA", "Balmoral", "Patcol"],
        "ff_entities": [
            "Sedgwick", "Campbell Constructions", "Morse Building Consultants",
            "Clear Engineering Services", "Australian Building & Construction",
            "Tomkat Roofing", "MCS Group",
            "Certified Building Inspection Services",
            "Live Electrical", "Aizer Insurance Builders",
            "Salt Water Roofing", "Imparta Engineers",
            "AJ Grant",
            "BlueScope", "QBE", "WeatherWatch", "BoM",
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
        "AAMI": "AAI",
        "aami.com.au": "AAI",
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
        "CoverMore": "Cover-More",
        "RCC National Pty Ltd": "RCC National",
        "RCC National Pty": "RCC National",
        "RCC": "RCC National",
        "MCS Group Holdings Pty Ltd": "MCS Group",
        "MCS Group Holdings": "MCS Group",
        "MCS Group Independent National": "MCS Group",
        "mcsgroup": "MCS Group",
        "Certified Building Inspection": "Certified Building Inspection Services",
        "Certified Pest and Building": "Certified Building Inspection Services",
        "Certified Pest & Building": "Certified Building Inspection Services",
        "certifiedbuildinginspection": "Certified Building Inspection Services",
        "www.certifiedbuildinginspection.com.au": "Certified Building Inspection Services",
        "BlueScope Steel": "BlueScope",
        "BlueScope Steel Limited": "BlueScope",
        "Tomkat Roofing Pty Ltd": "Tomkat Roofing",
        "tomkatroofing": "Tomkat Roofing",
        "RACQ Insurance Limited": "RACQ Insurance",
        "Australian Building & Construction Group Pty Ltd": "Australian Building & Construction",
        "Australian Building & Construction Group": "Australian Building & Construction",
        "Australian Building and Construction Group": "Australian Building & Construction",
        "Australian Building and Construction": "Australian Building & Construction",
        "Australian Building & Construction Pty Ltd": "Australian Building & Construction",
        "Clear Engineering Services Australia": "Clear Engineering Services",
        "Clear Engineering Services Australia Pty Ltd": "Clear Engineering Services",
        "Clear Engineering": "Clear Engineering Services",
        "clearengineeringservices": "Clear Engineering Services",
        "Claims Made Easy": "ClaimsCo",
        "CLAIMS MADE EASY": "ClaimsCo",
        "claimsco.com.au": "ClaimsCo",
        "Live Electrical & Air Conditioning": "Live Electrical",
        "Live Electrical and Air Conditioning": "Live Electrical",
        "Live Electrical & air conditioning": "Live Electrical",
        "LIVE ELECTRICAL": "Live Electrical",
        "liveg.com.au": "Live Electrical",
        "www.liveg.com.au": "Live Electrical",
        "Live Services Group": "Live Electrical",
        "Aizer Insurance Builders Pty Ltd": "Aizer Insurance Builders",
        "Aizer Insurance Builders Pty": "Aizer Insurance Builders",
        "Aizer Insurance": "Aizer Insurance Builders",
        "Aizer Group": "Aizer Insurance Builders",
        "Aizer": "Aizer Insurance Builders",
        "Saltwater Roofing": "Salt Water Roofing",
        "SALTWATER ROOFING": "Salt Water Roofing",
        "Salt Water Roofing Pty Ltd": "Salt Water Roofing",
        "Saltwater Roofing Pty Ltd": "Salt Water Roofing",
        "Imparta": "Imparta Engineers",
        "Imparta Engineers Pty Ltd": "Imparta Engineers",
        "impartaengineers": "Imparta Engineers",
        "Melrose Building": "Melrose Building Projects",
        "Melrose Building Projects Pty Ltd": "Melrose Building Projects",
        "Melrose Building Projects Pty": "Melrose Building Projects",
        "Solarez Energy": "Solarez",
        "Solarez Energy Pty Ltd": "Solarez",
        "PV Lab": "PV Lab Australia",
        "PV Lab Pty Ltd": "PV Lab Australia",
        "BMG": "BMG Engineering",
        "BMG Engineering Pty Ltd": "BMG Engineering",
        "Ezy Projects": "Ezy Projects",
        "EZ Projects": "Ezy Projects",
        "Ambrose Construct": "Ambrose Construct Group",
        "Ambrose Construct Group Pty Ltd": "Ambrose Construct Group",
        "Ambrose Construction": "Ambrose Construct Group",
        "Kehoe Myers Pty Ltd": "Kehoe Myers",
        "InTouch Projects": "InTouch Projects",
        "ITP": "InTouch Projects",
        "In Touch Projects": "InTouch Projects",
        "Early Warning Network": "Early Warning Network",
        "EWN": "Early Warning Network",
        "Vero Insurance": "Vero",
        "Vero Insurance Limited": "Vero",
        "Woolworths Insurance": "Woolworths Insurance",
        "RAA Insurance": "RAA",
    },
    "preferred_entities": [
        "ClaimsCo", "Campbell Constructions", "Sedgwick",
        "Morse Building Consultants", "Clear Engineering Services",
        "Australian Building & Construction", "Tomkat Roofing",
        "MCS Group", "Certified Building Inspection Services",
        "BlueScope", "RCC National", "QBE", "RACQ Insurance",
        "Live Electrical", "Aizer Insurance Builders", "Salt Water Roofing",
        "Imparta Engineers", "AJ Grant",
        "AFCA",
        "ACB", "AusCoast", "AusCoast Builders", "RUCA", "Balmoral", "Patcol",
        "Melrose Building Projects",
        "WeatherWatch", "BoM", "COI",
        # Insurers
        "Allianz", "Suncorp", "RACQ", "IAG", "NRMA",
        "Budget Direct", "Youi", "Coles Insurance", "Woolworths Insurance",
        "RAA", "SGIC", "AAMI", "GIO", "Bingle", "Shannons",
        "Vero", "Zurich", "AIG", "Chubb",
        # Solar / Specialist
        "Solarez", "Solarez Energy", "PV Lab", "PV Lab Australia",
        # Builders / Engineers
        "BMG Engineering", "BMG", "Ezy Projects", "EZ Projects",
        "Ambrose", "Ambrose Construct", "Ambrose Construct Group",
        "Kehoe Myers", "InTouch Projects", "ITP",
        # Weather
        "Early Warning Network", "EWN",
        # Internal tokens
        "DOA", "AAF",
    ],
    "preferred_doc_labels": [
        "Site Report", "Photo Schedule", "Assessment Report",
        "Progress Report 1", "Progress Report 2", "Roof Report",
        "Initial Claims Advice", "Claim Lodgement Email",
        "Claim Lodgement Form",
        "Certificate of Insurance", "PDS", "Claims Team FDL", "IDR FDL",
        "Notice of Response", "Notice of Response from QBE",
        "AFCA Submission", "Letter of Engagement", "Building Report",
        "Supplementary Report", "Supplementary Technical Assessment Report",
        "Pre Purchase Inspection Report",
        "Engineering Report", "TB32 Technical Bulletin", "Desktop Report",
        "Final Report",
        "Hail Report", "Solar PV Specialist Report",
        "Quote", "Weather Pack", "Agent Authority Form",
        "Delegation of Authority", "Information Sheet",
        "Timeline",
        "Request for Information", "Written Preliminary Assessment",
        "Variation Report", "Response to AFCA",
        "Engineers Roof Report", "Submission to AFCA"
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
        "Certificate of Insurance": [
            "certificate of insurance", "coi",
            "your insurance", "certificate of currency",
            "policy schedule", "schedule of insurance"
        ],
        "PDS": ["product disclosure statement"],
        "Claims Team FDL": [
            "claim decision", "claims decision",
            "allowing us to review your claim",
            "we have assessed your claim",
            "your claim has been assessed",
            "your claim has been reviewed",
            "we are unable to accept your claim",
            "your policy does not cover",
            "we regret to advise",
            "we have declined",
        ],
        "Information Sheet": [
            "complaint handling", "complaints handling",
            "information sheet", "information brochure",
            "handling your complaint",
        ],
        "IDR FDL": [
            "idr", "final decision letter", "internal dispute resolution",
            "idr response", "final decision",
            "we have reviewed your complaint",
            "complaints handling process",
            "our final decision",
        ],
        "Notice of Response": ["notice of response"],
        "AFCA Submission": [
            "afca submission", "submission to afca",
            "lodgement of a formal complaint",
            "complaint lodgement",
        ],
        "Letter of Engagement": ["letter of engagement", "engagement letter", "engagement"],
        "Building Report": ["building report", "building inspection"],
        "Supplementary Report": ["supplementary report", "supplementary assessment"],
        "Supplementary Technical Assessment Report": [
            "supplementary technical assessment",
            "supplementary technical report"
        ],
        "Engineering Report": [
            "engineering report", "engineering assessment",
            "engineering response", "engineers report",
            "engineers initial visual report", "engineers request for information",
            "engineering services",
        ],
        "Pre Purchase Inspection Report": [
            "pre purchase inspection", "pre-purchase inspection",
            "pre purchase building", "pre-purchase building",
            "pre purchase report", "pre-purchase report",
        ],
        "TB32 Technical Bulletin": ["tb-32", "tb 32", "tb32", "technical bulletin"],
        "Desktop Report": ["desktop report", "desktop assessment", "desktop review"],
        "Final Report": ["final report"],
        "Hail Report": ["hail report", "hail damage", "hail assessment"],
        "Solar PV Specialist Report": [
            "solar pv specialist report", "solar pv specialist",
            "solar pv report", "solar specialist report"
        ],
        "Quote": ["quote", "quotation", "estimate"],
        "Weather Pack": ["weather pack", "weather report", "weather data"],
        "Agent Authority Form": ["authority and access form", "aaf"],
        "Delegation of Authority": ["delegation of authority", "delegation authority"],
        "Timeline": ["timeline", "chronology", "file note", "file notes"],
        "Request for Information": [
            "request for information", "rfi",
            "information request response",
        ],
        "Written Preliminary Assessment": [
            "written preliminary assessment", "preliminary assessment"
        ],
        "Variation Report": [
            "variation report", "variation report & quotation",
            "variation report and quotation", "variation scope of works"
        ],
        "Response to AFCA": [
            "response to afca", "further response",
            "requesting a response to the information provided",
            "response to the information provided"
        ],
        "Engineers Roof Report": [
            "engineers roof report"
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
        "Engineering Report": True,
        "Pre Purchase Inspection Report": True,
        "Claims Team FDL": True,
        "TB32 Technical Bulletin": True,
        "Desktop Report": True,
        "Final Report": True,
        "Hail Report": True,
        "Solar PV Specialist Report": True,
        "Quote": True,
        "IDR FDL": True,
        "Notice of Response": False,
        "Notice of Response from QBE": False,
        "AFCA Submission": False,
        "Letter of Engagement": True,
        "Certificate of Insurance": True,
        "PDS": True,
        "Weather Pack": False,
        "Agent Authority Form": False,
        "Request for Information": True,
        "Written Preliminary Assessment": False,
        "Claim Lodgement Email": False,
        "Claim Lodgement Form": False,
        "Initial Claims Advice": False,
        "Timeline": False,
        "Delegation of Authority": True,
        "Information Sheet": True,
        "Variation Report": True,
        "Response to AFCA": True,
        "Engineers Roof Report": True,
        "Submission to AFCA": True
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
        self._migrate()

    def _migrate(self):
        """Apply setting migrations for new versions.

        When defaults change in ways that must override old saved values
        (e.g. entity_include_rules flipped from False to True), this
        method forces the correct value and persists it.
        """
        changed = False
        saved_version = self._data.get("_settings_version", "0")
        defaults = DEFAULT_SETTINGS

        # Version-specific migrations (one-time rule fixes)
        if saved_version < "1.4.2":
            rules = self._data.get("entity_include_rules", {})
            for key in ["Letter of Engagement", "Request for Information"]:
                if key in rules and not rules[key]:
                    rules[key] = True
                    changed = True

        # Always sync: merge new entries from defaults into saved settings.
        # This runs every version bump so newly added doc types, entities,
        # and aliases are always available without requiring manual resets.
        if saved_version != APP_VERSION:
            # Add new dict keys (doc types, aliases, rules) from defaults
            for section in ["doc_type_keywords", "entity_aliases",
                            "entity_include_rules"]:
                default_section = defaults.get(section, {})
                current_section = self._data.get(section, {})
                for key, value in default_section.items():
                    if key not in current_section:
                        current_section[key] = value
                        changed = True

            # Add new preferred entities that aren't already present
            default_pref = defaults.get("preferred_entities", [])
            current_pref = self._data.get("preferred_entities", [])
            current_lower = [e.lower() for e in current_pref]
            for ent in default_pref:
                if ent.lower() not in current_lower:
                    current_pref.append(ent)
                    changed = True

            # Add new FF entities / keywords that aren't already present
            mapping = self._data.get("who_mapping", {})
            default_mapping = defaults.get("who_mapping", {})
            for list_key in ["ff_entities", "ff_keywords"]:
                current_list = mapping.get(list_key, [])
                default_list = default_mapping.get(list_key, [])
                current_lower = [e.lower() for e in current_list]
                for item in default_list:
                    if item.lower() not in current_lower:
                        current_list.append(item)
                        changed = True

            changed = True

        if changed:
            self._data["_settings_version"] = APP_VERSION
            self.save()

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
