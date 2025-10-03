"""
Reference Registry - DuckDB-based registry for manual references
"""
import duckdb
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ReferenceRegistry:
    """
    DuckDB-based registry for validating manual references
    Stores TSM/FIM/AMM task numbers and metadata
    """
    
    def __init__(self, db_path: str = "reference_db/registry.db"):
        """
        Initialize registry
        
        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Connect to DuckDB database"""
        try:
            self.conn = duckdb.connect(str(self.db_path))
            logger.info(f"Connected to registry: {self.db_path}")
        except Exception as e:
            logger.error(f"Error connecting to registry: {e}")
            raise
    
    def _create_tables(self):
        """Create registry tables if not exist"""
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS references (
                    id INTEGER PRIMARY KEY,
                    manual_type VARCHAR,
                    ata04 VARCHAR,
                    task_number VARCHAR,
                    chapter VARCHAR,
                    section VARCHAR,
                    subject VARCHAR,
                    subsection1 VARCHAR,
                    subsection2 VARCHAR,
                    title VARCHAR,
                    filename VARCHAR,
                    exists BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for fast lookup
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_number 
                ON references(task_number)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ata04 
                ON references(ata04)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_manual_type 
                ON references(manual_type)
            """)
            
            logger.info("Registry tables initialized")
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def add_reference(self, ref_data: Dict) -> bool:
        """
        Add reference to registry
        
        Args:
            ref_data: Dict with reference data
            
        Returns:
            True if successful
        """
        try:
            self.conn.execute("""
                INSERT INTO references (
                    manual_type, ata04, task_number, chapter, section, 
                    subject, subsection1, subsection2, title, filename
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                ref_data.get('manual_type'),
                ref_data.get('ata04'),
                ref_data.get('task_number'),
                ref_data.get('chapter'),
                ref_data.get('section'),
                ref_data.get('subject'),
                ref_data.get('subsection1'),
                ref_data.get('subsection2'),
                ref_data.get('title'),
                ref_data.get('filename')
            ])
            return True
            
        except Exception as e:
            logger.error(f"Error adding reference: {e}")
            return False
    
    def add_references_batch(self, refs: List[Dict]) -> int:
        """
        Add multiple references in batch
        
        Args:
            refs: List of reference dicts
            
        Returns:
            Number of references added
        """
        added = 0
        
        try:
            # Prepare data
            data = []
            for ref in refs:
                data.append([
                    ref.get('manual_type'),
                    ref.get('ata04'),
                    ref.get('task_number'),
                    ref.get('chapter'),
                    ref.get('section'),
                    ref.get('subject'),
                    ref.get('subsection1'),
                    ref.get('subsection2'),
                    ref.get('title'),
                    ref.get('filename')
                ])
            
            # Batch insert
            self.conn.executemany("""
                INSERT INTO references (
                    manual_type, ata04, task_number, chapter, section, 
                    subject, subsection1, subsection2, title, filename
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            
            added = len(data)
            logger.info(f"Added {added} references to registry")
            
        except Exception as e:
            logger.error(f"Error in batch insert: {e}")
        
        return added
    
    def exists(self, task_number: str, manual_type: Optional[str] = None) -> bool:
        """
        Check if task number exists in registry
        
        Args:
            task_number: Task number to check
            manual_type: Optional manual type filter
            
        Returns:
            True if exists
        """
        try:
            if manual_type:
                result = self.conn.execute("""
                    SELECT COUNT(*) FROM references 
                    WHERE task_number = ? AND manual_type = ?
                """, [task_number, manual_type]).fetchone()
            else:
                result = self.conn.execute("""
                    SELECT COUNT(*) FROM references 
                    WHERE task_number = ?
                """, [task_number]).fetchone()
            
            return result[0] > 0 if result else False
            
        except Exception as e:
            logger.error(f"Error checking existence: {e}")
            return False
    
    def get_reference(self, task_number: str) -> Optional[Dict]:
        """
        Get reference details by task number
        
        Args:
            task_number: Task number to lookup
            
        Returns:
            Dict with reference data or None
        """
        try:
            result = self.conn.execute("""
                SELECT manual_type, ata04, task_number, chapter, section, 
                       subject, subsection1, subsection2, title, filename
                FROM references 
                WHERE task_number = ?
                LIMIT 1
            """, [task_number]).fetchone()
            
            if result:
                return {
                    'manual_type': result[0],
                    'ata04': result[1],
                    'task_number': result[2],
                    'chapter': result[3],
                    'section': result[4],
                    'subject': result[5],
                    'subsection1': result[6],
                    'subsection2': result[7],
                    'title': result[8],
                    'filename': result[9]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting reference: {e}")
            return None
    
    def search_by_ata(self, ata04: str) -> List[Dict]:
        """
        Search references by ATA04
        
        Args:
            ata04: ATA code (e.g., "21-26")
            
        Returns:
            List of matching references
        """
        try:
            results = self.conn.execute("""
                SELECT manual_type, ata04, task_number, title
                FROM references 
                WHERE ata04 = ?
                ORDER BY manual_type, task_number
            """, [ata04]).fetchall()
            
            return [
                {
                    'manual_type': r[0],
                    'ata04': r[1],
                    'task_number': r[2],
                    'title': r[3]
                }
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Error searching by ATA: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """Get registry statistics"""
        try:
            stats = {}
            
            # Total references
            result = self.conn.execute("""
                SELECT COUNT(*) FROM references
            """).fetchone()
            stats['total_references'] = result[0] if result else 0
            
            # By manual type
            results = self.conn.execute("""
                SELECT manual_type, COUNT(*) 
                FROM references 
                GROUP BY manual_type
            """).fetchall()
            stats['by_manual_type'] = {r[0]: r[1] for r in results}
            
            # Unique ATAs
            result = self.conn.execute("""
                SELECT COUNT(DISTINCT ata04) FROM references
            """).fetchone()
            stats['unique_atas'] = result[0] if result else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def clear(self):
        """Clear all references from registry"""
        try:
            self.conn.execute("DELETE FROM references")
            logger.info("Registry cleared")
        except Exception as e:
            logger.error(f"Error clearing registry: {e}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Registry connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
