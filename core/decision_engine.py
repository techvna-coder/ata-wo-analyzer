"""
Decision Engine - Tam-đối-soát logic for ATA determination
"""
from typing import Dict, Optional


class DecisionEngine:
    """
    Three-way reconciliation decision engine
    
    E0: ATA04_Entered (mechanic input)
    E1: ATA04_From_Cited (from TSM/FIM/AMM reference)
    E2: ATA04_Derived (from Catalog/RAG inference)
    """
    
    def __init__(self, confidence_threshold: float = 0.75):
        """
        Initialize decision engine
        
        Args:
            confidence_threshold: Minimum confidence for non-REVIEW decisions
        """
        self.confidence_threshold = confidence_threshold
    
    def make_decision(
        self,
        e0: Optional[str],
        e1: Optional[str],
        e1_valid: Optional[bool],
        e2: Optional[str],
        e2_score: Optional[float]
    ) -> Dict:
        """
        Make tri-lateral decision
        
        Args:
            e0: ATA entered by mechanic
            e1: ATA from cited manual
            e1_valid: Whether E1 reference exists in registry
            e2: ATA derived from catalog/RAG
            e2_score: Confidence score of E2 (0-1)
            
        Returns:
            Dict with keys: decision, ata04_final, confidence, reason
        """
        # Normalize ATAs
        e0 = self._normalize(e0)
        e1 = self._normalize(e1) if e1_valid else None
        e2 = self._normalize(e2)
        
        # Case 1: All three agree (E0 = E1 = E2, E1 valid)
        if e0 and e1 and e2 and e0 == e1 == e2:
            return {
                'decision': 'CONFIRM',
                'ata04_final': e0,
                'confidence': 0.97,
                'reason': 'All sources agree (E0=E1=E2)'
            }
        
        # Case 2: E1 and E2 agree, differ from E0 (E1 valid)
        if e1 and e2 and e1 == e2 and e0 != e1:
            return {
                'decision': 'CORRECT',
                'ata04_final': e1,
                'confidence': 0.95,
                'reason': f'Citation and derived agree on {e1}, differs from entered {e0}'
            }
        
        # Case 3: Only E2 matches E0 (no E1 or E1 invalid)
        if e0 and e2 and e0 == e2 and not e1:
            confidence = self._calculate_e2_confidence(e2_score)
            return {
                'decision': 'CONFIRM',
                'ata04_final': e0,
                'confidence': confidence,
                'reason': f'Catalog confirms entered ATA (score: {e2_score:.2f})'
            }
        
        # Case 4: Only E1 valid (no E2 or low score)
        if e1 and (not e2 or (e2_score and e2_score < 0.3)):
            if e0 == e1:
                return {
                    'decision': 'CONFIRM',
                    'ata04_final': e0,
                    'confidence': 0.92,
                    'reason': 'Valid citation confirms entered ATA'
                }
            else:
                return {
                    'decision': 'CORRECT',
                    'ata04_final': e1,
                    'confidence': 0.90,
                    'reason': f'Valid citation {e1} differs from entered {e0}'
                }
        
        # Case 5: Only E2 with good score (no E1)
        if e2 and e2_score and e2_score >= 0.3 and not e1:
            confidence = self._calculate_e2_confidence(e2_score)
            
            if e0 == e2:
                return {
                    'decision': 'CONFIRM',
                    'ata04_final': e0,
                    'confidence': confidence,
                    'reason': f'Catalog confirms (score: {e2_score:.2f})'
                }
            elif confidence >= self.confidence_threshold:
                return {
                    'decision': 'CORRECT',
                    'ata04_final': e2,
                    'confidence': confidence,
                    'reason': f'Catalog suggests {e2} (score: {e2_score:.2f})'
                }
            else:
                return {
                    'decision': 'REVIEW',
                    'ata04_final': e0,
                    'confidence': confidence,
                    'reason': f'Low catalog confidence (score: {e2_score:.2f})'
                }
        
        # Case 6: E1 and E2 disagree
        if e1 and e2 and e1 != e2:
            # Prefer E1 (cited reference) over E2 if E1 is valid
            if e0 == e1:
                return {
                    'decision': 'CONFIRM',
                    'ata04_final': e0,
                    'confidence': 0.88,
                    'reason': f'Citation confirms E0={e1}, catalog suggests {e2}'
                }
            elif e0 == e2:
                e2_conf = self._calculate_e2_confidence(e2_score)
                if e2_conf >= 0.85:
                    return {
                        'decision': 'CONFIRM',
                        'ata04_final': e0,
                        'confidence': 0.85,
                        'reason': f'Strong catalog confirms E0={e2}, citation suggests {e1}'
                    }
                else:
                    return {
                        'decision': 'REVIEW',
                        'ata04_final': e0,
                        'confidence': 0.70,
                        'reason': f'Conflict: citation={e1}, catalog={e2}'
                    }
            else:
                # E0 differs from both E1 and E2
                return {
                    'decision': 'REVIEW',
                    'ata04_final': e0,
                    'confidence': 0.65,
                    'reason': f'All differ: E0={e0}, citation={e1}, catalog={e2}'
                }
        
        # Case 7: Only E0 available
        if e0 and not e1 and not e2:
            return {
                'decision': 'REVIEW',
                'ata04_final': e0,
                'confidence': 0.65,
                'reason': 'No citation or catalog match found'
            }
        
        # Case 8: No ATA available at all
        return {
            'decision': 'REVIEW',
            'ata04_final': e0 if e0 else None,
            'confidence': 0.50,
            'reason': 'Insufficient data for decision'
        }
    
    def _normalize(self, ata: Optional[str]) -> Optional[str]:
        """Normalize ATA to AA-BB format"""
        if not ata:
            return None
        
        # Remove spaces and extra dashes
        ata_clean = str(ata).strip().replace(' ', '')
        
        # Extract digits
        digits = ''.join(c for c in ata_clean if c.isdigit())
        
        if len(digits) >= 4:
            return f"{digits[:2]}-{digits[2:4]}"
        
        return None
    
    def _calculate_e2_confidence(self, score: Optional[float]) -> float:
        """
        Calculate confidence from E2 score
        
        Score ranges:
        - 0.8-1.0 -> confidence 0.88
        - 0.6-0.8 -> confidence 0.83
        - 0.4-0.6 -> confidence 0.78
        - 0.2-0.4 -> confidence 0.73
        - 0.0-0.2 -> confidence 0.68
        """
        if not score:
            return 0.68
        
        if score >= 0.8:
            return 0.88
        elif score >= 0.6:
            return 0.83
        elif score >= 0.4:
            return 0.78
        elif score >= 0.2:
            return 0.73
        else:
            return 0.68
    
    def validate_decision(self, decision_result: Dict) -> bool:
        """
        Validate decision result meets quality thresholds
        
        Args:
            decision_result: Output from make_decision()
            
        Returns:
            True if decision is valid
        """
        required_keys = ['decision', 'ata04_final', 'confidence', 'reason']
        
        # Check all keys present
        if not all(key in decision_result for key in required_keys):
            return False
        
        # Check decision is valid
        if decision_result['decision'] not in ['CONFIRM', 'CORRECT', 'REVIEW', 'NON_DEFECT']:
            return False
        
        # Check confidence in valid range
        conf = decision_result['confidence']
        if conf is None or conf < 0 or conf > 1:
            return False
        
        return True
