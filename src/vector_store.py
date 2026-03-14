"""
vector_store.py
---------------
Creates and manages a FAISS vector index for fast similarity search.
Stores chunk metadata alongside embeddings for retrieval.
"""

import numpy as np
import faiss
import pickle
import os


class FAISSVectorStore:
    """
    In-memory FAISS vector store with metadata support.
    Supports save/load for caching between sessions.
    """
    
    def __init__(self, embedding_dim: int = 768):
        """
        Initialize the FAISS index.
        
        Args:
            embedding_dim: Dimension of embedding vectors (768 for Gemini embedding-001)
        """
        self.embedding_dim = embedding_dim
        self.index = None
        self.chunks = []  # Stores the original chunk metadata
        self._is_built = False
    
    def build(self, embeddings: np.ndarray, chunks: list):
        """
        Build the FAISS index from embeddings and store chunk metadata.
        
        Args:
            embeddings: numpy array of shape (n, embedding_dim)
            chunks: List of chunk dicts (with 'text', 'source', etc.)
        """
        if len(embeddings) == 0:
            raise ValueError("No embeddings provided to build index")
        
        if embeddings.shape[0] != len(chunks):
            raise ValueError(f"Mismatch: {embeddings.shape[0]} embeddings but {len(chunks)} chunks")
        
        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
        normalized = embeddings / norms
        
        # Create inner product index (equivalent to cosine similarity after normalization)
        self.embedding_dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.index.add(normalized.astype(np.float32))
        
        self.chunks = chunks
        self._is_built = True
        
        return self
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> list:
        """
        Search for the most similar chunks given a query embedding.
        
        Args:
            query_embedding: 1D numpy array (embedding vector)
            top_k: Number of top results to return
            
        Returns:
            List of dicts with chunk data and similarity scores
        """
        if not self._is_built:
            raise RuntimeError("Index not built. Call build() first.")
        
        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm
        
        # Reshape for FAISS (needs 2D array)
        query_2d = query_embedding.reshape(1, -1).astype(np.float32)
        
        # Limit top_k to available chunks
        actual_k = min(top_k, len(self.chunks))
        
        # Search
        scores, indices = self.index.search(query_2d, actual_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.chunks):
                result = dict(self.chunks[idx])
                result["similarity_score"] = float(score)
                results.append(result)
        
        return results
    
    def save(self, path: str):
        """Save the index and metadata to disk."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        
        faiss.write_index(self.index, path + ".faiss")
        
        with open(path + ".meta", "wb") as f:
            pickle.dump({
                "chunks": self.chunks,
                "embedding_dim": self.embedding_dim
            }, f)
    
    def load(self, path: str):
        """Load the index and metadata from disk."""
        self.index = faiss.read_index(path + ".faiss")
        
        with open(path + ".meta", "rb") as f:
            meta = pickle.load(f)
            self.chunks = meta["chunks"]
            self.embedding_dim = meta["embedding_dim"]
        
        self._is_built = True
        return self
    
    @property
    def num_chunks(self) -> int:
        return len(self.chunks)
    
    @property
    def is_built(self) -> bool:
        return self._is_built


def build_vector_store(chunks: list, embeddings: np.ndarray) -> FAISSVectorStore:
    """
    Convenience function to build a vector store from chunks and embeddings.
    
    Args:
        chunks: List of chunk dicts
        embeddings: numpy array of embeddings
        
    Returns:
        Built FAISSVectorStore instance
    """
    store = FAISSVectorStore()
    store.build(embeddings, chunks)
    return store
