import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from src.pdf_generator import generate_ddr_pdf
from PIL import Image

dummy_text = """
INSPECTION DETAILS
Customer Name / Property: Test Prop
Case No: 123
Date of Inspection: 2023-10-10
Time of Inspection: 10:00
Inspected By: Test Insp
Type of Structure: RCC
Number of Floors: 2
Year of Construction: 2020
Age of Building: 3
Previous Structure Audit Done: No
Previous Repairs: No

==========
SECTION 1: INTRODUCTION
1.1 BACKGROUND
Text
1.2 OBJECTIVE OF THE HEALTH ASSESSMENT
Text
1.3 SCOPE OF WORK
Text
==========
SECTION 2: GENERAL INFORMATION AND SUMMARY
Summ
==========
SECTION 3: VISUAL OBSERVATION AND READINGS
AREA 1: Test Area
Negative Side (Impacted Location): N/A
Positive Side (Source Location): N/A
Thermal Reading: N/A
Leakage Pattern: N/A
[IMAGE: Test_Page1_Index0]
==========
SECTION 4: STRUCTURAL CONDITION ASSESSMENTS
4.1 TERRACE CONDITION ASSESSMENT
1. Component: Good - Remarks
==========
SECTION 5: ANALYSIS & SUGGESTIONS
5.1 BATHROOM AND BALCONY GROUTING TREATMENT
Treatment
==========
SECTION 6: SUMMARY TABLE AND ACTIONS
OVERALL SEVERITY: Low
SUMMARY OF IMPACTED AREAS VS EXPOSED SOURCES
Priority | Impacted | N/A | Source
PRIORITY ACTIONS
IMMEDIATE:
- Act1
SHORT-TERM:
- Act2
LONG-TERM:
- Act3
==========
SECTION 7: LIMITATION AND PRECAUTION NOTE
7.1 ADDITIONAL OBSERVATIONS
Obs
7.2 MISSING OR UNCLEAR INFORMATION
None
"""

try:
    img = Image.new('RGB', (100, 100), color = 'red')
    images = [{"image": img, "source": "Test", "page": 1}]
    pdf_bytes = generate_ddr_pdf(dummy_text, metadata={}, images=images)
    print("SUCCESS, generated", len(pdf_bytes), "bytes")
except Exception as e:
    import traceback
    traceback.print_exc()
