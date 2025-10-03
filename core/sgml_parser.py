"""
SGML Parser - Parse SGML/XML aviation manuals
"""
import re
from typing import Dict, List, Optional
from pathlib import Path
from bs4 import BeautifulSoup, Tag
import logging

logger = logging.getLogger(__name__)


class SGMLParser:
    """
    Parse SGML/XML files from aviation manuals (TSM/FIM/AMM)
    Supports both ATA iSpec 2200 and S1000D formats
    """
    
    def __init__(self):
        """Initialize parser"""
        self.current_ata = None
        self.current_manual_type = None
    
    def parse_file(self, file_path: str) -> Dict:
        """
        Parse single SGML/XML file
        
        Args:
            file_path: Path to SGML file
            
        Returns:
            Dict with parsed content
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return self.parse_content(content, Path(file_path).name)
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return None
    
    def parse_content(self, content: str, filename: str = '') -> Dict:
        """
        Parse SGML/XML content
        
        Args:
            content: SGML/XML content string
            filename: Original filename for reference
            
        Returns:
            Dict with structured data
        """
        try:
            soup = BeautifulSoup(content, 'lxml-xml')
            
            # Detect format (S1000D vs iSpec)
            is_s1000d = soup.find('dmodule') is not None
            
            if is_s1000d:
                return self._parse_s1000d(soup, filename)
            else:
                return self._parse_ispec(soup, filename)
                
        except Exception as e:
            logger.error(f"Error parsing content: {e}")
            return None
    
    def _parse_s1000d(self, soup: BeautifulSoup, filename: str) -> Dict:
        """Parse S1000D format"""
        result = {
            'format': 'S1000D',
            'filename': filename,
            'ata04': None,
            'title': '',
            'manual_type': None,
            'task_number': '',
            'chunks': []
        }
        
        # Extract DMC (Data Module Code)
        dmc = soup.find('dmCode') or soup.find('dmc')
        if dmc:
            result['ata04'] = self._extract_ata_from_dmc(dmc)
            result['task_number'] = self._extract_task_from_dmc(dmc)
        
        # Extract title
        title = soup.find('dmTitle') or soup.find('title')
        if title:
            tech_name = title.find('techName')
            info_name = title.find('infoName')
            if tech_name:
                result['title'] = tech_name.get_text(strip=True)
            elif info_name:
                result['title'] = info_name.get_text(strip=True)
            else:
                result['title'] = title.get_text(strip=True)
        
        # Extract content chunks
        content = soup.find('content') or soup.find('dmodule')
        if content:
            result['chunks'] = self._extract_chunks_s1000d(content)
        
        return result
    
    def _parse_ispec(self, soup: BeautifulSoup, filename: str) -> Dict:
        """Parse ATA iSpec 2200 format"""
        result = {
            'format': 'iSpec2200',
            'filename': filename,
            'ata04': None,
            'title': '',
            'manual_type': None,
            'task_number': '',
            'chunks': []
        }
        
        # Try to extract ATA from filename
        result['ata04'] = self._extract_ata_from_filename(filename)
        
        # Extract title
        title = soup.find('title')
        if title:
            result['title'] = title.get_text(strip=True)
        
        # Extract task number
        task = soup.find('task') or soup.find('taskNumber')
        if task:
            result['task_number'] = task.get_text(strip=True)
        
        # Extract content chunks
        result['chunks'] = self._extract_chunks_ispec(soup)
        
        return result
    
    def _extract_ata_from_dmc(self, dmc: Tag) -> Optional[str]:
        """Extract ATA04 from DMC tag"""
        try:
            # S1000D structure
            sys_code = dmc.find('systemCode')
            subsys_code = dmc.find('subSystemCode')
            
            if sys_code and subsys_code:
                sys = sys_code.get_text(strip=True).zfill(2)
                subsys = subsys_code.get_text(strip=True).zfill(2)
                return f"{sys}-{subsys}"
            
            # Alternative: modelIdentCode attributes
            if dmc.has_attr('systemCode') and dmc.has_attr('subSystemCode'):
                sys = dmc['systemCode'].zfill(2)
                subsys = dmc['subSystemCode'].zfill(2)
                return f"{sys}-{subsys}"
                
        except Exception as e:
            logger.debug(f"Could not extract ATA from DMC: {e}")
        
        return None
    
    def _extract_task_from_dmc(self, dmc: Tag) -> str:
        """Extract full task number from DMC"""
        try:
            parts = []
            
            for attr in ['systemCode', 'subSystemCode', 'subSubSystemCode', 
                        'assyCode', 'disassyCode', 'disassyCodeVariant']:
                elem = dmc.find(attr)
                if elem:
                    parts.append(elem.get_text(strip=True).zfill(2 if len(parts) < 3 else 3))
                elif dmc.has_attr(attr):
                    parts.append(dmc[attr].zfill(2 if len(parts) < 3 else 3))
            
            return '-'.join(parts) if parts else ''
            
        except Exception as e:
            logger.debug(f"Could not extract task from DMC: {e}")
            return ''
    
    def _extract_ata_from_filename(self, filename: str) -> Optional[str]:
        """Extract ATA04 from filename"""
        # Pattern: ...21-26... or ...2126... or ...21_26...
        patterns = [
            r'(\d{2})[_-](\d{2})',
            r'[^\d](\d{2})(\d{2})[^\d]'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                return f"{match.group(1)}-{match.group(2)}"
        
        return None
    
    def _extract_chunks_s1000d(self, content: Tag) -> List[Dict]:
        """Extract text chunks from S1000D content"""
        chunks = []
        
        # Find all meaningful sections
        for section in content.find_all(['levelledPara', 'proceduralStep', 
                                        'para', 'warning', 'caution', 'note']):
            chunk = self._extract_chunk_from_tag(section)
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def _extract_chunks_ispec(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract text chunks from iSpec content"""
        chunks = []
        
        # Find all paragraph-like elements
        for tag in soup.find_all(['para', 'p', 'step', 'warning', 'caution', 
                                  'note', 'description']):
            chunk = self._extract_chunk_from_tag(tag)
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def _extract_chunk_from_tag(self, tag: Tag) -> Optional[Dict]:
        """Extract chunk data from tag"""
        try:
            text = tag.get_text(separator=' ', strip=True)
            
            # Skip too short or too long
            if len(text) < 20 or len(text) > 2000:
                return None
            
            # Determine chunk type
            chunk_type = 'content'
            if tag.name in ['warning', 'caution']:
                chunk_type = tag.name
            elif tag.name in ['note']:
                chunk_type = 'note'
            elif tag.name in ['proceduralStep', 'step']:
                chunk_type = 'procedure'
            
            # Extract title if present
            title_tag = tag.find('title')
            title = title_tag.get_text(strip=True) if title_tag else ''
            
            return {
                'type': chunk_type,
                'title': title,
                'text': text,
                'length': len(text)
            }
            
        except Exception as e:
            logger.debug(f"Error extracting chunk: {e}")
            return None
    
    def extract_warnings(self, soup: BeautifulSoup) -> List[str]:
        """Extract all warning/caution messages"""
        warnings = []
        
        for tag in soup.find_all(['warning', 'caution', 'warningAndCautionRef']):
            text = tag.get_text(strip=True)
            if text and 10 < len(text) < 500:
                warnings.append(text)
        
        return warnings
    
    def extract_figures(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract figure references and captions"""
        figures = []
        
        for fig in soup.find_all(['figure', 'graphic']):
            fig_data = {
                'id': fig.get('id', ''),
                'title': '',
                'caption': ''
            }
            
            title = fig.find('title')
            if title:
                fig_data['title'] = title.get_text(strip=True)
            
            caption = fig.find('caption') or fig.find('legend')
            if caption:
                fig_data['caption'] = caption.get_text(strip=True)
            
            if fig_data['title'] or fig_data['caption']:
                figures.append(fig_data)
        
        return figures
    
    def extract_references(self, soup: BeautifulSoup) -> List[str]:
        """Extract cross-references to other documents"""
        references = []
        
        for ref in soup.find_all(['dmRef', 'internalRef', 'externalRef']):
            ref_text = ref.get_text(strip=True)
            if ref_text:
                references.append(ref_text)
        
        return list(set(references))  # Remove duplicates
    
    def validate_ata_format(self, ata: str) -> bool:
        """Validate ATA format"""
        if not ata:
            return False
        
        pattern = r'^\d{2}-\d{2}$'
        return bool(re.match(pattern, ata))
