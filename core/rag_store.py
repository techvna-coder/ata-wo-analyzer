"""
RAG Store - FAISS-based vector store for manual content
"""
import os
import json
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

import faiss
import numpy as np
from langchain.embeddings import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class RAGStore:
    """
    FAISS-based vector store for RAG (Retrieval Augmented Generation)
    Supports sharding for large document collections
    """
    
    def __init__(
        self,
        index_dir: str = "reference_db",
        embedding_model: str = "text-embedding-3-small",
        dimension: int = 1536
    ):
        """
        Initialize RAG store
        
        Args:
            index_dir: Directory containing FAISS indices
            embedding_model: OpenAI embedding model name
            dimension: Embedding dimension
        """
        self.index_dir = Path(index_dir)
        self.embedding_model = embedding_model
        self.dimension = dimension
        
        self.indices = {}  # {manual_type: faiss.Index}
        self.metadatas = {}  # {manual_type: List[Dict]}
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=os.getenv('OPENAI_API_KEY')
        )
        
        self._load_indices()
    
    def _load_indices(self):
        """Load all FAISS indices from disk"""
        if not self.index_dir.exists():
            logger.warning(f"Index directory not found: {self.index_dir}")
            return
        
        # Load each manual type
        for manual_type in ['TSM', 'FIM', 'AMM', 'CATALOG']:
            self._load_manual_index(manual_type)
    
    def _load_manual_index(self, manual_type: str):
        """Load index for specific manual type"""
        try:
            # Check for sharded indices
            shard_pattern = f"{manual_type.lower()}_shard_*.faiss"
            shard_files = list(self.index_dir.glob(shard_pattern))
            
            if shard_files:
                # Load sharded indices
                self._load_sharded_index(manual_type, shard_files)
            else:
                # Load single index
                index_file = self.index_dir / f"{manual_type.lower()}.faiss"
                metadata_file = self.index_dir / f"{manual_type.lower()}_metadata.pkl"
                
                if index_file.exists() and metadata_file.exists():
                    self.indices[manual_type] = faiss.read_index(str(index_file))
                    
                    with open(metadata_file, 'rb') as f:
                        self.metadatas[manual_type] = pickle.load(f)
                    
                    logger.info(f"Loaded {manual_type} index: {self.indices[manual_type].ntotal} vectors")
        
        except Exception as e:
            logger.error(f"Error loading {manual_type} index: {e}")
    
    def _load_sharded_index(self, manual_type: str, shard_files: List[Path]):
        """Load and merge sharded indices"""
        try:
            # Sort shard files by number
            shard_files = sorted(shard_files, key=lambda x: int(x.stem.split('_')[-1]))
            
            # Load first shard to get dimension
            first_index = faiss.read_index(str(shard_files[0]))
            
            # Create merged index
            merged_index = faiss.IndexFlatL2(first_index.d)
            merged_metadata = []
            
            # Add vectors from all shards
            for shard_file in shard_files:
                index = faiss.read_index(str(shard_file))
                
                # Get vectors
                vectors = np.zeros((index.ntotal, index.d), dtype='float32')
                for i in range(index.ntotal):
                    vectors[i] = index.reconstruct(i)
                
                # Add to merged index
                merged_index.add(vectors)
                
                # Load metadata
                metadata_file = shard_file.with_suffix('.pkl')
                if metadata_file.exists():
                    with open(metadata_file, 'rb') as f:
                        shard_metadata = pickle.load(f)
                        merged_metadata.extend(shard_metadata)
            
            self.indices[manual_type] = merged_index
            self.metadatas[manual_type] = merged_metadata
            
            logger.info(f"Loaded {len(shard_files)} shards for {manual_type}: {merged_index.ntotal} vectors")
        
        except Exception as e:
            logger.error(f"Error loading sharded index for {manual_type}: {e}")
    
    def search(
        self,
        query: str,
        manual_types: List[str] = ['TSM', 'FIM', 'AMM'],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Search for relevant chunks
        
        Args:
            query: Search query text
            manual_types: List of manual types to search
            top_k: Number of results to return per manual type
            
        Returns:
            List of dicts with chunk data and scores
        """
        if not query or not query.strip():
            return []
        
        try:
            # Embed query
            query_embedding = self.embeddings.embed_query(query)
            query_vector = np.array([query_embedding], dtype='float32')
            
            # Search each manual type
            all_results = []
            
            for manual_type in manual_types:
                if manual_type not in self.indices:
                    logger.warning(f"Index not found for {manual_type}")
                    continue
                
                index = self.indices[manual_type]
                metadata = self.metadatas.get(manual_type, [])
                
                # Search
                distances, indices = index.search(query_vector, top_k)
                
                # Collect results
                for i, idx in enumerate(indices[0]):
                    if idx < len(metadata):
                        result = metadata[idx].copy()
                        result['score'] = float(1 / (1 + distances[0][i]))  # Convert distance to similarity
                        result['manual_type'] = manual_type
                        all_results.append(result)
            
            # Sort by score
            all_results.sort(key=lambda x: x['score'], reverse=True)
            
            return all_results[:top_k * len(manual_types)]
        
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def search_by_ata(
        self,
        ata04: str,
        query: str,
        manual_types: List[str] = ['TSM', 'FIM', 'AMM'],
        top_k: int = 3
    ) -> List[Dict]:
        """
        Search within specific ATA code
        
        Args:
            ata04: ATA code to filter by
            query: Search query
            manual_types: Manual types to search
            top_k: Number of results
            
        Returns:
            List of matching chunks
        """
        # First do general search
        results = self.search(query, manual_types, top_k * 3)
        
        # Filter by ATA
        filtered = [r for r in results if r.get('ata04') == ata04]
        
        return filtered[:top_k]
    
    def get_chunk_by_id(self, chunk_id: str, manual_type: str) -> Optional[Dict]:
        """
        Get specific chunk by ID
        
        Args:
            chunk_id: Chunk identifier
            manual_type: Manual type
            
        Returns:
            Chunk data or None
        """
        if manual_type not in self.metadatas:
            return None
        
        for chunk in self.metadatas[manual_type]:
            if chunk.get('id') == chunk_id:
                return chunk
        
        return None
    
    def get_statistics(self) -> Dict:
        """Get store statistics"""
        stats = {
            'total_vectors': 0,
            'by_manual_type': {},
            'dimension': self.dimension,
            'embedding_model': self.embedding_model
        }
        
        for manual_type, index in self.indices.items():
            count = index.ntotal
            stats['by_manual_type'][manual_type] = count
            stats['total_vectors'] += count
        
        return stats
    
    def is_available(self) -> bool:
        """Check if RAG store is available and ready"""
        return len(self.indices) > 0
    
    def get_available_manual_types(self) -> List[str]:
        """Get list of available manual types"""
        return list(self.indices.keys())


def build_faiss_index(
    chunks: List[Dict],
    embeddings_list: List[List[float]],
    output_file: str,
    metadata_file: str
):
    """
    Build and save FAISS index from chunks and embeddings
    
    Args:
        chunks: List of chunk metadata
        embeddings_list: List of embedding vectors
        output_file: Path to save FAISS index
        metadata_file: Path to save metadata
    """
    try:
        # Convert to numpy array
        embeddings_array = np.array(embeddings_list, dtype='float32')
        dimension = embeddings_array.shape[1]
        
        # Create FAISS index
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_array)
        
        # Save index
        faiss.write_index(index, output_file)
        
        # Save metadata
        with open(metadata_file, 'wb') as f:
            pickle.dump(chunks, f)
        
        logger.info(f"Built FAISS index: {index.ntotal} vectors, dim={dimension}")
        logger.info(f"Saved to: {output_file}")
        
        return index
        
    except Exception as e:
        logger.error(f"Error building FAISS index: {e}")
        raise
