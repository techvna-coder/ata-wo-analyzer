"""
Citation Extractor - Extracts TSM/FIM/AMM references from text
"""
import re
from typing import List, Dict, Optional


class CitationExtractor:
    """Extract manual references (TSM/FIM/AMM) from rectification text"""
    
    # Patterns for different manual formats
    PATTERNS = [
        # TSM 21-26-00, FIM 32-47-00-860-801, AMM 24-11-00
        r'\b(TSM|FIM|AMM)\s*(\d{2})-(\d{2})-(\d{2})(?:-(\d{3}))?(?:-(\d{3}))?\b',
        
        # TSM21-26-00, TSM2126, TSM212600
        r'\b(TSM|FIM|AMM)(\d{2})-?(\d{2})-?(\d{2})(?:-?(\d{3}))?(?:-?(\d{3}))?\b',
        
        # Standalone: 21-26-00, 212600
        r'\b(\d{2})-(\d{2})-(\d{2})(?:-(\d{3}))?(?:-(\d{3}))?\b',
        
        # With "Task" or "Ref"
        r'\b(?:task|ref|reference)\s*:?\s*(TSM|FIM|AMM)?\s*(\d{2})-?(\d{2})-?(\d{2})\b',
    ]
    
    # Manual type keywords
    MANUAL_TYPES = {
        'TSM': 'TSM',  # Trouble Shooting Manual
        'FIM': 'FIM',  # Fault Isolation Manual
        'AMM': 'AMM',  # Aircraft Maintenance Manual
        'TASK': 'AMM',  # Usually refers to AMM
        'REF': 'TSM',   # Usually TSM for troubleshooting
    }
    
    def __init__(self):
        """Initialize extractor with compiled patterns"""
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.PATTERNS
        ]
    
    def extract_citations(self, text: str) -> List[Dict]:
        """
        Extract all manual citations from text
        
        Args:
            text: Text to extract from (usually rectification action)
            
        Returns:
            List of dicts with keys: manual_type, task_number, ata04, chapter, section, subject
        """
        if not text:
            return []
        
        citations = []
        seen = set()  # Avoid duplicates
        
        for pattern in self.compiled_patterns:
            for match in pattern.finditer(text):
                citation = self._parse_match(match)
                if citation:
                    # Create unique key
                    key = f"{citation['manual_type']}-{citation['task_number']}"
                    if key not in seen:
                        citations.append(citation)
                        seen.add(key)
        
        return citations
    
    def _parse_match(self, match: re.Match) -> Optional[Dict]:
        """Parse regex match into citation dict"""
        groups = match.groups()
        
        # Determine manual type
        manual_type = None
        chapter = None
        section = None
        subject = None
        subsection1 = None
        subsection2 = None
        
        # Try to extract manual type from first group
        if groups[0] and groups[0].upper() in self.MANUAL_TYPES:
            manual_type = self.MANUAL_TYPES[groups[0].upper()]
            start_idx = 1
        else:
            # No explicit manual type, try to infer
            manual_type = 'TSM'  # Default assumption
            start_idx = 0 if groups[0] and groups[0].isdigit() else 1
        
        # Extract chapter-section-subject
        try:
            # Find numeric groups
            numeric_groups = [g for g in groups if g and g.isdigit()]
            
            if len(numeric_groups) >= 2:
                chapter = numeric_groups[0]
                section = numeric_groups[1]
                
                if len(numeric_groups) >= 3:
                    subject = numeric_groups[2]
                else:
                    subject = '00'
                
                # Optional subsections
                if len(numeric_groups) >= 4:
                    subsection1 = numeric_groups[3]
                if len(numeric_groups) >= 5:
                    subsection2 = numeric_groups[4]
        except (IndexError, ValueError):
            return None
        
        if not chapter or not section:
            return None
        
        # Build task number
        task_parts = [chapter, section, subject]
        if subsection1:
            task_parts.append(subsection1)
        if subsection2:
            task_parts.append(subsection2)
        
        task_number = '-'.join(task_parts)
        
        # ATA04 is chapter-section
        ata04 = f"{chapter}-{section}"
        
        return {
            'manual_type': manual_type,
            'task_number': task_number,
            'ata04': ata04,
            'chapter': chapter,
            'section': section,
            'subject': subject,
            'subsection1': subsection1,
            'subsection2': subsection2,
            'raw_match': match.group()
        }
    
    def normalize_task_number(self, task: str) -> str:
        """
        Normalize task number to standard format AA-BB-CC-DDD-EEE
        
        Args:
            task: Task number in any format
            
        Returns:
            Normalized task number
        """
        # Remove all non-numeric characters except dashes
        clean = re.sub(r'[^\d-]', '', task)
        
        # Split by dash or by position
        if '-' in clean:
            parts = clean.split('-')
        else:
            # Split into 2-2-2-3-3 pattern
            parts = []
            if len(clean) >= 2:
                parts.append(clean[0:2])
            if len(clean) >= 4:
                parts.append(clean[2:4])
            if len(clean) >= 6:
                parts.append(clean[4:6])
            if len(clean) >= 9:
                parts.append(clean[6:9])
            if len(clean) >= 12:
                parts.append(clean[9:12])
        
        # Ensure at least AA-BB-CC format
        while len(parts) < 3:
            parts.append('00')
        
        return '-'.join(parts[:5])  # Max 5 parts
    
    def extract_ata04(self, text: str) -> Optional[str]:
        """
        Quick extraction of ATA04 (AA-BB) from text
        
        Args:
            text: Text containing ATA reference
            
        Returns:
            ATA04 string or None
        """
        citations = self.extract_citations(text)
        if citations:
            return citations[0]['ata04']
        return None
