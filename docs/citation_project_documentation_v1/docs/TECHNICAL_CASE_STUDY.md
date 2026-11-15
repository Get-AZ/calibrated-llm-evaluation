# Technical case study: citation-support judge evaluation

**Author:** Getamesay Zegeye  
**Milestone:** V5 descriptive evaluation with offline verification  
**Decision:** Candidate not promoted; original acceptance BLOCKED

## Problem

A RAG answer can state a correct fact while citing the wrong PDF page. An LLM judge can also mistakenly credit a filename from a retrieval header even when the answer cites only a passage ID. A score-only judge response makes these mistakes difficult to inspect and constrain.

The engineering goal was to build a traceable evaluation process: define a rubric, collect human references, preserve exact inputs, measure agreement, diagnose failures and prevent a candidate from advancing when acceptance conditions are unmet.

## Approach

Initial calibration covered five criteria on YOLO and Transformer answers. Citation support required further focused work. Synthetic calibration and regression examples clarified missing filenames, unsupported sole locators, mixed page citations and context-scoped refusals.

Development then exposed two recurring problems. Some judge rationales claimed an exact filename was present when it existed only in context. Others awarded partial credit to a sole wrong-page citation despite instructions requiring 0. An instruction-only V4 revision matched guided references on 4/6 exposed development cases. V5 added an evidence response contract and matched 6/6 on the same exposed set. Those development figures were diagnostic, not held-out performance.

V5 changed both the response format and the output budget, from 2,048 to 4,096 tokens. Improvement cannot be attributed to one isolated change.

## Evidence contract

The response contains answer type, coverage status, claim records, a score and rationale. Claim records include exact answer quotes, exact citation quotes, cited filenames/pages, supporting passage IDs and a locator assessment.

Three offline layers check the response:

1. A structural validator rejects unexpected fields, duplicate JSON keys, nonfinite numbers, invalid score types, invented answer quotes, unknown passage IDs and filenames improperly credited from context.
2. A page validator checks supported explicit page notation against the pages reported in the response. Unsupported formats and ranges require review rather than silent interpretation.
3. A scoring consistency check compares the proposed score with reported evidence assessments. It preserves inconsistent responses instead of correcting or retrying them.

These checks constrain recorded evidence. The model still judges semantic support and claim coverage; a structurally valid response can be semantically wrong.

## Reproducibility and execution controls

The pipeline binds source bytes, page exports, character slices, case inputs, candidate instructions, response schema and configuration with hashes. Human labels remain outside judge messages. Frozen reviews and post-run amendments are stored separately.

Execution uses the recorded model `gemini-3.5-flash-lite`, Google SDK 3.3.0, temperature 0 and JSON schema output. Transport controls include a 120-second timeout, one SDK attempt per invocation and at least 60 seconds between requests. Only recorded HTTP 429/503 errors permit explicit retries, with 120/300-second backoff and at most three attempts per case. Interrupted or completed malformed responses are not silently resubmitted.

Raw responses are retained before validation. Cached valid results can be reused without new provider requests. Request and response hashes, attempt histories, pacing and retry eligibility are audited offline.

## Fresh-case evaluation

The candidate was frozen before construction of 30 cases across five new document families. Cases were assistant-authored, source-based examples with controlled defects; they were not live RAG traffic. One reviewer provided scores without judge outputs available at that stage.

Two guidance requests excluded cases from the primary test. The original acceptance attempt therefore remained blocked before execution. Rather than lower the requirements, the project retained a descriptive role for the 28 reviewed cases.

| Result | Value |
|---|---:|
| Valid and internally consistent | 28/28 |
| Exact agreement with original references | 19/28 (67.9%) |
| Numeric disagreements | 9 |
| Mean absolute score error | 0.3929 |
| Unweighted Cohen kappa | 0.5154 |
| Recorded SDK invocations | 29 |
| Provider-error attempts / retries | 1 / 1 |

The minimum recorded request-start gap was 62.291121 seconds. One 503 retry followed a recorded 322.320528-second interval, exceeding the required first backoff. These are audit-log observations, not independent network measurements.

Agreement is not verified accuracy. A shared human/judge decision can violate the rubric; a disagreement can originate in a human reference rather than a judge error.

## Reference-quality findings

Post-run review found several human labels treating sole wrong-page citations as partial credit. It also found mismatched rationales: a radon-unit answer had a map-year rationale, and a neighbor-test answer had a radon-unit rationale. These findings illustrate why annotation integrity and semantic reference quality are different concerns.

Ten guided post-run amendment records were preserved without altering original labels. One corrected only a rationale. Comparing unchanged judge responses with the revised references yielded 27/28 (96.4%). This is an exploratory self-review comparison after outputs were visible, not independent agreement and not a new model evaluation.

Case FRESH-V5-028 remains disputed. The answer briefly states that the supplied passage does not quote an exact hourly rate. The rubric permits such a scoped refusal without citations when it adds no factual explanation. The reviewer retained score 0 after discussion; the judge recorded 2. Both records and the dispute flag remain visible.

## Gate outcome

Offline integrity passed, including local verification of the amendment records reported by the author. Promotion remained blocked by the original acceptance state, exclusions and unmet registered primary requirements. The integrity checker separates successful artifact verification from quality approval. Its promotion mode deliberately returns a blocked exit code for this fixed run.

No candidate was promoted. Post-run relabeling did not retrospectively restore an untouched acceptance test. A second reviewer was unavailable; the project explicitly reports that independent human agreement was not measured.

## Lessons and next work

Evidence-first output made judge reasoning easier to validate and audit, but it did not establish semantic reliability. Human references also need review controls: showing the current question, answer and excerpt beside the label reduces accidental rationale drift. Agreement metrics should retain their original denominator and reference version.

A future acceptance study should use a separately registered fresh set, resolve eligibility before execution, apply the same rubric consistently, and retain the blocked history. Independent review would strengthen reference quality if it becomes available. Bias/invariance tests and broader five-criterion validation remain uncompleted work; they should not be claimed as existing capabilities.
