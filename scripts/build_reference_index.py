#!/usr/bin/env python3
"""
Build Reference Index - Create FAISS index and DuckDB registry from SGML
"""
import argparse
import tarfile
import json
import os
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm
import time

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sgml_parser import SGMLParser
from core.refregistry import ReferenceRegistry
from core.rag_store import build_faiss_index


class ReferenceIndexBuilder:
    """Build reference index from SGML manuals"""
    
    def __init__(
        self,
        output_dir: str = "reference_db",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        shard_size: int = 5000,
        batch_size: int = 100,
        resume: bool = True
    ):
        """
        Initialize builder
        
        Args:
            output_dir: Output directory for indices
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            shard_size: Vectors per shard
            batch_size: Embeddings per batch
            resume: Resume from previous run
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.shard_size = shard_size
        self.batch_size = batch_size
        self.resume = resume
        
        # Initialize components
        self.parser = SGMLParser()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        
        # Initialize embeddings
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.embeddings = OpenAIEmbeddings(
            model=os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small'),
            openai_api_key=api_key
        )
        
        # State tracking
        self.state_file = self.output_dir / "build_state.json"
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load build state for resume"""
        if self.resume and self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'processed_files': [],
            'current_shard': 0,
            'total_chunks': 0
        }
    
    def _save_state(self):
        """Save build state"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def process_tar(
        self,
        tar_path: str,
        manual_type: str = 'TSM',
        no_embed: bool = False
    ):
        """
        Process SGML tar file
        
        Args:
            tar_path: Path to tar file
            manual_type: Manual type (TSM/FIM/AMM)
            no_embed: Skip embedding (for testing)
        """
        print(f"\n{'='*60}")
        print(f"Processing {manual_type}: {tar_path}")
        print(f"{'='*60}\n")
        
        # Initialize registry
        registry_path = self.output_dir / "registry.db"
        with ReferenceRegistry(str(registry_path)) as registry:
            
            # Open tar file
            with tarfile.open(tar_path, 'r') as tar:
                members = tar.getmembers()
                
                # Filter SGML files
                sgml_files = [
                    m for m in members
                    if m.name.endswith(('.sgm', '.sgml'))
                ]
                
                print(f"Found {len(sgml_files)} SGML files\n")
                
                # Process files
                all_chunks = []
                references = []
                
                for member in tqdm(sgml_files, desc="Parsing SGML"):
                    # Check if already processed
                    if self.resume and member.name in self.state['processed_files']:
                        continue
                    
                    try:
                        # Extract and parse
                        f = tar.extractfile(member)
                        if not f:
                            continue
                        
                        content = f.read()
                        parsed = self.parser.parse_content(content, member.name)
                        
                        if not parsed:
                            continue
                        
                        # Add to registry
                        if parsed.get('ata04') and parsed.get('task_number'):
                            references.append({
                                'manual_type': manual_type,
                                'ata04': parsed['ata04'],
                                'task_number': parsed['task_number'],
                                'chapter': parsed['ata04'].split('-')[0],
                                'section': parsed['ata04'].split('-')[1] if '-' in parsed['ata04'] else None,
                                'subject': None,
                                'subsection1': None,
                                'subsection2': None,
                                'title': parsed.get('title', ''),
                                'filename': member.name
                            })
                        
                        # Create chunks
                        if parsed.get('chunks') and not no_embed:
                            for chunk_data in parsed['chunks']:
                                chunk_text = chunk_data.get('text', '')
                                
                                if not chunk_text or len(chunk_text) < 20:
                                    continue
                                
                                # Split if too long
                                if len(chunk_text) > self.chunk_size:
                                    sub_chunks = self.text_splitter.split_text(chunk_text)
                                else:
                                    sub_chunks = [chunk_text]
                                
                                for sub_chunk in sub_chunks:
                                    all_chunks.append({
                                        'text': sub_chunk,
                                        'ata04': parsed.get('ata04'),
                                        'task_number': parsed.get('task_number'),
                                        'title': parsed.get('title', ''),
                                        'filename': member.name,
                                        'chunk_type': chunk_data.get('type', 'content')
                                    })
                        
                        # Mark as processed
                        self.state['processed_files'].append(member.name)
                        
                    except Exception as e:
                        print(f"\n⚠️  Error processing {member.name}: {e}")
                        continue
                
                # Save references to registry
                if references:
                    print(f"\n💾 Saving {len(references)} references to registry...")
                    registry.add_references_batch(references)
                
                # Build FAISS index
                if all_chunks and not no_embed:
                    print(f"\n🔧 Building FAISS index for {len(all_chunks)} chunks...")
                    self._build_faiss_for_chunks(all_chunks, manual_type)
                
                self._save_state()
        
        print(f"\n✅ Completed processing {manual_type}")
    
    def _build_faiss_for_chunks(self, chunks: List[Dict], manual_type: str):
        """Build FAISS index from chunks with sharding"""
        
        total_chunks = len(chunks)
        num_shards = (total_chunks + self.shard_size - 1) // self.shard_size
        
        print(f"Creating {num_shards} shard(s)...")
        
        for shard_idx in range(num_shards):
            start_idx = shard_idx * self.shard_size
            end_idx = min(start_idx + self.shard_size, total_chunks)
            shard_chunks = chunks[start_idx:end_idx]
            
            print(f"\n📦 Shard {shard_idx + 1}/{num_shards}: {len(shard_chunks)} chunks")
            
            # Embed in batches with retry
            embeddings_list = []
            
            for i in tqdm(range(0, len(shard_chunks), self.batch_size), desc="Embedding"):
                batch = shard_chunks[i:i + self.batch_size]
                texts = [c['text'] for c in batch]
                
                # Retry logic
                for attempt in range(3):
                    try:
                        batch_embeddings = self.embeddings.embed_documents(texts)
                        embeddings_list.extend(batch_embeddings)
                        break
                    except Exception as e:
                        if attempt == 2:
                            print(f"\n❌ Failed to embed batch after 3 attempts: {e}")
                            # Use zero vectors as fallback
                            embeddings_list.extend([[0.0] * 1536] * len(texts))
                        else:
                            print(f"\n⚠️  Retry {attempt + 1}/3 after error: {e}")
                            time.sleep(2 ** attempt)
            
            # Build and save shard
            if num_shards > 1:
                index_file = self.output_dir / f"{manual_type.lower()}_shard_{shard_idx}.faiss"
                metadata_file = self.output_dir / f"{manual_type.lower()}_shard_{shard_idx}.pkl"
            else:
                index_file = self.output_dir / f"{manual_type.lower()}.faiss"
                metadata_file = self.output_dir / f"{manual_type.lower()}_metadata.pkl"
            
            build_faiss_index(
                chunks=shard_chunks,
                embeddings_list=embeddings_list,
                output_file=str(index_file),
                metadata_file=str(metadata_file)
            )
            
            self.state['current_shard'] = shard_idx + 1
            self.state['total_chunks'] += len(shard_chunks)
            self._save_state()


def main():
    parser = argparse.ArgumentParser(
        description="Build Reference Index from SGML manuals"
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
        '--output-dir',
        default='reference_db',
        help='Output directory (default: reference_db)'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=1000,
        help='Chunk size (default: 1000)'
    )
    parser.add_argument(
        '--chunk-overlap',
        type=int,
        default=200,
        help='Chunk overlap (default: 200)'
    )
    parser.add_argument(
        '--shard-size',
        type=int,
        default=5000,
        help='Vectors per shard (default: 5000)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Embeddings per batch (default: 100)'
    )
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Start fresh (ignore previous state)'
    )
    parser.add_argument(
        '--no-embed',
        action='store_true',
        help='Skip embedding (only parse and build registry)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Reference Index Builder")
    print("=" * 60)
    
    # Check API key
    if not args.no_embed and not os.getenv('OPENAI_API_KEY'):
        print("\n❌ Error: OPENAI_API_KEY not found in environment")
        print("   Set it with: export OPENAI_API_KEY=sk-...")
        return
    
    builder = ReferenceIndexBuilder(
        output_dir=args.output_dir,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        shard_size=args.shard_size,
        batch_size=args.batch_size,
        resume=not args.no_resume
    )
    
    builder.process_tar(
        tar_path=args.tar,
        manual_type=args.manual_type,
        no_embed=args.no_embed
    )
    
    print("\n✅ Reference index build complete!")
    print(f"📁 Output: {args.output_dir}/")
    
    if not args.no_embed:
        print("\nNext step: streamlit run app.py")


if __name__ == "__main__":
    main()
