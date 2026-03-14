import re

test_text = """1.1 BACKGROUND
This report details the findings.
1.2 OBJECTIVE OF THE HEALTH ASSESSMENT
INTRODUCTION
1.1 BACKGROUND
This report details the findings.
1.2 OBJECTIVE OF THE HEALTH ASSESSMENT
The primary objective.
1.3 SCOPE OF WORK
The scope of work included a visual examination.
==========
1.3 SCOPE OF WORK
INTRODUCTION
1.1 BACKGROUND
This report details the findings.
1.2 OBJECTIVE OF THE HEALTH ASSESSMENT
The primary objective.
1.3 SCOPE OF WORK
The scope of work included a visual examination.
==========
"""

def _deduplicate_subsections(text: str) -> str:
    # Pattern for sub-section headers like "1.1 BACKGROUND", "1.2 OBJECTIVE..."
    subsection_pattern = re.compile(
        r"(\d+\.\d+\s+[A-Z][A-Z\s&]+?)(?=\n)", re.MULTILINE
    )

    matches = list(subsection_pattern.finditer(text))
    if not matches:
        return text

    # Find duplicate sub-section headers
    seen_headers = {}
    ranges_to_remove = []

    for m in matches:
        header = re.sub(r"\s+", " ", m.group(1).strip().upper())
        if header in seen_headers:
            # mark the range from this header to the next header or end
            start = m.start()
            
            # Find next sub-section header or section divider after this one
            next_boundary = len(text)
            
            # Find next subsection
            for other_m in matches:
                if other_m.start() > start and other_m != m:
                    next_boundary = other_m.start()
                    break
            
            # Find next section divider
            divider_match = re.search(r"={5,}", text[start:])
            if divider_match:
                divider_pos = start + divider_match.start()
                next_boundary = min(next_boundary, divider_pos)

            # NOTE: this logic removes the dup header but leaves junk text BEFORE it if there's any.
            # E.g. "INTRODUCTION\n1.1 BACKGROUND" -> "INTRODUCTION\n" is left behind.
            ranges_to_remove.append((start, next_boundary))
        else:
            seen_headers[header] = m.start()

    # Remove ranges in reverse order to preserve positions
    result = text
    for start, end in sorted(ranges_to_remove, reverse=True):
        result = result[:start] + result[end:]

    return result

print("ORIGINAL:")
print(test_text)
print("\nDEDUPED:")
print(_deduplicate_subsections(test_text))
