"""Page checks for explicit page/p./pp. citation formats."""
import re
from citation_evidence_contract_v5 import validate_response, require

PAGE = re.compile(
    r"(?:\bPDF\s+pages?\b|\bpages?\b|\bpp?\.)\s*"
    r"(?P<numbers>\d+(?:\s*(?:,|\band\b)\s*\d+)*)",
    re.IGNORECASE
)

def extract_pages(citation_quotes):
    pages = set()
    for quote in citation_quotes:
        matches = list(PAGE.finditer(quote))
        require(matches, "Unsupported or missing explicit page notation.")
        for match in matches:
            tail = quote[match.end():].lstrip()
            require(not tail.startswith(("-", "\u2013", "\u2014")),
                    "Page ranges require review; not supported by this extractor.")
            require(not tail.startswith((",", "and ")),
                    "Incomplete or unsupported page list.")
            for number in re.findall(r"\d+", match.group("numbers")):
                page = int(number)
                require(page > 0, "Invalid cited PDF page.")
                pages.add(page)
    return pages

def validate_evidence_response(text, candidate_answer, context):
    value = validate_response(text, candidate_answer, context)
    for claim in value["claims"]:
        extracted = extract_pages(claim["citation_quotes"])
        require(extracted == set(claim["cited_pdf_pages"]),
                "Reported pages differ from quoted citation pages.")
    return value
