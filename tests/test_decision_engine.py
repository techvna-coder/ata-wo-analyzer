"""
Unit tests for Decision Engine
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.decision_engine import DecisionEngine


class TestDecisionEngine(unittest.TestCase):
    """Test cases for DecisionEngine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.engine = DecisionEngine(confidence_threshold=0.75)
    
    def test_all_agree_valid_e1(self):
        """Test when E0=E1=E2 with valid E1"""
        result = self.engine.make_decision(
            e0='21-26',
            e1='21-26',
            e1_valid=True,
            e2='21-26',
            e2_score=0.85
        )
        
        self.assertEqual(result['decision'], 'CONFIRM')
        self.assertEqual(result['ata04_final'], '21-26')
        self.assertGreaterEqual(result['confidence'], 0.95)
    
    def test_e1_e2_agree_differ_from_e0(self):
        """Test when E1=E2 but different from E0"""
        result = self.engine.make_decision(
            e0='21-26',
            e1='21-27',
            e1_valid=True,
            e2='21-27',
            e2_score=0.80
        )
        
        self.assertEqual(result['decision'], 'CORRECT')
        self.assertEqual(result['ata04_final'], '21-27')
        self.assertGreaterEqual(result['confidence'], 0.90)
    
    def test_only_e2_matches_e0(self):
        """Test when only E2 matches E0"""
        result = self.engine.make_decision(
            e0='21-26',
            e1=None,
            e1_valid=False,
            e2='21-26',
            e2_score=0.75
        )
        
        self.assertEqual(result['decision'], 'CONFIRM')
        self.assertEqual(result['ata04_final'], '21-26')
    
    def test_only_e1_valid(self):
        """Test when only E1 is valid"""
        result = self.engine.make_decision(
            e0='21-26',
            e1='21-26',
            e1_valid=True,
            e2=None,
            e2_score=None
        )
        
        self.assertEqual(result['decision'], 'CONFIRM')
        self.assertEqual(result['ata04_final'], '21-26')
        self.assertGreaterEqual(result['confidence'], 0.90)
    
    def test_e1_differs_from_e0(self):
        """Test when valid E1 differs from E0"""
        result = self.engine.make_decision(
            e0='21-26',
            e1='21-27',
            e1_valid=True,
            e2=None,
            e2_score=0.20
        )
        
        self.assertEqual(result['decision'], 'CORRECT')
        self.assertEqual(result['ata04_final'], '21-27')
    
    def test_only_e2_high_score(self):
        """Test when only E2 with high score"""
        result = self.engine.make_decision(
            e0='21-26',
            e1=None,
            e1_valid=False,
            e2='21-27',
            e2_score=0.85
        )
        
        self.assertEqual(result['decision'], 'CORRECT')
        self.assertEqual(result['ata04_final'], '21-27')
    
    def test_only_e2_low_score(self):
        """Test when only E2 with low score"""
        result = self.engine.make_decision(
            e0='21-26',
            e1=None,
            e1_valid=False,
            e2='21-27',
            e2_score=0.30
        )
        
        self.assertEqual(result['decision'], 'REVIEW')
    
    def test_e1_e2_conflict_e0_matches_e1(self):
        """Test conflict when E0 matches E1"""
        result = self.engine.make_decision(
            e0='21-26',
            e1='21-26',
            e1_valid=True,
            e2='21-27',
            e2_score=0.70
        )
        
        self.assertEqual(result['decision'], 'CONFIRM')
        self.assertEqual(result['ata04_final'], '21-26')
    
    def test_e1_e2_conflict_e0_matches_e2(self):
        """Test conflict when E0 matches E2"""
        result = self.engine.make_decision(
            e0='21-27',
            e1='21-26',
            e1_valid=True,
            e2='21-27',
            e2_score=0.90
        )
        
        self.assertEqual(result['decision'], 'CONFIRM')
        self.assertEqual(result['ata04_final'], '21-27')
    
    def test_all_differ(self):
        """Test when all three differ"""
        result = self.engine.make_decision(
            e0='21-26',
            e1='21-27',
            e1_valid=True,
            e2='21-28',
            e2_score=0.80
        )
        
        self.assertEqual(result['decision'], 'REVIEW')
        self.assertEqual(result['ata04_final'], '21-26')  # Defaults to E0
    
    def test_only_e0(self):
        """Test when only E0 available"""
        result = self.engine.make_decision(
            e0='21-26',
            e1=None,
            e1_valid=False,
            e2=None,
            e2_score=None
        )
        
        self.assertEqual(result['decision'], 'REVIEW')
        self.assertEqual(result['ata04_final'], '21-26')
        self.assertLessEqual(result['confidence'], 0.70)
    
    def test_no_ata_available(self):
        """Test when no ATA available"""
        result = self.engine.make_decision(
            e0=None,
            e1=None,
            e1_valid=False,
            e2=None,
            e2_score=None
        )
        
        self.assertEqual(result['decision'], 'REVIEW')
        self.assertIsNone(result['ata04_final'])
        self.assertLessEqual(result['confidence'], 0.60)
    
    def test_normalize_ata(self):
        """Test ATA normalization"""
        # With dashes
        result = self.engine._normalize('21-26')
        self.assertEqual(result, '21-26')
        
        # Without dashes
        result = self.engine._normalize('2126')
        self.assertEqual(result, '21-26')
        
        # With extra parts
        result = self.engine._normalize('21-26-00')
        self.assertEqual(result, '21-26')
        
        # Invalid
        result = self.engine._normalize('ABC')
        self.assertIsNone(result)
    
    def test_calculate_e2_confidence(self):
        """Test E2 confidence calculation"""
        # High score
        conf = self.engine._calculate_e2_confidence(0.85)
        self.assertGreaterEqual(conf, 0.85)
        
        # Medium score
        conf = self.engine._calculate_e2_confidence(0.55)
        self.assertGreaterEqual(conf, 0.75)
        
        # Low score
        conf = self.engine._calculate_e2_confidence(0.25)
        self.assertGreaterEqual(conf, 0.70)
    
    def test_validate_decision(self):
        """Test decision validation"""
        # Valid decision
        valid_decision = {
            'decision': 'CONFIRM',
            'ata04_final': '21-26',
            'confidence': 0.95,
            'reason': 'Test reason'
        }
        self.assertTrue(self.engine.validate_decision(valid_decision))
        
        # Missing key
        invalid_decision = {
            'decision': 'CONFIRM',
            'ata04_final': '21-26'
        }
        self.assertFalse(self.engine.validate_decision(invalid_decision))
        
        # Invalid decision type
        invalid_decision = {
            'decision': 'INVALID',
            'ata04_final': '21-26',
            'confidence': 0.95,
            'reason': 'Test'
        }
        self.assertFalse(self.engine.validate_decision(invalid_decision))
        
        # Invalid confidence
        invalid_decision = {
            'decision': 'CONFIRM',
            'ata04_final': '21-26',
            'confidence': 1.5,
            'reason': 'Test'
        }
        self.assertFalse(self.engine.validate_decision(invalid_decision))


if __name__ == '__main__':
    unittest.main()
