"""Quick test of enhanced pipeline components."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.chunking import chunk_text, chunk_documents, _classify_section
from src.ddr_generator import _post_process_ddr, _validate_output

# Test section-aware chunking
test_text = "--- Page 1 ---\nINSPECTION DETAILS\nCustomer Name: Test Property\nCase No: 12345\n\n--- Page 2 ---\nTHERMAL ANALYSIS\nTemperature reading: 28.5C delta = 3.2C\nHotspot detected in bathroom ceiling\n\n--- Page 3 ---\nAREA 1: Master Bedroom\nWater stains on wall\nDampness level: High\n\nAREA 2: Kitchen\nTile hollowness observed\n"

chunks = chunk_text(test_text, chunk_size=800)
print(f"Chunks created: {len(chunks)}")
for i, c in enumerate(chunks):
    sec_type = _classify_section(c)
    print(f"  Chunk {i}: section_type={sec_type}, len={len(c)}")

assert len(chunks) > 0, "Chunking produced zero chunks"

# Test section classification
assert _classify_section("INSPECTION DETAILS Customer Name") == "inspection_metadata"
assert _classify_section("Thermal reading temperature 28C") == "thermal_reading"
assert _classify_section("RCC column beam condition") == "structural"
print("Section classification: PASSED")

# Test post-processing
raw_ddr = "## **INSPECTION DETAILS**\nCustomer Name: Test\n=====\nSECTION 1: INTRODUCTION\nText\n==========\nSECTION 2: GENERAL INFORMATION AND SUMMARY\nSummary\n==========\nSECTION 3: VISUAL OBSERVATION AND READINGS\nDetails\n==========\nSECTION 4: STRUCTURAL CONDITION ASSESSMENTS\nAssessment\n==========\nSECTION 5: ANALYSIS & SUGGESTIONS\nFixes\n==========\nSECTION 6: SUMMARY TABLE AND ACTIONS\nOVERALL SEVERITY: Moderate\n==========\nSECTION 7: LIMITATION AND PRECAUTION NOTE\nNotes"

cleaned = _post_process_ddr(raw_ddr)
report = _validate_output(cleaned)
print(f"Sections found: {len(report['sections_found'])}/{len(report['sections_found']) + len(report['sections_missing'])}")
print(f"Missing: {report['sections_missing']}")
assert "END OF DETAILED REPORT" in cleaned, "Missing END marker"
assert len(report["sections_missing"]) == 0, f"Missing sections: {report['sections_missing']}"
assert "**" not in cleaned, "Markdown artifacts not removed"
print("Post-processing: PASSED")

# Test chunk_documents with section_type metadata
docs = [
    {"text": "INSPECTION DETAILS\nCustomer: Test\nDate: 2024-01-01", "source": "Inspection_Report"},
    {"text": "Thermal reading delta 3.2C hotspot bathroom", "source": "Thermal_Report"},
]
tagged_chunks = chunk_documents(docs, chunk_size=800)
assert all("section_type" in c for c in tagged_chunks), "Missing section_type metadata"
print(f"Tagged chunks: {len(tagged_chunks)} — all have section_type")

print("\n=== ALL TESTS PASSED ===")
