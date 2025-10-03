"""
Unit tests for Citation Extractor
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.citation_extractor import CitationExtractor


class TestCitationExtractor(unittest.TestCase):
    """Test cases for CitationExtractor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.extractor = CitationExtractor()
    
    def test_extract_tsm_with_spaces(self):
        """Test extraction of TSM with spaces"""
        text = "Performed troubleshooting per TSM 21-26-00"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]['manual_type'], 'TSM')
        self.assertEqual(citations[0]['ata04'], '21-26')
        self.assertEqual(citations[0]['task_number'], '21-26-00')
    
    def test_extract_tsm_without_spaces(self):
        """Test extraction of TSM without spaces"""
        text = "Ref TSM21-26-00"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]['ata04'], '21-26')
    
    def test_extract_tsm_compact(self):
        """Test extraction of compact format"""
        text = "Per TSM212600"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]['ata04'], '21-26')
    
    def test_extract_fim_with_subsections(self):
        """Test extraction of FIM with subsections"""
        text = "Performed FIM 32-47-00-860-801"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]['manual_type'], 'FIM')
        self.assertEqual(citations[0]['ata04'], '32-47')
        self.assertEqual(citations[0]['subsection1'], '860')
        self.assertEqual(citations[0]['subsection2'], '801')
    
    def test_extract_amm(self):
        """Test extraction of AMM"""
        text = "Replaced component per AMM 24-11-00"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]['manual_type'], 'AMM')
        self.assertEqual(citations[0]['ata04'], '24-11')
    
    def test_extract_standalone_ata(self):
        """Test extraction of standalone ATA"""
        text = "Performed task 21-26-00"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]['ata04'], '21-26')
    
    def test_extract_multiple_citations(self):
        """Test extraction of multiple citations"""
        text = "Per TSM 21-26-00 and FIM 32-47-00"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0]['ata04'], '21-26')
        self.assertEqual(citations[1]['ata04'], '32-47')
    
    def test_no_citations(self):
        """Test text with no citations"""
        text = "Performed general inspection"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 0)
    
    def test_normalize_task_number(self):
        """Test task number normalization"""
        # With dashes
        result = self.extractor.normalize_task_number("21-26-00")
        self.assertEqual(result, "21-26-00")
        
        # Without dashes
        result = self.extractor.normalize_task_number("212600")
        self.assertEqual(result, "21-26-00")
        
        # With subsections
        result = self.extractor.normalize_task_number("21-26-00-860-801")
        self.assertEqual(result, "21-26-00-860-801")
    
    def test_extract_ata04_quick(self):
        """Test quick ATA04 extraction"""
        text = "Per TSM 21-26-00"
        
        ata04 = self.extractor.extract_ata04(text)
        
        self.assertEqual(ata04, '21-26')
    
    def test_extract_with_task_keyword(self):
        """Test extraction with Task keyword"""
        text = "Completed task: 21-26-00"
        
        citations = self.extractor.extract_citations(text)
        
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]['ata04'], '21-26')


if __name__ == '__main__':
    unittest.main()
