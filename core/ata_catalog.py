"""
ATA Catalog - TF-IDF based ATA inference
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class ATACatalog:
    """
    ATA Catalog for fast offline ATA inference using TF-IDF
    """
    
    def __init__(self, catalog_dir: str = "catalog"):
        """
        Load catalog and TF-IDF model
        
        Args:
            catalog_dir: Directory containing catalog files
        """
        self.catalog_dir = Path(catalog_dir)
        self.catalog_data = None
        self.vectorizer = None
        self.tfidf_matrix = None
        self.ata_list = []
        
        self._load_catalog()
        self._load_model()
    
    def _load_catalog(self):
        """Load ATA catalog JSON"""
        catalog_file = self.catalog_dir / "ata_catalog.json"
        
        if not catalog_file.exists():
            raise FileNotFoundError(
                f"Catalog not found at {catalog_file}. "
                "Please run: python scripts/build_ata_catalog.py"
            )
        
        with open(catalog_file, 'r', encoding='utf-8') as f:
            self.catalog_data = json.load(f)
        
        # Build flat list of ATAs
        self.ata_list = list(self.catalog_data.keys())
    
    def _load_model(self):
        """Load TF-IDF model and matrix"""
        model_dir = self.catalog_dir / "model"
        
        if not model_dir.exists():
            raise FileNotFoundError(
                f"Model directory not found at {model_dir}. "
                "Please run: python scripts/build_ata_catalog.py"
            )
        
        vectorizer_path = model_dir / "tfidf_vectorizer.pkl"
        matrix_path = model_dir / "tfidf_matrix.pkl"
        
        if not vectorizer_path.exists() or not matrix_path.exists():
            raise FileNotFoundError(
                "TF-IDF model files not found. "
                "Please run: python scripts/build_ata_catalog.py"
            )
        
        self.vectorizer = joblib.load(vectorizer_path)
        self.tfidf_matrix = joblib.load(matrix_path)
    
    def predict_ata(
        self,
        defect_text: str,
        top_k: int = 3,
        min_score: float = 0.2
    ) -> Optional[Dict]:
        """
        Predict ATA from defect description
        
        Args:
            defect_text: Defect description text
            top_k: Number of top matches to consider
            min_score: Minimum similarity score
            
        Returns:
            Dict with keys: ata04, score, description, keywords
            None if no match above threshold
        """
        if not defect_text or not defect_text.strip():
            return None
        
        # Transform input text
        query_vec = self.vectorizer.transform([defect_text.lower()])
        
        # Calculate similarity
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]
        
        # Get top matches
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        top_scores = similarities[top_indices]
        
        # Return best match if above threshold
        if top_scores[0] >= min_score:
            best_idx = top_indices[0]
            best_ata = self.ata_list[best_idx]
            
            return {
                'ata04': best_ata,
                'score': float(top_scores[0]),
                'description': self.catalog_data[best_ata].get('system_name', ''),
                'keywords': self.catalog_data[best_ata].get('keywords', [])
            }
        
        return None
    
    def get_ata_info(self, ata04: str) -> Optional[Dict]:
        """
        Get catalog information for specific ATA
        
        Args:
            ata04: ATA code (e.g., "21-26")
            
        Returns:
            Dict with ATA information or None
        """
        return self.catalog_data.get(ata04)
    
    def search_by_keyword(self, keyword: str) -> List[Dict]:
        """
        Search catalog by keyword
        
        Args:
            keyword: Keyword to search
            
        Returns:
            List of matching ATA entries
        """
        keyword_lower = keyword.lower()
        results = []
        
        for ata04, data in self.catalog_data.items():
            # Search in system name
            if keyword_lower in data.get('system_name', '').lower():
                results.append({'ata04': ata04, **data})
                continue
            
            # Search in keywords
            keywords = data.get('keywords', [])
            if any(keyword_lower in kw.lower() for kw in keywords):
                results.append({'ata04': ata04, **data})
                continue
            
            # Search in warnings
            warnings = data.get('warnings', [])
            if any(keyword_lower in w.lower() for w in warnings):
                results.append({'ata04': ata04, **data})
        
        return results
    
    def get_statistics(self) -> Dict:
        """Get catalog statistics"""
        total_atas = len(self.catalog_data)
        
        total_keywords = sum(
            len(data.get('keywords', []))
            for data in self.catalog_data.values()
        )
        
        total_warnings = sum(
            len(data.get('warnings', []))
            for data in self.catalog_data.values()
        )
        
        total_descriptions = sum(
            len(data.get('sample_descriptions', []))
            for data in self.catalog_data.values()
        )
        
        return {
            'total_atas': total_atas,
            'total_keywords': total_keywords,
            'total_warnings': total_warnings,
            'total_sample_descriptions': total_descriptions,
            'vocabulary_size': len(self.vectorizer.vocabulary_) if self.vectorizer else 0
        }
    
    def validate_ata_format(self, ata: str) -> bool:
        """
        Validate ATA format
        
        Args:
            ata: ATA string to validate
            
        Returns:
            True if valid format
        """
        import re
        
        # Pattern: AA-BB or AA-BB-CC or AABB or AABBCC
        pattern = r'^(\d{2})-?(\d{2})(-\d{2})?$'
        return bool(re.match(pattern, str(ata)))
    
    def normalize_ata(self, ata: str) -> Optional[str]:
        """
        Normalize ATA to AA-BB format
        
        Args:
            ata: ATA in any format
            
        Returns:
            Normalized ATA04 or None if invalid
        """
        if not ata:
            return None
        
        # Extract digits
        digits = ''.join(c for c in str(ata) if c.isdigit())
        
        if len(digits) >= 4:
            return f"{digits[:2]}-{digits[2:4]}"
        
        return None
