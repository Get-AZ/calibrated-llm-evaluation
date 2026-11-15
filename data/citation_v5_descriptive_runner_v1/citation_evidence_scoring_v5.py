"""Check score consistency with recorded evidence assessments.

This does not independently verify semantic support or claim coverage.
"""
from citation_evidence_pages_v5 import validate_evidence_response as validate_response

FAILURES = {
    "no_usable_supporting_locator",
    "contradicted_by_cited_text"
}
PARTIAL = {
    "missing_filename",
    "support_with_extra_unverified_locator"
}

def check_consistency(text, candidate_answer, context):
    value = validate_response(text, candidate_answer, context)
    claims = value["claims"]

    def outcome(status, reason, expected=None):
        return {
            "status": status,
            "recorded_score": value["score"],
            "expected_score_from_assessments": expected,
            "reason": reason,
            "semantic_support_verified": False,
            "claim_coverage_verified": False
        }

    if value["coverage_status"] != "complete":
        return outcome("needs_review", "Judge reports uncertain claim coverage.")

    # Require minimally coherent evidence records before aggregation.
    for claim in claims:
        assessment = claim["locator_assessment"]
        if assessment in {"fully_supported"} | PARTIAL:
            if not claim["citation_quotes"] or not claim["supporting_passage_ids"]:
                return outcome("needs_review", "Supporting attribution lacks evidence records.")
        if assessment in {"fully_supported", "support_with_extra_unverified_locator"}:
            if not claim["cited_source_filenames"] or not claim["cited_pdf_pages"]:
                return outcome("needs_review", "Assessment lacks required filename/page records.")
        if assessment == "missing_filename":
            if claim["cited_source_filenames"]:
                return outcome("needs_review", "Missing-filename assessment records a filename.")

    if any(c["centrality"] == "central"
           and c["locator_assessment"] in FAILURES for c in claims):
        expected = 0
    elif any(c["locator_assessment"] in FAILURES for c in claims):
        return outcome(
            "needs_review",
            "Peripheral unsupported attribution needs rubric-based review."
        )
    elif any(c["locator_assessment"] in PARTIAL for c in claims):
        expected = 1
    elif all(c["locator_assessment"] == "not_required" for c in claims):
        if value["answer_type"] != "context_scoped_refusal":
            return outcome("needs_review", "Attribution exemption needs review.")
        expected = 2
    else:
        expected = 2

    if value["score"] != expected:
        return outcome(
            "inconsistent",
            "Recorded score conflicts with recorded evidence assessments.",
            expected
        )
    return outcome(
        "consistent",
        "Score agrees with recorded assessments; their truth is not verified.",
        expected
    )
