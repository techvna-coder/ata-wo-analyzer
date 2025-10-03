"""
Unit tests for Non-Defect Filter
"""
import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.non_defect_filter import NonDefectFilter


class TestNonDefectFilter(unittest.TestCase):
    """Test cases for NonDefectFilter"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.filter = NonDefectFilter()
    
    def test_routine_cleaning(self):
        """Test detection of routine cleaning"""
        description = "Cabin cleaning required"
        action = "Performed general cleaning"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertFalse(is_defect)
        self.assertIn("clean", reason.lower())
    
    def test_scheduled_maintenance(self):
        """Test detection of scheduled maintenance"""
        description = "Scheduled inspection due"
        action = "Completed scheduled maintenance check"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertFalse(is_defect)
        self.assertIn("scheduled", reason.lower())
    
    def test_nff(self):
        """Test detection of No Fault Found"""
        description = "Warning light illuminated"
        action = "Inspected system, NFF"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertFalse(is_defect)
        self.assertIn("nff", reason.lower())
    
    def test_technical_defect_with_failure(self):
        """Test that failures override non-defect patterns"""
        description = "Cleaning system failure"
        action = "Replaced faulty component"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertTrue(is_defect)
        self.assertIn("failure", reason.lower())
    
    def test_ecam_warning(self):
        """Test ECAM warnings are treated as defects"""
        description = "ECAM HYD SYS 1 LO LEVEL"
        action = "Replenished hydraulic fluid per TSM 29-11-00"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertTrue(is_defect)
        self.assertIn("ecam", reason.lower())
    
    def test_leak_detection(self):
        """Test leak detection"""
        description = "Oil leak observed from engine"
        action = "Tightened fitting, leak stopped"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertTrue(is_defect)
        self.assertIn("leak", reason.lower())
    
    def test_lubrication_without_defect(self):
        """Test routine lubrication"""
        description = "Routine lubrication required"
        action = "Applied lubrication to hinges"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertFalse(is_defect)
    
    def test_default_is_defect(self):
        """Test that ambiguous cases default to defect"""
        description = "Unusual noise from landing gear"
        action = "Inspected landing gear system"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertTrue(is_defect)
    
    def test_empty_text(self):
        """Test handling of empty text"""
        is_defect, reason = self.filter.is_technical_defect("", "")
        
        self.assertTrue(is_defect)  # Default to defect
    
    def test_software_load(self):
        """Test software load detection"""
        description = "Software update required"
        action = "Software load completed per AMM"
        
        is_defect, reason = self.filter.is_technical_defect(description, action)
        
        self.assertFalse(is_defect)
        self.assertIn("software", reason.lower())


if __name__ == '__main__':
    unittest.main()
