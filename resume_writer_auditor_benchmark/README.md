# Resume writer and auditor benchmark

Start with [`SPEC.md`](SPEC.md). It specifies a controlled evaluation for selecting cost-efficient resume **writers**, independent factuality/format **auditors**, and writer–auditor **pairs** against pinned flagship controls.

**Status:** design only. No harness, dataset, paid run, or benchmark result is created or claimed by this folder yet. Work belongs in `/home/skystarved/dev_workspaces`; the external `resume_bench` documents are read-only references.

## Handoff

1. Review the scope, input contracts, controls, evaluator-only gold, metrics, privacy and budget rules in `SPEC.md`.
2. Choose and approve the flagship controls and auditor candidates; verify model/endpoint availability, rates and actual response metadata before any paid run.
3. Obtain permission and produce minimized, independently reviewed source-backed fixtures. `resume_experiment/` contains two useful but potentially sensitive source resumes and partial answer keys—not exhaustive factual gold.
4. Implement and validate the offline positive/negative controls and one consistent verdict path before freezing prompts, gold and the live matrix. Do not count old Test A/B results or the already-consulted healthcare fixture as an untouched evaluation.
5. Approve a dry-run plan and explicit spending ceiling before live calls. Compare writers, auditors on identical blinded drafts, and pairs separately; publish denominators, uncertainty, provider identity and total cost.

No production deployment or database access is part of this specification.