# Calibrated LLM Evaluation & Quality Gates

A reproducible evaluation harness for checking whether an LLM judge applies a citation-support rubric to supplied PDF excerpts. Built by Getamesay Zegeye as an extension of a multi-PDF RAG evaluation project.

**Current milestone: verified descriptive evaluation. The V5 judge is not promoted; original acceptance remains BLOCKED.**

The project began with five answer-quality criteria: correctness, completeness, groundedness, citation support and appropriate abstention. The subsequent judge-development work focuses on citation support. It does not establish a validated judge for all five criteria.

## What it does

- Keeps calibration, development and fresh-case evaluation artifacts distinct.
- Binds source PDFs, extracted pages, exact excerpts, prompts and candidate configurations with hashes.
- Excludes human scores, reference answers and answerability labels from judge messages.
- Requires structured evidence: quoted claims and citations, filenames, page numbers, supporting passage IDs and a proposed score.
- Checks quoted text, citation fields, supported page notation and score/evidence consistency offline.
- Preserves raw responses and attempt records before accepting or rejecting a result.
- Enforces fixed settings, request pacing, bounded retries and explicit retry eligibility.
- Reports original-reference agreement separately from guided post-run self-review.
- Separates artifact integrity from the protocol-based promotion decision.

## Results

| Measure | Frozen-reference descriptive result |
|---|---:|
| Planned / excluded / included cases | 30 / 2 / 28 |
| Valid and internally consistent responses | 28/28 |
| Exact agreement | 19/28 (67.9%) |
| Mean absolute score error | 0.3929 |
| Unweighted Cohen kappa, judge versus one reviewer | 0.5154 |
| Recorded SDK invocations / provider-error attempts | 29 / 1 |
| Candidate promoted | No |

Ten guided post-run amendment records, including a rationale-only correction, produced an **exploratory comparison of 27/28 (96.4%)**. The model responses did not change. This is a reference-revision result, not evidence of model improvement. Original labels and the 19/28 report remain preserved. FRESH-V5-028 remains disputed.

Offline integrity passed on the author's local project, including verification of the exploratory amendment records. No independent second reviewer was available; independent human agreement has not been measured.

## Evaluation design

Thirty assistant-authored controlled examples were planned across five new document families: NASA solar-system lithographs, FEMA preparedness guidance, an EPA radon guide, a NOAA spotter guide and a USGS publication record. Each case supplies one exact excerpt. These are controlled citation examples, not sampled live RAG answers.

The USGS PDF is a generated webpage conversion containing a publication record and abstract, not the full booklet. Its PDF page numbers refer to that conversion. Domain content is used as evaluation material, not as current operational guidance.

The registered primary evaluation was blocked before judge execution after two requests for case-specific guidance excluded FRESH-V5-001 and FRESH-V5-003. The remaining 28 cases were evaluated descriptively. The original protocol was not relaxed to manufacture an acceptance pass.

## Citation decision rules

Scores use the frozen draft rubric, not a new rubric introduced by this README:

| Score | Citation-support interpretation |
|---|---|
| 2 | Required claims have the exact source filename and supporting supplied PDF page; a brief scoped refusal can qualify without citations if it adds no factual explanation requiring attribution. |
| 1 | Supporting attribution is traceable but misses the filename, or valid support is accompanied by extra unverified page references. |
| 0 | A central claim has no usable supporting locator, its sole cited page is unsupported in the supplied context, or cited evidence contradicts it. |

Finding a fact elsewhere in context does not repair the answer's wrong citation. Context-header filenames cannot be credited as filenames written in the candidate answer. Semantic support and full claim coverage still require judgment.

## Reproduce offline

Run from the Windows project root after installing the separately supplied artifact packages and preserving their expected paths:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\data\citation_v5_offline_quality_checks_v1\tests -v

.\.venv\Scripts\python.exe `
  .\data\citation_v5_offline_quality_checks_v1\run_checks.py `
  --project-root .
```

Expected current outcome: `Offline integrity: PASS`, `Promotion gate: BLOCKED`, `Original agreement: 19/28`. With the complete local amendment files installed, post-run status is `VERIFIED_EXPLORATORY_ONLY`.

```powershell
.\.venv\Scripts\python.exe `
  .\data\citation_v5_offline_quality_checks_v1\run_checks.py `
  --project-root . --mode promotion
```

Promotion mode exits 2 because the gate remains blocked. An integrity-only exit code 0 is not quality approval. These commands make no API requests. The optional GitHub Actions file is a template, not evidence that hosted CI has run.

## Required artifact layout

```text
data/
  citation_candidate_v5_freeze_v1/
  citation_v5_fresh_sources_v1/
  citation_v5_fresh_review_v1/
  citation_v5_descriptive_freeze_v1/
  citation_v5_descriptive_runner_v1/
  citation_v5_descriptive_results_v1/
  citation_v5_descriptive_report_v1/
  citation_v5_descriptive_report_local_v1/
  citation_v5_offline_quality_checks_v1/
```

The verification chain also uses the original protocol and checkpoint files. Optional exploratory verification requires `citation_v5_postrun_amendments_v1/` and `citation_v5_postrun_comparison_v2.json`. This documentation package contains documentation only; it does not bundle the full reproducibility tree.

## Limitations and status

One reviewer supplied the references. Guided post-run changes are not independent adjudication. The small curated set contains correlated cases within document families. Hashes detect changes against bindings; they are not independent signatures. Structural checks cannot prove semantic correctness, claim coverage or absence of all prompt leakage. Bias/invariance testing and validated evaluation across all five answer-quality criteria remain future work.

The project demonstrates an auditable evaluation workflow and a gate that retains a failed acceptance state. It does not demonstrate production-ready automated grading.

See [the technical case study](docs/TECHNICAL_CASE_STUDY.md) for design decisions, failures and lessons.
