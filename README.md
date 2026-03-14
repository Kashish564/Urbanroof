# 🏗️ AI DDR Generator

> **Generate professional Detailed Diagnostic Reports (DDR)** from property inspection PDFs and thermal imaging reports using RAG + Gemini 1.5 Pro.

---

## 📖 Overview

The AI DDR Generator is a production-ready system that:

1. **Ingests** two PDF documents — an Inspection Report and a Thermal Images Report
2. **Extracts** text and images using PyMuPDF
3. **Chunks** and **embeds** the text using Google Gemini's embedding model
4. **Indexes** embeddings in a FAISS vector store for fast semantic search
5. **Retrieves** the most relevant context via multi-query RAG
6. **Generates** a structured DDR using Gemini 1.5 Pro, grounded in retrieved evidence

**Key Principle**: The system never invents information. If data is missing, it writes "Not Available".

---

## 🏛️ Architecture

```
PDF Upload (Inspection + Thermal)
        ↓
PDF Parsing (PyMuPDF)
  - Text extraction
  - Image extraction
        ↓
Text Chunking (800 chars, 150 overlap)
        ↓
Embedding Generation (Gemini embedding-001)
        ↓
FAISS Vector Index (cosine similarity)
        ↓
Multi-Query RAG Retrieval (10 targeted queries)
        ↓
Context Assembly (deduplicated, ranked)
        ↓
Gemini 1.5 Pro (temp=0.1, grounded generation)
        ↓
DDR Report (7 sections)
        ↓
Streamlit Display + Download
```

---

## 📋 DDR Report Sections

| # | Section | Description |
|---|---------|-------------|
| 1 | Property Issue Summary | Overall summary of all findings |
| 2 | Area-wise Observations | Per-area detailed observations with thermal data |
| 3 | Probable Root Cause | Evidence-based root causes |
| 4 | Severity Assessment | Issue severity table with reasoning |
| 5 | Recommended Actions | Prioritized action items (Immediate/Short/Long-term) |
| 6 | Additional Notes | Conflicts, contextual info |
| 7 | Missing or Unclear Information | Data gaps identified |

---

## 🗂️ Project Structure

```
ai_ddr_generator/
│
├── data/                       # Sample PDFs (place here for testing)
│   ├── inspection_report.pdf
│   └── thermal_report.pdf
│
├── src/                        # Core pipeline modules
│   ├── __init__.py
│   ├── pdf_parser.py           # PyMuPDF text + image extraction
│   ├── chunking.py             # Sliding window text chunking
│   ├── embedding.py            # Gemini embedding-001 API
│   ├── vector_store.py         # FAISS IndexFlatIP with cosine similarity
│   ├── retriever.py            # RAGRetriever with multi-query support
│   ├── rag_pipeline.py         # Orchestration: parse→chunk→embed→index
│   └── ddr_generator.py        # Gemini 1.5 Pro DDR generation
│
├── frontend/
│   └── app.py                  # Streamlit UI
│
├── prompts/
│   └── ddr_prompt.txt          # LLM prompt template
│
├── output/                     # Generated DDR reports saved here
│
├── .env.example                # API key template
├── requirements.txt
└── README.md
```

---

## ⚙️ Installation

### 1. Clone or download the project

```bash
cd ai_ddr_generator
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
# or
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your API key

```bash
cp .env.example .env
# Edit .env and add your Google Gemini API key:
# GOOGLE_API_KEY=AIza...
```

Get your API key from: https://makersuite.google.com/app/apikey

---

## 🚀 Running the App

```bash
streamlit run frontend/app.py
```

The app will open at `http://localhost:8501`

---

## 📝 Example Workflow

1. Open the Streamlit app in your browser
2. Enter your Gemini API key in the sidebar
3. Upload the **Inspection Report PDF** in the left panel
4. Upload the **Thermal Images Report PDF** in the right panel
5. Click **"⚡ GENERATE DDR REPORT"**
6. Watch the pipeline run:
   - Text extraction (~5 seconds)
   - Embedding generation (~10-20 seconds depending on PDF size)
   - FAISS indexing (instant)
   - RAG retrieval + LLM generation (~15-30 seconds)
7. View the structured DDR report in the results tab
8. Download the report as a `.txt` file
9. Browse extracted images in the "Extracted Images" tab

---

## 🔧 Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Chunk Size | 800 chars | Size of each text chunk |
| Chunk Overlap | 150 chars | Overlap between consecutive chunks |
| Retrieval Top-K | 5 | Chunks retrieved per query |
| Max Images | 15 | Maximum images extracted per PDF |
| Model | gemini-1.5-pro | LLM for DDR generation |
| Embedding Model | embedding-001 | Gemini embedding model |
| Temperature | 0.1 | Low = factual, consistent output |

---

## 🧩 Tech Stack

| Component | Technology |
|-----------|------------|
| PDF Parsing | PyMuPDF (fitz) |
| Embeddings | Google Gemini embedding-001 |
| Vector DB | FAISS (IndexFlatIP) |
| LLM | Google Gemini 1.5 Pro |
| RAG Framework | Custom (langchain-compatible) |
| Frontend | Streamlit |
| Image Processing | Pillow |
| Config | python-dotenv |

---

## ⚠️ Important Notes

- **No hallucinations**: The system is designed to only use information from the uploaded PDFs. Missing data will appear as "Not Available" in the report.
- **API costs**: Each run uses Gemini API calls for embedding (per chunk) and generation (1 call). Monitor your API usage.
- **PDF quality**: Better quality PDFs with more text content will produce more accurate DDR reports.
- **Image extraction**: Some PDFs may not have extractable embedded images if images are rendered as page backgrounds.

---

## 📄 License

This project is provided as a production-ready template for building AI-powered inspection report systems.
