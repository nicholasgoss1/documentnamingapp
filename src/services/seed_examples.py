"""
Seed examples for Groq few-shot classification.
Updated periodically by harvest_corrections.py from staff corrections.
"""

SEED_EXAMPLES = [
    {"filename": "FF - 11.12.2025 - Allianz - IDR FDL.pdf", "result": {"who": "FF", "entity": "Allianz", "date": "11.12.2025", "what": "IDR FDL"}},
    {"filename": "Complainant - 12.11.2025 - Solarez - Solar testing report.pdf", "result": {"who": "Complainant", "entity": "Solarez", "date": "12.11.2025", "what": "Solar Testing Report"}},
    {"filename": "AFCA - 16.03.2026 - AFCA - Written Preliminary Assessment.pdf", "result": {"who": "AFCA", "entity": "AFCA", "date": "16.03.2026", "what": "Written Preliminary Assessment"}},
    {"filename": "Complainant - 15.08.2025 - AusCoast - Variation Report.pdf", "result": {"who": "Complainant", "entity": "AusCoast Builders", "date": "15.08.2025", "what": "Variation Report"}},
    {"filename": "FF - 06.05.2025 - Ezy Projects - Roof Report.pdf", "result": {"who": "FF", "entity": "Ezy Projects", "date": "06.05.2025", "what": "Roof Report"}},
    {"filename": "TEST - 27.03.2026 - Test - Entity.pdf", "result": {"who": "FF", "entity": "TestCo", "date": "27.03.2026", "what": "Test"}},
]
