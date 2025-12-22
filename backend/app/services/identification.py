import re

SYSTEM_PATTERNS = {
    "Salesforce": [r"force\.com", r"salesforce"],
    "SAP": [r"sap", r"fiori"],
    "Jira": [r"jira", r"atlassian"],
    "Excel": [r"excel", r"spreadsheet"],
    "Unknown": []
}

def identify_system(ocr_text: str, window_title: str) -> str:
    """
    Identify the enterprise system based on text signals.
    """
    combined_text = (ocr_text + " " + window_title).lower()
    
    for system, patterns in SYSTEM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined_text):
                return system
                
    return "Generic Web Portal"
