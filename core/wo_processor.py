"""
Work Order Processor - Main processing pipeline
"""
import pandas as pd
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from .non_defect_filter import NonDefectFilter
from .citation_extractor import CitationExtractor
from .decision_engine import DecisionEngine
from .ata_catalog import ATACatalog


@dataclass
class WOResult:
    """Work Order processing result"""
    # Input
    ATA04_Entered: str
    Defect_Text: str
    Rectification_Text: str
    WO_Type: str
    AC_Registration: str
    Open_Date: str
    Close_Date: str
    
    # Phase 1: Non-defect filtering
    Is_Technical_Defect: bool
    Non_Defect_Reason: Optional[str] = None
    
    # Phase 2: Citation extraction (E1)
    ATA04_From_Cited: Optional[str] = None
    Cited_Manual: Optional[str] = None
    Cited_Task: Optional[str] = None
    Cited_Exists: Optional[bool] = None
    
    # Phase 3: Derived inference (E2)
    ATA04_Derived: Optional[str] = None
    Derived_Task: Optional[str] = None
    Derived_DocType: Optional[str] = None
    Derived_Score: Optional[float] = None
    Evidence_Snippet: Optional[str] = None
    Evidence_Source: Optional[str] = None
    
    # Phase 4: Final decision
    Decision: str = "REVIEW"
    ATA04_Final: Optional[str] = None
    Confidence: Optional[float] = None
    Reason: Optional[str] = None


