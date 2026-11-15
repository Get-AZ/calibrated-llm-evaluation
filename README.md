# Calibrated LLM Evaluation & Quality Gates

[![Calibrated LLM Evaluation cover: evidence validation and quality gates](https://getamesay-ml-cloud-ai.getgad-uss.chatgpt.site/assets/calibrated-llm-evaluation-cover.png)](https://getamesay-ml-cloud-ai.getgad-uss.chatgpt.site/#calibrated-llm-evaluation)

*Cover illustration: the latency claim is an example, not a measured project result.*

By Getamesay Zegeye

An auditable evaluation harness for scoring citation support against exact supplied PDF excerpts.

## Current status

V5 descriptive evaluation verified. Candidate not promoted. Original acceptance remains BLOCKED.

## Results

- Planned cases: 30; exclusions: 2; included cases: 28.
- Valid and internally consistent judge responses: 28/28.
- Original human-reference agreement: 19/28 (67.9%).
- Guided post-run reference comparison: 27/28 (96.4%).
- Judge responses were unchanged; revised-reference agreement is exploratory, not model improvement.
- Case FRESH-V5-028 remains disputed.
- One reviewer; independent human agreement was not measured.

## Implemented

Versioned rubrics, human annotations, frozen source and prompt bindings, structured evidence responses, offline validators, preserved raw responses, controlled retries, agreement reports and a separate promotion gate.

Offline integrity passed, including local verification of post-run amendments. Integrity PASS does not establish semantic accuracy or authorize promotion.

## Scope and limitations

Cases are assistant-authored controlled examples across five document families, not live RAG traffic. The USGS source is a converted publication record, not the full booklet.

This repository contains selected tools, tests and documentation. Local evaluation artifacts are excluded, so a fresh clone cannot reproduce the complete audit without those artifacts.

Structural validity does not prove semantic support or complete claim coverage. Bias testing and broader five-criterion validation remain future work. GitHub Actions passed 37 repository-only offline unit tests for commit bee8d80. Seven snapshot-dependent loader tests remain local. CI success does not establish semantic accuracy or promotion eligibility.

## Documentation

[Technical case study](docs/citation_project_documentation_v1/docs/TECHNICAL_CASE_STUDY.md)
