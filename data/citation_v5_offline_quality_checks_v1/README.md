# V5 offline quality checks

This package audits the fixed descriptive run without network requests, SDK calls, score repair, or label changes. A second reviewer is unavailable. Independent human agreement has not been measured.

Integrity PASS means the frozen files, saved responses, operational audit and reported counts verify. It does not mean the judge passed a quality gate. Promotion remains BLOCKED under the original protocol. Original agreement is 19/28; guided post-run agreement is 27/28 and is exploratory only. Case FRESH-V5-028 remains disputed.

## Windows use

Extract this ZIP into the project `data` folder. Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\data\citation_v5_offline_quality_checks_v1\tests -v
.\.venv\Scripts\python.exe .\data\citation_v5_offline_quality_checks_v1\run_checks.py --project-root .
```

The existing descriptive freeze, runner, raw results, original source bindings and report auditor package must be installed. Optional post-run verification requires the original local report, all ten amendment files, and comparison v2. If none are present, the tool explicitly reports `not_present`; this is not verification of the exploratory result.

To exercise the separate blocked gate:

```powershell
.\.venv\Scripts\python.exe .\data\citation_v5_offline_quality_checks_v1\run_checks.py --project-root . --mode promotion
```

Exit codes: 0 = integrity verified; 1 or traceback = verification failed; 2 = promotion blocked in promotion mode. Do not treat an integrity-only zero exit as promotion approval. Optional `--output NEW_PATH.json` saves a new summary and refuses overwrite.

## CI template

The workflow template is optional and is not installed automatically. It requires the same complete artifact tree on the CI machine. Do not publish source PDFs or review records merely to enable CI. No API key is required. The promotion job is expected to fail because acceptance is blocked.

## Limits

Hashes detect changes relative to recorded bindings; they are not independent signatures. The evidence validators check structure and internal consistency, not semantic truth or complete claim coverage. Post-run self-review cannot restore an untouched acceptance test or establish independent reviewer agreement. This fixed-run checker does not authorize future promotion.
