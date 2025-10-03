
"""
Core package for ATA WO Analyzer
"""
from .wo_processor import WOProcessor, WOResult
from .non_defect_filter import NonDefectFilter
from .citation_extractor import CitationExtractor
from .decision_engine import DecisionEngine
from .ata_catalog import ATACatalog

__all__ = [
    'WOProcessor',
    'WOResult',
    'NonDefectFilter',
    'CitationExtractor',
    'DecisionEngine',
    'ATACatalog',
]

__version__ = '1.0.0'
