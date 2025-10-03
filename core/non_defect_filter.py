"""
Non-Defect Filter - Identifies non-technical work orders
"""
import re
from typing import Tuple


class NonDefectFilter:
    """Filter to identify non-technical defect work orders"""
    
    # Patterns that indicate non-defect (routine maintenance)
    NON_DEFECT_PATTERNS = [
        r'\bclean(?:ing|ed)?\b',
        r'\blubrication\b',
        r'\bservicing\b',
        r'\boil\s+replenish(?:ment|ed)?\b',
        r'\bfirst\s+aid\s+kit\b',
        r'\btyre\s+wear\b',
        r'\btire\s+wear\b',
        r'\bscheduled\s+(?:maintenance|inspection|check)\b',
        r'\broutine\s+(?:maintenance|inspection|check)\b',
        r'\bsoftware\s+load(?:ing|ed)?\b',
        r'\bsoftware\s+update\b',
        r'\bnff\b',  # No Fault Found
        r'\bno\s+fault\s+found\b',
        r'\boperational\s+check\b',
        r'\bfunctional\s+(?:test|check)\b',
        r'\bvisual\s+inspection\b',
        r'\bgeneral\s+inspection\b',
        r'\bperiodic\s+(?:check|inspection)\b',
        r'\breplacement\s+as\s+per\s+schedule\b',
        r'\blife\s+limited\s+part\b',
        r'\bllp\s+replacement\b',
        r'\bcabin\s+(?:cleaning|refurbishment)\b',
        r'\bcosmetic\s+repair\b',
        r'\bseat\s+(?:cleaning|cover)\b',
        r'\bcarpet\s+(?:cleaning|replacement)\b',
        r'\blavatory\s+(?:cleaning|servicing)\b',
        r'\bgalley\s+(?:cleaning|servicing)\b',
        r'\bpassenger\s+(?:seat|entertainment)\s+(?:cleaning|adjustment)\b',
    ]
    
    # Patterns that indicate technical defect (override non-defect)
    DEFECT_OVERRIDE_PATTERNS = [
        r'\bfailure\b',
        r'\bfailed\b',
        r'\bfault\b',
        r'\bfaulty\b',
        r'\bleak(?:ing|age)?\b',
        r'\boverheat(?:ing|ed)?\b',
        r'\bvibration\b',
        r'\becam\b',
        r'\beicas\b',
        r'\bcas\b',  # Crew Alerting System
        r'\bwarning\b',
        r'\bsmoke\b',
        r'\binoperative\b',
        r'\binop\b',
        r'\bunserviceable\b',
        r'\bu/s\b',
        r'\bdefect(?:ive)?\b',
        r'\bdamage(?:d)?\b',
        r'\bbroken\b',
        r'\bcrack(?:ed)?\b',
        r'\bcorrosion\b',
        r'\berror\b',
        r'\babnormal\b',
        r'\bmalfunction\b',
        r'\bnot\s+working\b',
        r'\bout\s+of\s+tolerance\b',
        r'\bexceed(?:ed|s)?\s+limit\b',
        r'\bhigh\s+(?:temperature|pressure|vibration)\b',
        r'\blow\s+(?:pressure|oil|fuel)\b',
        r'\bcontamination\b',
        r'\bwear\s+(?:beyond|exceeds)\b',
        r'\bnoise\b',
        r'\bunusual\s+(?:noise|sound|smell)\b',
    ]
    
    def __init__(self):
        """Initialize filter with compiled patterns"""
        self.non_defect_regex = re.compile(
            '|'.join(self.NON_DEFECT_PATTERNS),
            re.IGNORECASE
        )
        
        self.defect_override_regex = re.compile(
            '|'.join(self.DEFECT_OVERRIDE_PATTERNS),
            re.IGNORECASE
        )
    
    def is_technical_defect(
        self,
        description: str,
        action: str = ''
    ) -> Tuple[bool, str]:
        """
        Determine if WO is a technical defect
        
        Args:
            description: Defect description text
            action: Rectification action text
            
        Returns:
            Tuple of (is_defect: bool, reason: str)
        """
        # Combine texts for analysis
        combined_text = f"{description} {action}".lower()
        
        # Check for defect override patterns first (higher priority)
        if self.defect_override_regex.search(combined_text):
            match = self.defect_override_regex.search(combined_text)
            return True, f"Defect indicator found: '{match.group()}'"
        
        # Check for non-defect patterns
        if self.non_defect_regex.search(combined_text):
            match = self.non_defect_regex.search(combined_text)
            return False, f"Routine maintenance: '{match.group()}'"
        
        # Default: assume technical defect if no pattern matched
        return True, "Default: no non-defect pattern found"
    
    def get_non_defect_matches(self, text: str) -> list:
        """Get all non-defect pattern matches in text"""
        return self.non_defect_regex.findall(text.lower())
    
    def get_defect_matches(self, text: str) -> list:
        """Get all defect indicator matches in text"""
        return self.defect_override_regex.findall(text.lower())
