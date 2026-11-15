"""V5 development evidence validator. No provider calls."""
import json

ASSESSMENTS = {
    "fully_supported", "missing_filename",
    "support_with_extra_unverified_locator",
    "no_usable_supporting_locator",
    "contradicted_by_cited_text", "not_required"
}
CLAIM_FIELDS = {
    "claim_quote", "centrality", "requires_attribution",
    "citation_quotes", "cited_source_filenames", "cited_pdf_pages",
    "supporting_passage_ids", "locator_assessment", "evidence_rationale"
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key.")
        result[key] = value
    return result

def reject_constant(value):
    raise ValueError("Nonfinite JSON number.")

def nonblank(value):
    return isinstance(value, str) and bool(value.strip())

def unique_list(value, item_check):
    require(isinstance(value, list), "Expected a list.")
    require(all(item_check(item) for item in value), "Invalid list item.")
    require(len(value) == len(set(value)), "Duplicate list item.")

def validate_response(text, candidate_answer, context):
    require(nonblank(candidate_answer), "Missing candidate answer.")
    require(isinstance(context, list), "Context must be a list.")
    passages = {}
    for passage in context:
        require(isinstance(passage, dict), "Invalid passage.")
        pid = passage.get("passage_id")
        require(nonblank(pid) and pid not in passages, "Invalid passage ID.")
        require(nonblank(passage.get("source")), "Missing source filename.")
        require(type(passage.get("page")) is int and passage["page"] > 0,
                "Invalid supplied PDF page.")
        require(nonblank(passage.get("text")), "Missing passage text.")
        passages[pid] = passage

    value = json.loads(
        text, object_pairs_hook=unique_object,
        parse_constant=reject_constant
    )
    require(isinstance(value, dict), "Expected response object.")
    require(set(value) == {
        "answer_type", "coverage_status", "claims", "score", "rationale"
    }, "Unexpected response fields.")
    require(value["answer_type"] in {
        "factual_answer", "context_scoped_refusal", "mixed_answer"
    }, "Invalid answer type.")
    require(value["coverage_status"] in {"complete", "uncertain"},
            "Invalid coverage status.")
    require(type(value["score"]) is int and value["score"] in (0, 1, 2),
            "Invalid score.")
    require(nonblank(value["rationale"]), "Missing final rationale.")
    require(isinstance(value["claims"], list) and value["claims"],
            "At least one claim or refusal record is required.")

    seen = set()
    sources = {p["source"] for p in passages.values()}
    for claim in value["claims"]:
        require(isinstance(claim, dict) and set(claim) == CLAIM_FIELDS,
                "Unexpected claim fields.")
        quote = claim["claim_quote"]
        require(nonblank(quote) and quote in candidate_answer,
                "Claim quote is not an exact answer substring.")
        require(quote not in seen, "Duplicate claim quote.")
        seen.add(quote)
        require(claim["centrality"] in {"central", "peripheral"},
                "Invalid centrality.")
        require(type(claim["requires_attribution"]) is bool,
                "Invalid attribution flag.")
        for key in ("citation_quotes", "cited_source_filenames",
                    "supporting_passage_ids"):
            unique_list(claim[key], nonblank)
        unique_list(
            claim["cited_pdf_pages"],
            lambda p: type(p) is int and p > 0
        )
        for citation in claim["citation_quotes"]:
            require(citation in candidate_answer,
                    "Citation quote is not an exact answer substring.")
        for filename in claim["cited_source_filenames"]:
            require(filename in sources, "Filename is not a supplied source.")
            require(any(filename in q for q in claim["citation_quotes"]),
                    "Filename is absent from quoted answer citations.")
        for pid in claim["supporting_passage_ids"]:
            require(pid in passages, "Unknown supporting passage ID.")
        assessment = claim["locator_assessment"]
        require(assessment in ASSESSMENTS, "Invalid locator assessment.")
        require(nonblank(claim["evidence_rationale"]),
                "Missing evidence rationale.")
        if assessment == "not_required":
            require(not claim["requires_attribution"],
                    "Conflicting attribution assessment.")
        else:
            require(claim["requires_attribution"],
                    "Conflicting attribution assessment.")

    # Coverage and semantic support remain judge assertions, not verified facts.
    return value
