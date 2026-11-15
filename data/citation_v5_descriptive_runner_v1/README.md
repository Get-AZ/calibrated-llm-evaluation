# Frozen V5 descriptive evaluation runner

Runs one of the 28 reviewed cases from `citation_v5_descriptive_freeze_v1`. FRESH-V5-001 and FRESH-V5-003 cannot execute. The original 30-case acceptance attempt remains BLOCKED. All outputs are descriptive only and cannot promote the candidate.

## Install and offline checks

Extract this folder into the project's `data` directory. From the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\data\citation_v5_descriptive_runner_v1\tests -v
.\.venv\Scripts\python.exe .\data\citation_v5_descriptive_runner_v1\run_descriptive.py --case FRESH-V5-002 --project-root .
```

The default dry run validates the snapshot and original project bindings, exact SDK version, fixed settings, prompt hashes and runner files. It makes no provider calls and creates no result files.

## Execute one case

Only after offline verification and dry run:

```powershell
.\.venv\Scripts\python.exe .\data\citation_v5_descriptive_runner_v1\run_descriptive.py --case FRESH-V5-002 --project-root . --execute
```

Requires an existing `GOOGLE_API_KEY` environment variable and locked google-genai 3.3.0. The key is not stored in request or error records. Model, schema, instructions and generation settings cannot be overridden through the CLI. The fixed output budget is 4096 tokens.

Results are written exclusively to `data/citation_v5_descriptive_results_v1`. Requests bind the candidate and descriptive freeze hashes. The runtime context and provider messages exclude human scores, reference rationales and review statuses; snapshot verification reads the reviews locally but does not send them to the provider.

## Controls and outcomes

- Raw response text is saved before evidence validation; no repair or score correction.
- `valid`: evidence contract accepted and score internally consistent with recorded assessments, not proof of semantic support or complete claim coverage.
- `contract_failure`, `score_evidence_inconsistent`, `needs_human_review`, `unfinished_response`: terminal completed responses; retain them and do not retry to seek a better score or format.
- `provider_error`: retain error records. Only HTTP 429 or 503 permits explicit `--retry`, after 120 seconds for the second attempt or 300 seconds for the third. Maximum three recorded SDK invocations per case. SDK automatic retry is set to one attempt.
- Missing/drifted model metadata creates a block that prevents further execution pending investigation.
- An interrupted request is preserved as unresolved and is not automatically resubmitted. Do not delete markers or clear an orphaned lock without inspecting what happened.
- Enforces at least 60 seconds between recorded request starts across **FRESH-V5** cases. It does not sleep automatically.
- Saved terminal results are verified and reused without a new provider call, even when their status is not `valid`.

Non-valid outcomes exit with code 2. A batch should stop for inspection. Continuing other cases does not erase a retained failure. Report all 28 included cases in the descriptive-run denominator, while disclosing all 30 planned cases and both exclusions separately.

`adaptation.json` records the exact adaptation from the frozen development execution code: run identity and pacing-file prefix only. The copied validator bytes are unchanged. The candidate's historical runner placeholder is preserved; actual request identity is `citation-v5-descriptive-runner-v1`.
