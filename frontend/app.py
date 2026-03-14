"""
app.py
------
AI DDR Generator - Streamlit Frontend
A professional interface for generating Detailed Diagnostic Reports
from inspection and thermal PDFs using RAG + Gemini.

Run with: streamlit run frontend/app.py
"""

import streamlit as st
import sys
import os
import tempfile
import time

# Add parent directory to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag_pipeline import RAGPipeline
from src.ddr_generator import generate_full_ddr


# ─────────────────────────────────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI DDR Generator",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');
    
    /* Root variables */
    :root {
        --primary: #1a1a2e;
        --accent: #e94560;
        --accent2: #0f3460;
        --surface: #16213e;
        --text: #eaeaea;
        --muted: #8892a4;
        --success: #00d4aa;
        --warning: #ffd166;
        --card-bg: rgba(22, 33, 62, 0.8);
        --border: rgba(233, 69, 96, 0.3);
    }

    /* Global */
    .stApp {
        background: linear-gradient(135deg, #0a0a1a 0%, #1a1a2e 50%, #0f3460 100%);
        font-family: 'DM Sans', sans-serif;
        color: var(--text);
    }
    
    /* Hide default Streamlit elements */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.5rem; max-width: 1400px; }
    
    /* Hero Header */
    .hero-header {
        background: linear-gradient(135deg, rgba(233,69,96,0.15) 0%, rgba(15,52,96,0.3) 100%);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
    }
    
    .hero-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(233,69,96,0.1) 0%, transparent 70%);
        border-radius: 50%;
    }
    
    .hero-title {
        font-family: 'Space Mono', monospace;
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #ffffff 0%, #e94560 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        line-height: 1.2;
    }
    
    .hero-subtitle {
        color: var(--muted);
        font-size: 0.95rem;
        margin-top: 0.5rem;
        font-weight: 300;
        letter-spacing: 0.5px;
    }
    
    .hero-badge {
        display: inline-block;
        background: rgba(233,69,96,0.2);
        border: 1px solid rgba(233,69,96,0.4);
        color: #e94560;
        font-family: 'Space Mono', monospace;
        font-size: 0.7rem;
        padding: 3px 10px;
        border-radius: 20px;
        margin-bottom: 0.8rem;
        letter-spacing: 1px;
    }
    
    /* Upload cards */
    .upload-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        backdrop-filter: blur(10px);
        transition: border-color 0.3s ease;
    }
    
    .upload-card:hover {
        border-color: rgba(233,69,96,0.6);
    }
    
    .upload-label {
        font-family: 'Space Mono', monospace;
        font-size: 0.75rem;
        color: #e94560;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    
    /* Metrics */
    .metric-row {
        display: flex;
        gap: 1rem;
        margin: 1rem 0;
    }
    
    .metric-card {
        flex: 1;
        background: rgba(15,52,96,0.5);
        border: 1px solid rgba(0,212,170,0.2);
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    
    .metric-value {
        font-family: 'Space Mono', monospace;
        font-size: 1.8rem;
        color: var(--success);
        font-weight: 700;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: var(--muted);
        margin-top: 0.2rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* DDR Output */
    .ddr-output {
        background: rgba(10, 10, 26, 0.9);
        border: 1px solid rgba(233,69,96,0.3);
        border-radius: 12px;
        padding: 2rem;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.9rem;
        line-height: 1.8;
        color: #d4d4d4;
        white-space: pre-wrap;
        max-height: 700px;
        overflow-y: auto;
    }
    
    .ddr-output::-webkit-scrollbar {
        width: 6px;
    }
    .ddr-output::-webkit-scrollbar-track {
        background: rgba(255,255,255,0.05);
    }
    .ddr-output::-webkit-scrollbar-thumb {
        background: rgba(233,69,96,0.5);
        border-radius: 3px;
    }
    
    /* Section header */
    .section-header {
        font-family: 'Space Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: var(--muted);
        border-bottom: 1px solid var(--border);
        padding-bottom: 0.5rem;
        margin-bottom: 1.2rem;
    }
    
    /* Status badges */
    .status-ready {
        background: rgba(0,212,170,0.15);
        border: 1px solid rgba(0,212,170,0.4);
        color: #00d4aa;
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.75rem;
        font-family: 'Space Mono', monospace;
        display: inline-block;
    }
    
    .status-waiting {
        background: rgba(255,209,102,0.15);
        border: 1px solid rgba(255,209,102,0.3);
        color: #ffd166;
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.75rem;
        font-family: 'Space Mono', monospace;
        display: inline-block;
    }
    
    /* Image gallery */
    .image-caption {
        font-family: 'Space Mono', monospace;
        font-size: 0.65rem;
        color: var(--muted);
        text-align: center;
        margin-top: 4px;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #e94560 0%, #c23152 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Space Mono', monospace !important;
        font-size: 0.8rem !important;
        letter-spacing: 1px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 700 !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(233,69,96,0.4) !important;
    }
    
    /* File uploader */
    [data-testid="stFileUploader"] {
        background: rgba(15,52,96,0.3) !important;
        border: 2px dashed rgba(233,69,96,0.3) !important;
        border-radius: 10px !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(10,10,26,0.95) !important;
        border-right: 1px solid var(--border) !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: var(--text) !important;
    }
    
    /* Progress */
    .stProgress > div > div {
        background-color: #e94560 !important;
    }
    
    /* Info/warning boxes */
    .stAlert {
        border-radius: 10px !important;
    }
    
    /* Text input for API key */
    .stTextInput > div > div > input {
        background: rgba(15,52,96,0.5) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
        font-family: 'Space Mono', monospace !important;
        font-size: 0.85rem !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialization
# ─────────────────────────────────────────────────────────────────────────────
if "pipeline" not in st.session_state:
    st.session_state.pipeline = None
if "ddr_text" not in st.session_state:
    st.session_state.ddr_text = None
if "pipeline_stats" not in st.session_state:
    st.session_state.pipeline_stats = None
if "extracted_images" not in st.session_state:
    st.session_state.extracted_images = []
if "ddr_pdf_bytes" not in st.session_state:
    st.session_state.ddr_pdf_bytes = None


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="font-family: 'Space Mono', monospace; font-size: 0.65rem; 
                letter-spacing: 2px; color: #e94560; text-transform: uppercase; 
                margin-bottom: 1rem;">
        ⚙️ Configuration
    </div>
    """, unsafe_allow_html=True)
    
    # API Key input
    api_key_input = st.text_input(
        "Google Gemini API Key",
        type="password",
        placeholder="AIza...",
        help="Get your key from https://makersuite.google.com/app/apikey",
        value=os.getenv("GOOGLE_API_KEY", "")
    )
    
    st.markdown("---")
    
    # Advanced settings
    st.markdown("""
    <div style="font-family: 'Space Mono', monospace; font-size: 0.65rem; 
                letter-spacing: 2px; color: #8892a4; text-transform: uppercase; 
                margin-bottom: 0.8rem;">
        Advanced Settings
    </div>
    """, unsafe_allow_html=True)
    
    chunk_size = st.slider("Chunk Size (chars)", 400, 1200, 800, 100,
                           help="Size of each text chunk for embedding")
    top_k = st.slider("Retrieval Top-K", 3, 10, 5,
                      help="Number of chunks retrieved per query")
    max_images = st.slider("Max Images to Extract", 5, 30, 15,
                           help="Maximum number of images to extract from PDFs")
    
    st.markdown("---")
    
    # Architecture overview
    st.markdown("""
    <div style="font-family: 'Space Mono', monospace; font-size: 0.65rem; 
                letter-spacing: 2px; color: #8892a4; text-transform: uppercase; 
                margin-bottom: 0.8rem;">
        Pipeline
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="font-size: 0.8rem; color: #8892a4; line-height: 2;">
    📄 PDF Upload<br>
    ↓<br>
    🔍 Text Extraction<br>
    ↓<br>
    ✂️ Chunking<br>
    ↓<br>
    🧠 Gemini Embeddings<br>
    ↓<br>
    🗄️ FAISS Index<br>
    ↓<br>
    🔎 RAG Retrieval<br>
    ↓<br>
    ✨ Gemini 1.5 Pro<br>
    ↓<br>
    📋 DDR Report
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    if st.session_state.pipeline and st.session_state.pipeline.is_ready():
        st.markdown('<span class="status-ready">● PIPELINE READY</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-waiting">○ AWAITING UPLOAD</span>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────────────────────────────────────

# Hero Header
st.markdown("""
<div class="hero-header">
    <div class="hero-badge">RAG + GEMINI 1.5 PRO</div>
    <h1 class="hero-title">🏗️ AI DDR Generator</h1>
    <p class="hero-subtitle">
        Upload your Inspection Report and Thermal Images Report — 
        the AI will extract, analyze, and generate a structured Detailed Diagnostic Report
        using Retrieval Augmented Generation.
    </p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Upload Section
# ─────────────────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="section-header">01 — Inspection Report</div>', unsafe_allow_html=True)
    inspection_file = st.file_uploader(
        "Upload Inspection PDF",
        type=["pdf"],
        key="inspection_upload",
        help="Upload the property inspection report PDF"
    )
    if inspection_file:
        st.success(f"✅ {inspection_file.name} ({inspection_file.size / 1024:.1f} KB)")

with col2:
    st.markdown('<div class="section-header">02 — Thermal Images Report</div>', unsafe_allow_html=True)
    thermal_file = st.file_uploader(
        "Upload Thermal Report PDF",
        type=["pdf"],
        key="thermal_upload",
        help="Upload the thermal imaging report PDF"
    )
    if thermal_file:
        st.success(f"✅ {thermal_file.name} ({thermal_file.size / 1024:.1f} KB)")


# ─────────────────────────────────────────────────────────────────────────────
# Process Button
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])

with col_btn2:
    generate_btn = st.button(
        "⚡ GENERATE DDR REPORT",
        disabled=(inspection_file is None or thermal_file is None or not api_key_input),
        help="Upload both PDFs and enter your API key to generate the DDR"
    )
    
    if not api_key_input:
        st.caption("⚠️ Enter your Google Gemini API key in the sidebar")
    elif inspection_file is None or thermal_file is None:
        st.caption("⚠️ Upload both PDF files to proceed")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Execution
# ─────────────────────────────────────────────────────────────────────────────
if generate_btn and inspection_file and thermal_file and api_key_input:
    
    # Save uploaded files to temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        inspection_path = os.path.join(tmpdir, "inspection_report.pdf")
        thermal_path = os.path.join(tmpdir, "thermal_report.pdf")
        image_dir = os.path.join(tmpdir, "images")
        
        with open(inspection_path, "wb") as f:
            f.write(inspection_file.getbuffer())
        with open(thermal_path, "wb") as f:
            f.write(thermal_file.getbuffer())
        
        # ── Step 1: Build RAG Pipeline ──────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="section-header">Processing Pipeline</div>', unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        pipeline_steps = [
            (0.1, "📄 Extracting text and images from PDFs..."),
            (0.3, "✂️ Chunking extracted text..."),
            (0.5, "🧠 Generating Gemini embeddings..."),
            (0.75, "🗄️ Building FAISS vector index..."),
            (0.9, "🔎 Retrieving relevant context..."),
            (1.0, "✨ Generating DDR with Gemini 1.5 Pro..."),
        ]
        
        try:
            # Build pipeline
            status_text.markdown("📄 **Extracting text and images from PDFs...**")
            progress_bar.progress(0.1)
            
            pipeline = RAGPipeline(api_key=api_key_input)
            
            def progress_callback(step, total, message):
                progress = step / total
                progress_bar.progress(min(progress * 0.85, 0.85))
                status_text.markdown(f"**{message}**")
            
            stats = pipeline.process_pdfs(
                inspection_pdf_path=inspection_path,
                thermal_pdf_path=thermal_path,
                image_output_dir=image_dir,
                progress_callback=progress_callback
            )
            
            st.session_state.pipeline = pipeline
            st.session_state.pipeline_stats = stats
            st.session_state.extracted_images = pipeline.extracted_images.copy()
            
            # ── Step 2: Generate DDR ──────────────────────────────────────
            progress_bar.progress(0.9)
            status_text.markdown("✨ **Generating DDR with Gemini 1.5 Pro...**")
            
            # Find prompt template
            prompt_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "prompts", "ddr_prompt.txt"
            )
            
            result = generate_full_ddr(
                retriever=pipeline.get_retriever(),
                api_key=api_key_input,
                prompt_template_path=prompt_path if os.path.exists(prompt_path) else None,
                save_output=False,
                images=st.session_state.extracted_images
            )
            
            st.session_state.ddr_text = result["ddr_text"]

            # Generate PDF bytes in memory
            try:
                from src.pdf_generator import generate_ddr_pdf
                st.session_state.ddr_pdf_bytes = generate_ddr_pdf(
                    result["ddr_text"], 
                    images=st.session_state.extracted_images
                )
            except Exception as pdf_err:
                import traceback
                with open("error_log.txt", "w") as f:
                    f.write(traceback.format_exc())
                st.session_state.ddr_pdf_bytes = None
                st.warning(f"PDF generation note: {pdf_err}")
            
            progress_bar.progress(1.0)
            status_text.markdown("✅ **DDR Report generated successfully!**")
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ Pipeline Error: {str(e)}")
            st.exception(e)


# ─────────────────────────────────────────────────────────────────────────────
# Results Display
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.ddr_text:
    st.markdown("---")
    
    # Stats row
    if st.session_state.pipeline_stats:
        stats = st.session_state.pipeline_stats
        
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        
        with col_s1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats.get('num_chunks', 0)}</div>
                <div class="metric-label">Text Chunks</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_s2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats.get('num_embeddings', 0)}</div>
                <div class="metric-label">Embeddings</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_s3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats.get('num_images', 0)}</div>
                <div class="metric-label">Images Found</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_s4:
            ddr_words = len(st.session_state.ddr_text.split())
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{ddr_words}</div>
                <div class="metric-label">Report Words</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # DDR Report Output
    tab_ddr, tab_images = st.tabs(["📋 DDR Report", "🖼️ Extracted Images"])
    
    with tab_ddr:
        st.markdown('<div class="section-header">Generated Detailed Diagnostic Report</div>', unsafe_allow_html=True)
        
        # Download buttons
        col_dl1, col_dl2, col_dl3 = st.columns([2, 1, 1])
        with col_dl2:
            st.download_button(
                label="⬇️ Download TXT",
                data=st.session_state.ddr_text,
                file_name="detailed_diagnostic_report.txt",
                mime="text/plain",
            )
        with col_dl3:
            pdf_bytes = st.session_state.get("ddr_pdf_bytes")
            if pdf_bytes:
                st.download_button(
                    label="📄 Download PDF",
                    data=pdf_bytes,
                    file_name="detailed_diagnostic_report.pdf",
                    mime="application/pdf",
                )
            else:
                st.button("📄 PDF N/A", disabled=True)
        
        # Display the report
        st.markdown(
            f'<div class="ddr-output">{st.session_state.ddr_text}</div>',
            unsafe_allow_html=True
        )
    
    with tab_images:
        st.markdown('<div class="section-header">Extracted Images from PDFs</div>', unsafe_allow_html=True)
        
        images = st.session_state.extracted_images
        
        if images:
            st.caption(f"Showing {len(images)} images extracted from both PDFs")
            
            # Display images in a grid
            cols_per_row = 4
            for i in range(0, len(images), cols_per_row):
                img_cols = st.columns(cols_per_row)
                for j, img_data in enumerate(images[i:i + cols_per_row]):
                    with img_cols[j]:
                        try:
                            pil_img = img_data["image"]
                            source = img_data.get("source", img_data.get("ext", ""))
                            page = img_data.get("page", "?")
                            
                            st.image(
                                pil_img,
                                use_column_width=True,
                            )
                            st.markdown(
                                f'<div class="image-caption">Page {page} · {img_data.get("source", "PDF")}</div>',
                                unsafe_allow_html=True
                            )
                        except Exception:
                            st.markdown(
                                '<div style="text-align:center; color:#8892a4; '
                                'font-size:0.75rem; padding:2rem; border:1px dashed #333; '
                                'border-radius:8px;">Image Not Available</div>',
                                unsafe_allow_html=True
                            )
        else:
            st.markdown("""
            <div style="text-align:center; padding:3rem; color:#8892a4;">
                <div style="font-size:2rem; margin-bottom:1rem;">🖼️</div>
                <div>No images extracted from the PDFs</div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Empty State
# ─────────────────────────────────────────────────────────────────────────────
elif not generate_btn:
    st.markdown("""
    <div style="text-align:center; padding:3rem 2rem; 
                background:rgba(22,33,62,0.4); border-radius:16px; 
                border:1px dashed rgba(233,69,96,0.2); margin-top:1rem;">
        <div style="font-size:3rem; margin-bottom:1rem;">📊</div>
        <div style="font-family:'Space Mono',monospace; font-size:1rem; 
                    color:#eaeaea; margin-bottom:0.5rem;">
            Ready to Generate Your DDR
        </div>
        <div style="color:#8892a4; font-size:0.85rem; max-width:500px; margin:0 auto;">
            Upload your Inspection Report PDF and Thermal Images Report PDF above,
            enter your Gemini API key in the sidebar, then click Generate.
        </div>
        <br>
        <div style="display:flex; gap:2rem; justify-content:center; flex-wrap:wrap; margin-top:1rem;">
            <div style="color:#8892a4; font-size:0.8rem;">✦ RAG-powered retrieval</div>
            <div style="color:#8892a4; font-size:0.8rem;">✦ Gemini 1.5 Pro reasoning</div>
            <div style="color:#8892a4; font-size:0.8rem;">✦ FAISS vector search</div>
            <div style="color:#8892a4; font-size:0.8rem;">✦ No hallucinations policy</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
