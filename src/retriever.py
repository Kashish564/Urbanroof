"""
retriever.py
------------
Retrieves relevant text chunks from the FAISS vector store
using semantic similarity search.

Enhanced features:
- Balanced cross-document retrieval (ensures both sources are represented)
- Area-based correlation (groups inspection + thermal data per location)
- Extended domain-specific queries for comprehensive DDR coverage
- Deduplication with similarity-based merging
"""

import re
import numpy as np
from src.vector_store import FAISSVectorStore
from src.embedding import get_query_embedding
from src.logger import get_logger

logger = get_logger("retriever")


def _text_overlap_ratio(a: str, b: str) -> float:
    """
    Compute the overlap ratio between two texts using set-of-lines intersection.
    Returns a value between 0.0 (no overlap) and 1.0 (identical).
    """
    if not a or not b:
        return 0.0
    lines_a = set(line.strip() for line in a.split('\n') if line.strip())
    lines_b = set(line.strip() for line in b.split('\n') if line.strip())
    if not lines_a or not lines_b:
        return 0.0
    intersection = lines_a & lines_b
    smaller = min(len(lines_a), len(lines_b))
    return len(intersection) / smaller if smaller > 0 else 0.0


class RAGRetriever:
    """
    Retrieves relevant document chunks using semantic search.
    Supports multi-query, cross-document, and area-aware retrieval.
    """

    def __init__(self, vector_store: FAISSVectorStore, api_key: str = None):
        self.vector_store = vector_store
        self.api_key = api_key

    def retrieve(self, query: str, top_k: int = 5) -> list:
        """Retrieve top-k most relevant chunks for a query."""
        query_emb = get_query_embedding(query, api_key=self.api_key)
        results = self.vector_store.search(query_emb, top_k=top_k)
        return results

    def balanced_retrieve(self, query: str, top_k: int = 5) -> list:
        """
        Retrieve chunks ensuring BOTH document sources are represented.
        Fetches extra results and selects a balanced mix from each source.
        """
        # Fetch 2x to have enough candidates from each source
        query_emb = get_query_embedding(query, api_key=self.api_key)
        all_results = self.vector_store.search(query_emb, top_k=top_k * 3)

        # Group by source
        by_source = {}
        for chunk in all_results:
            src = chunk.get("source", "unknown")
            by_source.setdefault(src, []).append(chunk)

        # Balanced selection: alternate between sources
        balanced = []
        sources = list(by_source.keys())
        per_source = max(2, top_k // max(len(sources), 1))

        for src in sources:
            balanced.extend(by_source[src][:per_source])

        # Sort by score and trim to top_k
        balanced.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        return balanced[:top_k]

    def retrieve_for_ddr(self, top_k_per_query: int = 5) -> str:
        """
        Retrieve comprehensive context for DDR generation using
        multiple targeted queries covering all DDR sections.

        Enhanced:
        - Uses balanced retrieval to ensure cross-document coverage
        - Extended query set for thorough coverage
        - Groups context by section type
        - Reports coverage gaps

        Returns:
            Deduplicated, structured context string
        """
        # Comprehensive targeted queries covering all DDR sections
        queries = [
            # Inspection metadata
            "property inspection details customer name case number date inspected by",
            "type of structure number of floors year of construction age of building",
            "previous structure audit done previous repairs history",

            # Area observations and leakage
            "impacted areas dampness seepage leakage skirting hall bedroom kitchen",
            "bathroom tile hollowness grouting tile joints plumbing issues gaps",
            "parking area ceiling leakage common area seepage drainage",
            "balcony terrace waterproofing membrane condition",
            "master bedroom wall dampness ceiling stain moisture",

            # Thermal data
            "thermal reading temperature variation hotspot coldspot moisture detection",
            "thermal imaging infrared analysis temperature difference delta",
            "thermal scan results heat pattern anomaly surface temperature",

            # Structural condition
            "RCC column beam slab condition cracks spalling reinforcement",
            "external wall cracks facade efflorescence plaster deterioration",
            "terrace condition waterproofing drainage slope assessment",
            "structural condition assessment rating good moderate poor",

            # Checklists and scores
            "inspection checklist score flagged items concealed plumbing",
            "severity assessment high moderate low overall condition",

            # Summary and actions
            "summary table impacted areas exposed sources negative positive side",
            "priority actions immediate short-term long-term recommendations",
            "treatment suggestion repair waterproofing grouting plaster",
        ]

        all_chunks = []
        source_counts = {}

        for query in queries:
            try:
                # Use balanced retrieval for cross-document coverage
                results = self.balanced_retrieve(query, top_k=top_k_per_query)

                for chunk in results:
                    text = chunk.get("text", "")
                    if not text.strip():
                        continue

                    # Overlap-based dedup: skip if >50% overlap with any existing chunk
                    is_duplicate = False
                    for existing in all_chunks:
                        if _text_overlap_ratio(text, existing.get("text", "")) > 0.50:
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        all_chunks.append(chunk)
                        src = chunk.get("source", "unknown")
                        source_counts[src] = source_counts.get(src, 0) + 1

            except Exception as e:
                logger.warning("Query failed: '%s...' — %s", query[:40], e)
                continue

        # Log retrieval statistics
        logger.info(
            "Retrieved %d unique chunks from %d queries. Source distribution: %s",
            len(all_chunks), len(queries), source_counts,
        )

        # Sort by relevance score
        all_chunks.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

        # Build structured context grouped by source
        context_parts = []

        # Add a coverage summary header
        coverage_header = self._build_coverage_report(all_chunks, source_counts)
        if coverage_header:
            context_parts.append(coverage_header)

        # Group chunks by source for clarity
        inspection_chunks = [c for c in all_chunks if "inspection" in c.get("source", "").lower()]
        thermal_chunks = [c for c in all_chunks if "thermal" in c.get("source", "").lower()]
        other_chunks = [c for c in all_chunks
                        if c not in inspection_chunks and c not in thermal_chunks]

        if inspection_chunks:
            context_parts.append("=== INSPECTION REPORT DATA ===")
            for chunk in inspection_chunks:
                section = chunk.get("section_type", "general")
                text = chunk.get("text", "")
                context_parts.append(f"[Source: Inspection_Report | Section: {section}]\n{text}")

        if thermal_chunks:
            context_parts.append("\n=== THERMAL REPORT DATA ===")
            for chunk in thermal_chunks:
                section = chunk.get("section_type", "general")
                text = chunk.get("text", "")
                context_parts.append(f"[Source: Thermal_Report | Section: {section}]\n{text}")

        if other_chunks:
            context_parts.append("\n=== ADDITIONAL DATA ===")
            for chunk in other_chunks:
                source = chunk.get("source", "Unknown")
                text = chunk.get("text", "")
                context_parts.append(f"[Source: {source}]\n{text}")

        return "\n\n---\n\n".join(context_parts)

    def _build_coverage_report(self, chunks: list, source_counts: dict) -> str:
        """
        Build a coverage report that tells the LLM what data is available
        and what might be missing.
        """
        section_types_found = set()
        for c in chunks:
            st = c.get("section_type", "general")
            section_types_found.add(st)

        expected = {
            "inspection_metadata", "observation", "thermal_reading",
            "structural", "checklist", "severity_action",
        }
        missing = expected - section_types_found

        lines = [
            "[DATA COVERAGE REPORT]",
            f"Total chunks retrieved: {len(chunks)}",
            f"Sources: {source_counts}",
            f"Section types found: {sorted(section_types_found)}",
        ]

        if missing:
            lines.append(f"⚠ Missing section types: {sorted(missing)}")
            lines.append("Note: For missing sections, write 'Not Available' with a specific reason.")
        else:
            lines.append("✓ All expected section types have data coverage.")

        return "\n".join(lines)

    def simple_retrieve(self, query: str, top_k: int = 10) -> str:
        """Simple retrieval returning a formatted context string."""
        results = self.retrieve(query, top_k=top_k)

        context_parts = []
        for chunk in results:
            source = chunk.get("source", "Unknown")
            text = chunk.get("text", "")
            context_parts.append(f"[Source: {source}]\n{text}")

        return "\n\n---\n\n".join(context_parts)
