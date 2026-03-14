"""
rag_pipeline.py
---------------
Orchestrates the full RAG pipeline:
1. Parse PDFs
2. Chunk text (section-aware)
3. Generate embeddings
4. Build FAISS index
5. Retrieve context
6. Generate DDR with Gemini

Enhanced features:
- Section-type metadata propagation
- Pipeline timing/metrics collection
- Structured error handling with descriptive messages
- Per-source chunk distribution tracking
"""

import os
import numpy as np
from dotenv import load_dotenv

from src.pdf_parser import parse_pdf
from src.chunking import chunk_documents
from src.embedding import get_gemini_embeddings
from src.vector_store import build_vector_store
from src.retriever import RAGRetriever
from src.logger import get_logger, PipelineTimer, PipelineMetrics

load_dotenv(override=True)

logger = get_logger("rag_pipeline")


class RAGPipeline:
    """
    End-to-end RAG pipeline for DDR generation.
    Handles the full flow from PDF upload to indexed vector store.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY not found. "
                "Set it in .env file or pass as api_key argument."
            )

        self.vector_store = None
        self.retriever = None
        self.extracted_images = []
        self.processed_docs = []
        self.metrics = PipelineMetrics()

    def process_pdfs(
        self,
        inspection_pdf_path: str,
        thermal_pdf_path: str,
        image_output_dir: str = None,
        progress_callback=None,
    ) -> dict:
        """
        Full pipeline: parse → chunk → embed → index.

        Enhanced with:
        - Section-type metadata on all chunks
        - Timing metrics for each stage
        - Per-source chunk distribution stats
        """

        def update_progress(step, total, message):
            if progress_callback:
                progress_callback(step, total, message)

        # ── Step 1: Parse PDFs ──────────────────────────────────────────
        update_progress(1, 5, "Extracting text and images from PDFs...")

        with PipelineTimer("PDF Parsing", logger) as t:
            inspection_data = parse_pdf(inspection_pdf_path, image_output_dir=image_output_dir)
            thermal_data = parse_pdf(thermal_pdf_path, image_output_dir=image_output_dir)
        self.metrics.record("pdf_parsing", t.elapsed,
                            inspection_pages=inspection_data.get("num_pages", 0),
                            thermal_pages=thermal_data.get("num_pages", 0))

        # Tag images with their source document
        for img in inspection_data["images"]:
            img["source"] = "Inspection_Report"
        for img in thermal_data["images"]:
            img["source"] = "Thermal_Report"

        self.extracted_images = inspection_data["images"] + thermal_data["images"]

        # Validate extraction
        if not inspection_data["text"].strip():
            logger.warning("⚠ No text extracted from inspection PDF!")
        if not thermal_data["text"].strip():
            logger.warning("⚠ No text extracted from thermal PDF!")

        # ── Step 2: Chunk documents (section-aware) ─────────────────────
        update_progress(2, 5, "Splitting text into section-aware chunks...")

        with PipelineTimer("Chunking", logger) as t:
            documents = [
                {"text": inspection_data["text"], "source": "Inspection_Report"},
                {"text": thermal_data["text"], "source": "Thermal_Report"},
            ]
            chunks = chunk_documents(documents, chunk_size=800, chunk_overlap=150)
        self.processed_docs = chunks

        # Log chunk distribution
        source_dist = {}
        section_dist = {}
        for c in chunks:
            src = c.get("source", "unknown")
            sec = c.get("section_type", "general")
            source_dist[src] = source_dist.get(src, 0) + 1
            section_dist[sec] = section_dist.get(sec, 0) + 1

        logger.info("Chunk distribution by source: %s", source_dist)
        logger.info("Chunk distribution by section: %s", section_dist)
        self.metrics.record("chunking", t.elapsed,
                            total_chunks=len(chunks),
                            source_distribution=source_dist,
                            section_distribution=section_dist)

        if not chunks:
            raise ValueError(
                "No text content could be extracted from the PDFs. "
                "The files may be image-only or corrupted."
            )

        # ── Step 3: Generate embeddings ─────────────────────────────────
        update_progress(3, 5, f"Generating embeddings for {len(chunks)} chunks...")

        with PipelineTimer("Embedding Generation", logger) as t:
            texts = [chunk["text"] for chunk in chunks]
            embeddings = get_gemini_embeddings(texts, api_key=self.api_key)
        self.metrics.record("embedding", t.elapsed, num_embeddings=len(embeddings))

        # ── Step 4: Build FAISS vector store ────────────────────────────
        update_progress(4, 5, "Building vector index...")

        with PipelineTimer("FAISS Indexing", logger) as t:
            self.vector_store = build_vector_store(chunks, embeddings)
        self.metrics.record("indexing", t.elapsed, index_size=self.vector_store.num_chunks)

        # ── Step 5: Initialize retriever ────────────────────────────────
        update_progress(5, 5, "Pipeline ready for DDR generation!")

        self.retriever = RAGRetriever(self.vector_store, api_key=self.api_key)

        logger.info("Pipeline ready. Metrics: %s", self.metrics.summary())

        return {
            "num_chunks": len(chunks),
            "num_embeddings": len(embeddings),
            "num_images": len(self.extracted_images),
            "inspection_text_length": len(inspection_data["text"]),
            "thermal_text_length": len(thermal_data["text"]),
            "source_distribution": source_dist,
            "section_distribution": section_dist,
            "pipeline_metrics": self.metrics.summary(),
        }

    def get_retriever(self) -> RAGRetriever:
        """Get the retriever after pipeline processing."""
        if self.retriever is None:
            raise RuntimeError("Pipeline not processed. Call process_pdfs() first.")
        return self.retriever

    def is_ready(self) -> bool:
        """Check if the pipeline has been processed and is ready for queries."""
        return self.vector_store is not None and self.retriever is not None