class WOProcessor:
    """Main Work Order processing pipeline"""
    
    COLUMN_MAPPING = {
        'ATA': 'ATA04_Entered',
        'W/O Description': 'Defect_Text',
        'W/O Action': 'Rectification_Text',
        'Type': 'WO_Type',
        'A/C': 'AC_Registration',
        'Issued': 'Open_Date',
        'Closed': 'Close_Date',
        'ATA 04 Corrected': 'ATA04_Final'
    }
    
    def __init__(
        self,
        catalog: ATACatalog,
        mode: str = 'catalog',
        filter_non_defect: bool = True,
        confidence_threshold: float = 0.75,
        rag_store=None
    ):
        """
        Initialize processor
        
        Args:
            catalog: ATACatalog instance
            mode: 'catalog' or 'rag'
            filter_non_defect: Whether to filter non-defects
            confidence_threshold: Minimum confidence for decisions
            rag_store: Optional RAG store for advanced mode
        """
        self.catalog = catalog
        self.mode = mode
        self.filter_non_defect = filter_non_defect
        self.confidence_threshold = confidence_threshold
        self.rag_store = rag_store
        
        # Initialize components
        self.non_defect_filter = NonDefectFilter()
        self.citation_extractor = CitationExtractor()
        self.decision_engine = DecisionEngine(confidence_threshold)
        
        # Cache for repeated defect texts
        self._cache: Dict[str, WOResult] = {}
    
    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process entire dataframe of work orders
        
        Args:
            df: Input dataframe with WO data
            
        Returns:
            DataFrame with results
        """
        # Map columns
        df_mapped = self._map_columns(df)
        
        # Process each row
        results = []
        for idx, row in df_mapped.iterrows():
            result = self.process_wo(row.to_dict())
            results.append(asdict(result))
        
        # Convert to dataframe
        results_df = pd.DataFrame(results)
        
        # Copy any additional columns from original
        for col in df.columns:
            if col not in self.COLUMN_MAPPING and col in df_mapped.columns:
                results_df[col] = df_mapped[col]
        
        return results_df
    
    def process_wo(self, wo_dict: Dict) -> WOResult:
        """
        Process single work order
        
        Args:
            wo_dict: Dictionary with WO data
            
        Returns:
            WOResult object
        """
        # Extract fields
        ata_entered = self._normalize_ata(wo_dict.get('ATA04_Entered', ''))
        defect_text = str(wo_dict.get('Defect_Text', ''))
        rectification_text = str(wo_dict.get('Rectification_Text', ''))
        
        # Check cache
        cache_key = self._get_cache_key(defect_text, rectification_text)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            # Update with current WO specifics
            cached.ATA04_Entered = ata_entered
            cached.WO_Type = wo_dict.get('WO_Type', '')
            cached.AC_Registration = wo_dict.get('AC_Registration', '')
            cached.Open_Date = wo_dict.get('Open_Date', '')
            cached.Close_Date = wo_dict.get('Close_Date', '')
            return cached
        
        # Initialize result
        result = WOResult(
            ATA04_Entered=ata_entered,
            Defect_Text=defect_text,
            Rectification_Text=rectification_text,
            WO_Type=wo_dict.get('WO_Type', ''),
            AC_Registration=wo_dict.get('AC_Registration', ''),
            Open_Date=str(wo_dict.get('Open_Date', '')),
            Close_Date=str(wo_dict.get('Close_Date', '')),
            Is_Technical_Defect=True
        )
        
        # Phase 1: Filter non-defects
        if self.filter_non_defect:
            is_defect, reason = self.non_defect_filter.is_technical_defect(
                defect_text, rectification_text
            )
            result.Is_Technical_Defect = is_defect
            result.Non_Defect_Reason = reason
            
            if not is_defect:
                result.Decision = "NON_DEFECT"
                result.ATA04_Final = ata_entered
                result.Confidence = 0.99
                result.Reason = f"Non-technical: {reason}"
                self._cache[cache_key] = result
                return result
        
        # Phase 2: Extract citations (E1)
        citations = self.citation_extractor.extract_citations(rectification_text)
        if citations:
            # Take first valid citation
            citation = citations[0]
            result.ATA04_From_Cited = citation['ata04']
            result.Cited_Manual = citation['manual_type']
            result.Cited_Task = citation['task_number']
            result.Cited_Exists = True  # TODO: Validate against registry
        
        # Phase 3: Derive from catalog/RAG (E2)
        if self.mode == 'catalog':
            derived = self.catalog.predict_ata(defect_text)
            if derived:
                result.ATA04_Derived = derived['ata04']
                result.Derived_DocType = 'CATALOG'
                result.Derived_Score = derived['score']
                result.Evidence_Snippet = derived.get('description', '')
                result.Evidence_Source = 'ATA Catalog'
        
        # Phase 4: Decision engine
        decision_result = self.decision_engine.make_decision(
            e0=ata_entered,
            e1=result.ATA04_From_Cited,
            e1_valid=result.Cited_Exists,
            e2=result.ATA04_Derived,
            e2_score=result.Derived_Score
        )
        
        result.Decision = decision_result['decision']
        result.ATA04_Final = decision_result['ata04_final']
        result.Confidence = decision_result['confidence']
        result.Reason = decision_result['reason']
        
        # Cache result
        self._cache[cache_key] = result
        
        return result
    
    def _map_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map user columns to internal names"""
        df_copy = df.copy()
        
        # Rename columns according to mapping
        rename_dict = {}
        for user_col, internal_col in self.COLUMN_MAPPING.items():
            if user_col in df_copy.columns:
                rename_dict[user_col] = internal_col
        
        df_copy = df_copy.rename(columns=rename_dict)
        
        return df_copy
    
    def _normalize_ata(self, ata: str) -> str:
        """Normalize ATA to AA-BB format"""
        if not ata:
            return ''
        
        ata_str = str(ata).strip()
        
        # Remove spaces and dashes
        ata_clean = ata_str.replace(' ', '').replace('-', '')
        
        # Extract first 4 digits
        digits = ''.join(c for c in ata_clean if c.isdigit())
        
        if len(digits) >= 4:
            return f"{digits[:2]}-{digits[2:4]}"
        
        return ata_str
    
    def _get_cache_key(self, defect_text: str, rectification_text: str) -> str:
        """Generate cache key from texts"""
        combined = f"{defect_text}|{rectification_text}"
        return hashlib.sha1(combined.encode()).hexdigest()[:16]
