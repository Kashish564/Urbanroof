import os, sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.ddr_generator import _robust_deduplicate

test_text = """1.1 BACKGROUND
This report details the findings of a structural inspection and thermal analysis conducted on Flat No. 103. The inspection was
performed on 27.09.2022 by Krushna & Mahesh.
1.2 OBJECTIVE OF THE HEALTH ASSESSMENT
INTRODUCTION
1.1 BACKGROUND
This report details the findings of a structural inspection and thermal analysis conducted on Flat No. 103. The inspection was
performed on 27.09.2022 by Krushna & Mahesh.
1.2 OBJECTIVE OF THE HEALTH ASSESSMENT
The primary objective of this assessment is to identify and diagnose any structural defects, water ingress issues, and related
problems within the property, utilizing both visual inspection and thermal imaging techniques.
1.3 SCOPE OF WORK
The scope of work included a visual examination of various areas within Flat No. 103, focusing on dampness, tile joint integrity, and
external wall conditions. Thermal imaging was used to detect temperature anomalies that may indicate moisture or other subsurface
issues.
==========
1.3 SCOPE OF WORK
INTRODUCTION
1.1 BACKGROUND
This report details the findings of a structural inspection and thermal analysis conducted on Flat No. 103. The inspection was
performed on 27.09.2022 by Krushna & Mahesh.
1.2 OBJECTIVE OF THE HEALTH ASSESSMENT
The primary objective of this assessment is to identify and diagnose any structural defects, water ingress issues, and related
problems within the property, utilizing both visual inspection and thermal imaging techniques.
1.3 SCOPE OF WORK
The scope of work included a visual examination of various areas within Flat No. 103, focusing on dampness, tile joint integrity, and
external wall conditions. Thermal imaging was used to detect temperature anomalies that may indicate moisture or other subsurface
issues.
==========
"""

print("--- ORIGINAL ---")
print(test_text)
print("--- DEDUPED ---")
print(_robust_deduplicate(test_text))
