#!/usr/bin/env python3
"""
Build ATA Catalog from SGML manuals
Creates catalog JSON and TF-IDF model for fast ATA inference
"""
import argparse
import json
import tarfile
from pathlib import Path
from typing import Dict, List
from collections import defaultdict
import re

from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
from tqdm import tqdm


class CatalogBuilder:
    """Build ATA catalog from SGML files"""
    
    def __init__(self, manual_type: str = 'TSM'):
        """
        Initialize builder
        
        Args:
            manual_type: Type of manual (TSM, FIM, AMM)
        """
        self.manual_type = manual_type
        self.catalog = defaultdict(lambda: {
            'system_name': '',
            'keywords': set(),
            'warnings': set(),
            'sample_descriptions': set()
        })
    
    def process_tar(self, tar_path: str):
        """
        Process SGML tar file
        
        Args:
            tar_path: Path to SGML tar file
        """
        print(f"📦 Opening {tar_path}...")
        
        with tarfile.open(tar_path, 'r') as tar:
            members = tar.getmembers()
            
            # Filter SGML files
            sgml_files = [
                m for m in members
                if m.name.endswith('.sgm') or m.name.endswith('.sgml')
            ]
            
            print(f"📄 Found {len(sgml_files)} SGML files")
            
            for member in tqdm(sgml_files, desc="Processing"):
                try:
                    f = tar.extractfile(member)
                    if f:
                        content = f.read()
                        self._parse_sgml(content, member.name)
                except Exception as e:
                    print(f"⚠️  Error processing {member.name}: {e}")
    
    def _parse_sgml(self, content: bytes, filename: str):
        """Parse single SGML file"""
        try:
            soup = BeautifulSoup(content, 'lxml-xml')
            
            # Extract ATA from filename or DMC
            ata04 = self._extract_ata_from_filename(filename)
            
            if not ata04:
                # Try DMC tag
                dmc = soup.find('dmc')
                if dmc:
                    ata04 = self._extract_ata_from_dmc(dmc)
            
            if not ata04:
                return
            
            # Extract system name
            system_name = self._extract_system_name(soup)
            if system_name and not self.catalog[ata04]['system_name']:
                self.catalog[ata04]['system_name'] = system_name
            
            # Extract keywords from titles and descriptions
            keywords = self._extract_keywords(soup)
            self.catalog[ata04]['keywords'].update(keywords)
            
            # Extract warnings/cautions (ECAM/EICAS/CAS)
            warnings = self._extract_warnings(soup)
            self.catalog[ata04]['warnings'].update(warnings)
            
            # Extract sample descriptions
            descriptions = self._extract_descriptions(soup)
            self.catalog[ata04]['sample_descriptions'].update(descriptions)
            
        except Exception as e:
            pass  # Silently skip problematic files
    
    def _extract_ata_from_filename(self, filename: str) -> str:
        """Extract ATA04 from filename"""
        # Pattern: ...21-26-00... or ...212600...
        match = re.search(r'(\d{2})[_-]?(\d{2})', filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        return None
    
    def _extract_ata_from_dmc(self, dmc_tag) -> str:
        """Extract ATA from DMC tag"""
        try:
            # Look for systemCode or similar
            sys_code = dmc_tag.find('systemCode')
            subsys_code = dmc_tag.find('subSystemCode')
            
            if sys_code and subsys_code:
                return f"{sys_code.text.strip()}-{subsys_code.text.strip()}"
        except:
            pass
        return None
    
    def _extract_system_name(self, soup) -> str:
        """Extract system name from SGML"""
        # Try various title tags
        for tag_name in ['title', 'dmTitle', 'techName', 'infoName']:
            tag = soup.find(tag_name)
            if tag and tag.text:
                text = tag.text.strip()
                if len(text) > 5 and len(text) < 200:
                    return text
        return ""
    
    def _extract_keywords(self, soup) -> set:
        """Extract keywords from SGML"""
        keywords = set()
        
        # From titles and descriptions
        for tag_name in ['title', 'para', 'description', 'warning', 'caution']:
            for tag in soup.find_all(tag_name):
                text = tag.get_text().strip()
                if text and len(text) < 100:
                    # Extract meaningful words
                    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
                    keywords.update(words[:10])  # Limit per tag
        
        return keywords
    
    def _extract_warnings(self, soup) -> set:
        """Extract warning messages (ECAM/EICAS/CAS)"""
        warnings = set()
        
        # Look for warning/caution tags
        for tag in soup.find_all(['warning', 'caution', 'warningAndCautionRef']):
            text = tag.get_text().strip()
            if text and len(text) < 200:
                warnings.add(text)
        
        # Look for ECAM/EICAS patterns in text
        text_content = soup.get_text()
        ecam_pattern = r'[A-Z]{2,}\s+[A-Z/]+(?:\s+[A-Z]+)?'
        for match in re.finditer(ecam_pattern, text_content):
            msg = match.group().strip()
            if 5 < len(msg) < 50:
                warnings.add(msg)
        
        return warnings
    
    def _extract_descriptions(self, soup) -> set:
        """Extract sample defect descriptions"""
        descriptions = set()
        
        # From paragraphs
        for para in soup.find_all(['para', 'description']):
            text = para.get_text().strip()
            # Look for symptom-like sentences
            if text and 20 < len(text) < 150:
                if any(word in text.lower() for word in [
                    'failure', 'fault', 'leak', 'inoperative', 'malfunction',
                    'abnormal', 'warning', 'error', 'defect'
                ]):
                    descriptions.add(text)
        
        return descriptions
    
    def build_tfidf_model(self):
        """Build TF-IDF model from catalog"""
        print("🔧 Building TF-IDF model...")
        
        # Prepare training texts
        ata_list = []
        texts = []
        
        for ata04, data in self.catalog.items():
            # Combine all text for this ATA
            components = [
                data['system_name'],
                ' '.join(data['keywords']),
                ' '.join(data['warnings']),
                ' '.join(list(data['sample_descriptions'])[:5])  # Limit samples
            ]
            
            combined_text = ' '.join(components).lower()
            
            if combined_text.strip():
                ata_list.append(ata04)
                texts.append(combined_text)
        
        if not texts:
            raise ValueError("No texts to build model. Check SGML parsing.")
        
        print(f"📊 Training on {len(texts)} ATA codes...")
        
        # Train TF-IDF
        vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            min_df=1,
            max_df=0.8,
            stop_words='english'
        )
        
        tfidf_matrix = vectorizer.fit_transform(texts)
        
        return vectorizer, tfidf_matrix, ata_list
    
    def save_catalog(self, output_dir: str):
        """
        Save catalog and model
        
        Args:
            output_dir: Output directory
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Convert sets to lists for JSON
        catalog_json = {}
        for ata04, data in self.catalog.items():
            catalog_json[ata04] = {
                'system_name': data['system_name'],
                'keywords': list(data['keywords'])[:50],  # Limit size
                'warnings': list(data['warnings'])[:20],
                'sample_descriptions': list(data['sample_descriptions'])[:10]
            }
        
        # Save catalog JSON
        catalog_file = output_path / "ata_catalog.json"
        with open(catalog_file, 'w', encoding='utf-8') as f:
            json.dump(catalog_json, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved catalog to {catalog_file}")
        print(f"   Total ATAs: {len(catalog_json)}")
        
        # Build and save model
        vectorizer, tfidf_matrix, ata_list = self.build_tfidf_model()
        
        model_dir = output_path / "model"
        model_dir.mkdir(exist_ok=True)
        
        joblib.dump(vectorizer, model_dir / "tfidf_vectorizer.pkl")
        joblib.dump(tfidf_matrix, model_dir / "tfidf_matrix.pkl")
        
        # Save ATA list
        with open(model_dir / "ata_list.json", 'w') as f:
            json.dump(ata_list, f)
        
        print(f"✅ Saved TF-IDF model to {model_dir}")
        print(f"   Vocabulary size: {len(vectorizer.vocabulary_)}")


def main():
    parser = argparse.ArgumentParser(
        description="Build ATA Catalog from SGML manuals"
    )
    parser.add_argument(
        '--tar',
        required=True,
        help='Path to SGML tar file'
    )
    parser.add_argument(
        '--manual-type',
        default='TSM',
        choices=['TSM', 'FIM', 'AMM'],
        help='Manual type (default: TSM)'
    )
    parser.add_argument(
        '--output',
        default='catalog',
        help='Output directory (default: catalog)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("ATA Catalog Builder")
    print("=" * 60)
    
    builder = CatalogBuilder(manual_type=args.manual_type)
    builder.process_tar(args.tar)
    builder.save_catalog(args.output)
    
    print("\n✅ Catalog build complete!")
    print(f"📁 Output: {args.output}/")
    print("\nNext step: streamlit run app.py")


if __name__ == "__main__":
    main()
