# Specification: Resume Writer and Independent Auditor Model Benchmark

**Status:** Draft for review; not implemented or approved for paid execution.

**Date:** 2026-11-03.

**Workspace:** `/home/skystarved/dev_workspaces`. This is a standalone evaluation here, not a change to a production service.

**Purpose:** Find cost-efficient model configurations that write faithful, useful resumes and independently detect resume defects; quantify how each compares with a pinned flagship on each distinct task.

## 1. Decision and scope

There are three separate decisions:

1. **Writer:** Which model produces the best source-grounded, job-targeted resume at acceptable reliability, latency, and cost?
2. **Auditor:** Which model catches real defects, locates them, and avoids rejecting supported content, when given exactly the same frozen resumes and evidence as its competitors?
3. **Pair:** Which writer–auditor combination yields the best end-to-end safety, usefulness, and cost per accepted usable resume?

Run the writer and auditor evaluations independently before pairing. A writer does not grade its own output for the primary comparison, and an auditor is **not** assumed correct simply because it is a flagship. Human-reviewed source evidence and independently adjudicated labels, not another model, are the reference standard. Any later repair stage is an explicitly separate experiment, not an invisible extra call.

This spec adapts the **truth, selection, schema, evidence, and experiment controls**, not the deployment-release purpose, of `resume_bench/SPEC.v2.md` and `SPEC.v3.changelog.md`. Model comparison and buying decisions are explicitly outside that bench's scope. Here T0/T1/T2 mean evaluation modes, not a production merge authorization.

**This document specifies work; it does not assert the harness, datasets, thresholds, or model results exist.** No production connections, deployments, test data uploads, or paid calls are authorized merely by writing it.

## 2. Source references and verified caveats

Reference documents, read-only, captured 2026-11-03:

| Reference | SHA-256 | Use |
|---|---|---|
| `/home/skystarved/Render_Dockers/resume_bench/SPEC.v2.md` | `05a2f1977424c36cb4022d59c09f74179d73532f5e1c5d456e9afa5e22fe24d4` | Typed facts, tiered truth, preservation, schema, formatting, failure and isolation contracts. |
| `/home/skystarved/Render_Dockers/resume_bench/SPEC.v3.changelog.md` | `27cd6af18e3b038a789925dec31a9cb418332f59643fcd8503733cbc292d22a5` | Required-fact provenance, review ownership, holdout limits, fix-commit evidence. |
| `resume_writing_v2/` | Pin repo commit and relevant file hashes at registration | Historical exploratory results, prompts, candidate discovery, and known scorer failures; not a validated oracle. |
| `resume_experiment/` | Record hashes in the private fixture manifest | Candidate source resumes, text extraction, and partial historical answer keys; see §3. |

Source references describe historical snapshots, not verified current deployment state. Do not mutate or depend on live production services. Pin the workspace commit, exact paths, and hashes at run registration; absent references block the affected experiment.

### 2.1 Existing harness: useful evidence, not an oracle

Earlier experiments can help select candidates and supply development examples; their scores, criteria, and previous sample sizes **must not be pooled** with this benchmark or represented as new-system results. In particular:

- The healthcare fixture called a holdout in `resume_writing_v2/round_c_holdout.py` was inspected and used to fix scorer behavior. It is **development data**, not a fresh holdout.
- `resume_writing_v2/grounding.py` includes useful normalization and adversarial examples, but its `check_truth()` can accept a unique matching bare value despite a unit mismatch; its subject overlap is diagnostic, not semantic proof. `check_ownership()` uses employer-name proximity and can miss unknown/ambiguous ownership; duplicate value/unit pairs can collide. `check_preservation()` checks global number presence, not a complete owned proposition.
- `round_b_fullresume.py` and `round_c_holdout.py` differ in which checks control `pass`; do not inherit their verdict implicitly. They do not reserve the budget before queuing every request. Capture actual model, provider, finish reason, attempts and exact payloads rather than inferring them from a label.
- A section-only or empty resume can otherwise pass a truth check vacuously. A clean deterministic scan does **not** establish factual or semantic truth. Nonempty content, explicit check coverage, and human adjudication are required.
- A response with zero reported reasoning tokens does not by itself prove an effort was ignored: telemetry can be missing or provider-dependent. Record request and provider-reported behavior; unknown remains unknown.

## 3. Dataset, privacy, and ground truth

### 3.1 Local source material

Use `resume_experiment/Holloway_ElecWA25.txt` with `answer_key_elec.txt` and `resume_experiment/Whitfield_AdminNC25.txt` with `answer_key_admin.txt` as **candidate source material**, subject to permission and minimization. The first source has three experience entries and the second four; each also contains education and certifications. These two source documents and their answer keys contain contact/identity information and must be treated as sensitive even when authenticity is unknown.

The key files contain Python literal assignments, not JSON. Parse a restricted literal without executing source code. They supply section counts and expected entities but **do not** supply an exhaustive ledger, job dates, credential dates, evidence spans, or full claim ownership. Approximate expected bullet counts are not gold. A missing key entry is **unannotated**, not evidence that the source omits the fact. Some extracted text has disrupted ordering, ligatures or NUL characters: document source-preserving repair and flag ambiguity instead of guessing.

The `resume_bench/rctb/fixtures.py` profiles reuse similar legacy IDs but are synthetic and materially different; they are **not** substitutes for the local resumes or their answer keys. Their synthetic examples may be used as separate development cases if clearly labeled and independently reviewed.

### 3.2 Dataset preparation and provenance

1. Confirm permission to use and send the data for this experiment. Default to **no external transmission** until approval of provider, region, retention, and disclosure. If approval or privacy review is missing, the live run is BLOCKED.
2. Prefer synthetic fixtures. For the two source resumes, create a separately versioned, locally minimized copy. Consistently replace names, contact information, street addresses, personal URLs and handles, photos, and credential identifiers in **resume, answer key, snippets, reports, and filenames**; keep role evidence, company associations, dates, and achievement quantities needed for the task. A stable mapping is sensitive, stored separately with restricted access, never sent to a provider or committed.
3. Independently review text extraction and normalization, including missing lines, Unicode and PDF/DOCX discrepancies. Preserve source references and transformations with hashes and versions; do not publish raw text, source documents, identities, tokens, or reversible mapping. Minimized career details may still re-identify a person: do not call them anonymous.
4. Create a reviewed ledger of **all claims covered by gold**, including fact ID, experience/entity ID, normalized quantity/unit/direction/qualifier where relevant, subject, exact source span/reference, date precision, claim type, and ambiguity. Distinguish direct support, contradiction, unknown/absent evidence, and review-needed. Source-supported does not mean independently verified in the real world.
5. Two reviewers independently annotate the evaluation subset; reconcile discrepancies before freezing. At least one reviewer must be independent of the dataset author; retain disagreement and adjudication records. Keep gold labels and seeded-defect metadata out of writer/auditor prompts.
6. A separate selection record defines this JD's intentionally selected and omitted source facts. `required` defaults to false; every required fact needs a reason and independent reviewer sign-off. Reject an all-required selection unless its reviewer supplies a comprehensive-resume rationale. Optional facts may be omitted without a penalty.

### 3.3 Splits, prompts, and contamination

- Partition at **source-profile** level into development, locked evaluation, and advisory holdout; no resume variants from the same person across splits. The two existing local resumes are candidate development fixtures until their permission, annotation, and split are approved. Acquire enough independently reviewed material before claiming generalization.
- Target at least 8 distinct profiles across relevant domains, each with 2 job descriptions, including sparse/rich sources, date precision variations, no-certificate cases, ambiguous ownership, overlapping source/JD numbers, and layout/OCR issues. This is a proposed minimum for an initial comparative dataset, not proof of statistical power. All conditions use the same minimized source, JD, selection policy and task contract.
- Maintain 3 sequestered holdout profiles, rotate one active profile per release/evaluation cycle, and consult it at most once per cycle. As in v3, report `HOLDOUT (advisory)`; never use a single holdout as an automatic release gate. Tuning after viewing a case permanently promotes it to development; replace it before another holdout claim. Do not infer that all scorers or models generalize from this smoke detector.
- Use **two registered freezes**, because actual writer outputs do not exist before the writer calls. Freeze and hash fixtures, source transformations, writer prompts/schema, selection records, candidate registry, writer scoring/adjudication protocol, reference date for `Present`, writer manifest, and an outcome-independent auditor-corpus sampling rule before writer calls. After generation, sample and independently adjudicate the drafts under that rule; then freeze the resulting draft IDs/content hashes, gold, auditor prompts/schema, audit model roster, seed, and auditor analysis plan before any auditor evaluation calls. Pilot outputs and prompts are separately versioned and cannot be silently included in the locked evaluation. No auditor or prompt tuning after audit-corpus freeze. Refuse a run on a relevant hash mismatch. Record exact requests in restricted artifacts, not just hashes. A change starts a new version; do not rewrite old outputs.
- The same task inputs and rules apply to every competitor. If context length or capabilities force trimming, do not silently shorten one model's input. Mark that configuration incompatible or run a separately versioned equal-input track for every model.

## 4. Model registry and baseline

The **configuration**, not just model family, is the unit: model ID/version, provider endpoint, routing policy, reasoning setting, parameters, prompt, context and output caps. Record availability and exact resolved identities per call.

Before the evaluation is frozen, select and pin at least one currently available **flagship control** for the writer role and one for the auditor role; the same model may serve as both controls, but it must not adjudicate gold. `openai/gpt-6.1-sol` is a *candidate to verify*, not a claim of present availability, superiority, or fixed price. Explicitly label each reference's role and requested effort. Ask the owner to approve the exact models, provider, budget and noninferiority margins before the paid run.

Initial writer candidates, to verify in the live catalog before registration, are the five configurations previously explored in `resume_writing_v2/round_c_holdout.py`: `qwen/qwen3.7-plus`, `minimax/minimax-m3`, `xiaomi/mimo-v2.6-pro`, `qwen/qwen3.6-35b-a3b`, and `z-ai/glm-5.3-flash`. Prior results are **exploratory**, not evidence of passing this new test. Use a separate auditor candidate list that may overlap the writer list; include cheaper, medium-cost and flagship alternatives. Do not assume a strong writer is a strong auditor or exclude an auditor solely because it wrote poorly. Document availability failures and untested candidates.

For controlled comparisons, select the same specific provider endpoint for each repeated call of a configuration where possible. For OpenRouter, set provider routing to the registered endpoint, `allow_fallbacks: false`, and `require_parameters: true` when supported. Verify the request's model, provider, supported parameters, schema and context size before spending. Disable model fallbacks separately. An unavailable endpoint is recorded as BLOCKED, not relabeled as another model. Log actual model/provider when exposed; if unavailable, say `unknown`, not the requested value. Merely requesting an effort is not proof it was honored.

## 5. Evaluation modes and authoritative gates

| Mode | Network / models | What it demonstrates | Prerequisite / outcome |
|---|---|---|---|
| T0 offline contract and adversarial scorer tests | Denied; stubs only | Prompt/schema construction and rejection/detection of known controls, not live behavior. | All frozen positive and negative controls pass; verify denial with a deliberate outbound attempt. |
| T1 live model experiment | Explicit approved inference endpoint only; no production app or database | Writer and auditor behavior for the registered experiment. | T0 passed, fixture privacy approved, reviewer gold frozen, preflight and explicit spend authorization complete. |
| T2 local document format checks | Denied; local renderer/extractor | Canonical-to-PDF/DOCX text and visual fidelity, not model ability. | Synthetic/minimized artifacts only; review page images for clipping or overlap. |

All modes save a structured record. A model FAIL cannot be overridden by a weighted quality score. Infrastructure BLOCKED is not a success and is never silently removed from the denominator. A provider's malformed or truncated output is a **model/output failure** for the planned attempt; record the transport/provider cause separately when known. Endpoint outages, unavailable model, missing credential and network errors are infrastructure BLOCKED. Report timeouts as reliability events; unknown provider-side billing is not $0.

## 6. Task sequence and common contract

The benchmark's system emulates the source → selection → draft → optional final render → independent audit sequence. Do not assert exact production equivalence without separately pinned source-code and prompt snapshots and equivalence evidence. The core comparison remains reproducible without touching production.

### 6.1 Frozen writer prompt contract

Freeze a versioned exact system message, user message and output schema **before** T1. The message must require:

> Use only the candidate evidence in the supplied source. The job description is context for prioritization, not evidence of candidate experience. Write a targeted resume with supported facts; do not invent duties, employers, education, dates, credentials, tools, outcomes or numbers. Preserve selected required facts and their owners. Preserve date precision; if a date is unknown, omit it or use an explicitly allowed unknown marker rather than infer it. Return the prescribed schema only.

Inputs: the same minimized source profile, selection policy, target JD, and output contract for every writer. Structured experience records carry immutable `experience_id`, employer, role, source-provided date/precision, and bullet-level evidence references; education and credentials have stable IDs. Selected fact IDs may be provided as task inputs **only if equally provided to every writer** and reviewed for source support. They are not auditor gold labels.

Writer response must provide (a) a canonical resume with explicit sections and stable entity/experience IDs, (b) source references for each generated assertion or explicit `unknown`, and (c) no commentary outside the structured result. A renderer produces plaintext/Markdown for human inspection and, where requested, PDF/DOCX. Evidence references are model proposals and must be resolved against source; an existing reference alone does not prove the claim is entailed or bound to the correct role.

### 6.2 Structural and deterministic checks

Apply content and schema gates before evaluating truth, with explicit `FAIL`, `BLOCKED`, and `REVIEW_REQUIRED` categories. Check parseability, required fields, nonempty sections where the source has them, fixture-specific minimum usable content and placeholder/refusal detection. Never require certificates, education, years, or metrics absent from the source. Preserve employment ordering when the source supports a chronological order; unknown/overlapping dates require explicit handling. Validate dates, education, certification, identities, metrics, units, sign, scale and qualifiers against the owning source entity. Normalize representational equivalents without inventing precision. Reject malformed JSON, empty content, provider-refused content, and unambiguous length truncation.

Check **all** sections and claims, including summaries, skills, projects and headings. For selected required facts, check the entire proposition and owner, not just that a number appears anywhere. Check omitted optional facts separately without automatically failing. Explicitly mark unchecked semantic content and unresolved source ambiguities for human review. Validate no unauthorized entities or altered employment dates; a fact from a JD is allowed only if the source independently supports it.

### 6.3 Frozen auditor prompt contract

Give each auditor exactly the same blinded canonical resume plus the same minimized candidate evidence, task instructions, and applicable selection record; exclude model/provider identity, writer scoring, gold outcomes and seeded-defect labels. Prevent audit-model self-review in the primary analysis; store self-review as a separate exploratory track. Ask for **findings**, not an ungrounded scalar score:

> Review this candidate resume against the supplied source and approved selection. Identify unsupported or contradicted facts, wrong employer or date ownership, changed quantities/units/directions, missing required selected facts, structural and formatting violations, and unresolved ambiguity. Never infer source support from the job description. For each finding cite a draft span and supporting or conflicting source span/ID; distinguish unsupported, contradicted, missing-required, compliant, and uncertain. Return only the specified JSON schema; do not rewrite the resume.

Per finding require `category`, `severity`, `draft_span_or_missing_fact_id`, `source_reference_or_absence_explanation`, `reason`, and `confidence` if supplied. Require a document-level `accept`, `reject`, or `needs_review` disposition. A claimed absent fact cannot be proven absent from an unreviewed partial key; require a sufficiently complete reviewed source or adjudicate as unknown. Reject invalid schema, missing required citations or bad IDs as auditor output failures. Citations are evaluated for relevance and ownership, not merely existence. Model confidence is not proof.

The auditor must not receive evaluator-only gold. No privileged gold hints, revealed seeded mutations, writer labels, expected verdict or answers in prompts. Preserve blinded randomization and record the mapping locally for analysis only.

## 7. Controls and evaluation matrix

### 7.1 Offline adversarial controls: required before live testing

Create independently labeled positive and negative pairs, including every item below. A clean counterpart must be accepted alongside each negative example; prove expected failure before claiming a guard works. Controls must exercise the actual grader and audit schema, not only helper functions.

| ID | Gold case | Required check |
|---|---|---|
| C01 | Empty/headers-only, conversational refusal, unfilled placeholder, repetitive or truncated response | Content/schema failure before truth; no vacuous PASS. |
| C02 | Supported metric paraphrases (`30%` / `30 percent`; equivalent currency scales) | Equal normalized value **and unit**, retaining sign/qualifiers. |
| C03 | Correct number attached to wrong employer; same value used twice by different owners | Flag wrong ownership; no global or pair-key collision shortcut. |
| C04 | Same number with altered unit, direction, subject or claim (`30%` diagnostic-time decrease vs revenue increase) | Flag contradiction/unsupported or require human review; do not accept on bare value. |
| C05 | JD value copied into resume with and without independent source support | Reject only unsupported candidate claims; provenance, not JD string membership. |
| C06 | Month dropped, fabricated graduation/certificate date, date transferred to another job, year-only source | Preserve owner and source precision; no invented month/year. |
| C07 | Required selected fact absent vs optional fact deliberately omitted | Flag only the required omission; require reviewed selection reason. |
| C08 | Invented tool/activity, unsupported project, employer, education or clearance; relevant cite to wrong role | Flag actual proposition, not just cite existence. Semantic uncertainty goes to review. |
| C09 | Faithful acceptable resumes in different section/date layouts and sparse profiles | Correctly accept; not a mandatory hardcoded certificate or global word-count check. |
| C10 | Wrong claims in summary, skills, headings and projects, not only marked bullets | Entire artifact examined. |
| C11 | Auditor confidently accepts defective draft, flags correct one, fabricates evidence ID, returns invalid JSON or refuses | Count miss, false alarm, invalid citation and output failure in their correct denominators. |
| C12 | Embedded prompt injection in untrusted source, JD and draft | Treat as data; never override the frozen instructions or reveal evaluator labels. |
| C13 | Network attempt in offline modes, cost-cap exhaustion, provider fallback, interrupted run | Fail closed; no hidden spend, relabeling, destructive overwrite or dropped attempt. |
| C14 | Same-line/above/below dates, nearby credentials, non-ASCII names and OCR corruption | Prevent accidental date borrowing; unresolved association is review, not acceptance. |

Each injected defect is a single labeled mutation where practical, paired with its clean original; include explicitly labeled multi-defect cases to test interaction and conditional detection. Verify mutations by a reviewer independent of the author and verify they did not unintentionally introduce extra defects. Do not use evaluation mutations or their answers in prompts or development tuning.

### 7.2 Writer comparison

Run every registered writer—including flagship—on the same locked set of source/JD pairs and repeats. Proposed initial matrix: 8 profiles × 2 JDs × 3 repeats = **48 planned writer requests per configuration**. Randomize model/task order with a recorded seed; apply the same prompt, schema, sampling settings, task caps and fixture version. The model/provider may be different but not the underlying evidence. Save every paid attempt and status; do not replace failed generations with a retry without accounting for both.

Score writer output using frozen deterministic checks plus blinded independent human review of semantic fidelity and usefulness against the gold ledger. Record each error's type, source citation and severity; distinguish unresolved from verified. Separate factual safety, required selection retention, formatting, job relevance and writing quality. Human assessment uses a pre-registered rubric and balanced assignment; record inter-reviewer disagreement and resolve before results lock. All outputs, including refusals, truncations and infrastructure failures, count in the planned-run outcome table.

### 7.3 Auditor comparison on identical drafts

Build one frozen, blinded draft corpus **before** auditor evaluation. For every auditor use identical content, evidence, schema, and seed-controlled order. The corpus contains:

1. Clean expert-reviewed examples and legitimately concise resumes.
2. Paired clean and deliberately corrupted versions covering C02–C10, balanced across defect types and severity; retain independently authored natural multi-error examples. Keep mutation labels evaluator-only.
3. Explicitly ambiguous cases where the correct outcome is `needs_review`, not forced true/false.

The **primary identical corpus** consists of independently authored/synthetic drafts or drafts produced by writer families **outside the entire eligible auditor roster**, including the flagship auditor. All registered auditors get every same frozen case, so model identity is blinded and there is no auditor-family self-review. If insufficient eligible drafts exist, do not substitute overlapping authors: report the primary comparison as BLOCKED until the corpus is expanded. Natural outputs of the candidate writers are evaluated separately as the §7.4 pair cohort. Each auditor can only audit outputs from other model families in that cohort; eligible subsets therefore differ and their unadjusted natural-output audit metrics are **not** the primary identical-corpus ranking.

Before auditor calls, publish exact case counts, sampled draft IDs, clean/defective mixture, defect-class balance and per-case severity without disclosing answer labels to the models. Use the same primary draft IDs for every auditor and randomize presentation per auditor; stratify by fixture, category and writer. At least one independent reviewer must adjudicate proposed findings, with a second reviewer for disagreements. Link each reported span to a gold finding using a frozen matching rule; a vague `something is wrong` is not a matched finding. A model may legitimately report a previously unannotated issue: independently adjudicate it without changing the prior gold silently; record gold version and assess its impact.

Report **critical-defect recall** `TP / (TP + FN)`, precision `TP / (TP + FP)`, false-alarm rate on clean documents `FP_clean_docs / all_clean_docs`, and per-class confusion matrices with denominators. Also report citation validity, localization, supported-evidence relevance, disposition accuracy, `needs_review`/abstention, output-schema compliance, and latency/cost. Invalid/empty/truncated/refused audits are failures to produce an audit, not true negatives; report both operational denominator (all planned attempts) and conditional-on-valid-audit rates. If any denominator is zero, report `N/A`, never 0% or 100%. Audit failures cannot be treated as a safe approval.

### 7.4 Paired pipeline comparison

Replay each frozen natural writer output through every **eligible** auditor once per chosen repeat, using the exact same draft within a writer's cross-auditor comparison; no writer regeneration. Preserve input hash and blinded writer-origin mapping. Exclude same-model-family self-audits from primary pair analysis and label any permitted self-audits exploratory. If the flagship writer and flagship auditor are the same family, their pair is excluded, not silently substituted; pre-register a different-family flagship auditor or use an explicitly different cross-family baseline. The pair does not repair a draft and does not claim to guarantee safety.

Operational sequence: writer output → deterministic output/grounding gates → auditor disposition → independent human adjudication where required. `accept` is the auditor's prediction; it is **not** final release. A deterministic reject, writer failure, audit failure, or `needs_review` is withheld pending a separate human decision. Define, for each pair, over **all planned cases**: `auto_accept_rate = auditor_accept AND deterministic_gates_pass / planned`; `unsafe_auto_accept_rate = auto_accepted AND adjudicated_critical_defect / planned`, with unknown adjudications separately counted; `verified_usable_rate = auto_accepted AND independently_adjudicated_usable / planned`; `safe_rejected_rate = adjudicated_safe AND (auditor_reject OR deterministic_reject) / adjudicated_safe`; and `review_or_failure_rate = needs_review OR invalid_audit OR failed_writer OR blocked / planned`, using mutually exclusive outcome precedence fixed in the manifest. Also report the conditional false-accept rate among all adjudicated unsafe drafts and false-reject rate among adjudicated safe drafts, each with its denominator. Missing adjudications remain unknown, not safe. The human adjudication stage confirms labels and tracks downstream review; it does not retroactively change what was auto-accepted.

Allocate each original writer call's observed cost and latency once to **each hypothetical pair using that writer output**, not the sum of all auditors in the replay grid. Add only that pair's auditor call, its own retries, and predeclared corrections if any. Report actual experiment-wide grid spend separately so reused calls are not double-counted as actual spend. Define pair cost per verified usable accepted output as `sum(pair-attributed billed writer + that auditor + applicable retry costs across planned cases) / count(verified usable auto-accepted outputs)`; unresolved bills make the estimate provisional with known-cost subtotal and unknown count. A zero denominator is `N/A`. Human-review effort/cost is separate and must be included in a clearly labeled total-cost scenario when estimated.

The balanced seeded corpus is diagnostic: its artificial defect prevalence cannot directly estimate production precision, unsafe-accept rates, or cost per usable resume. Calculate pair outcomes on the natural, pre-sampled writer-output cohort; if it is too small or nonrepresentative, label it accordingly. Provide separately labeled sensitivity scenarios using predeclared deployment defect prevalences and the controlled-corpus class-specific rates; give assumptions and propagate uncertainty, not an asserted production rate.

## 8. Flagship-level decision and statistical plan

Pre-register control configurations, primary outcomes, sample size, selection strategy, risk and significance level **before** paid testing. The proposed decision below is a starting design, not evidence or an already-approved standard:

- **Safety eligibility:** no known critical defect can be offset by quality or low cost. Calculate the unsafe-accepted rate and its two-sided 95% confidence interval; mark eligibility `INSUFFICIENT EVIDENCE` when samples are too small to support the owner's preapproved risk ceiling. Three clean runs do not establish a negligible failure rate. Keep unresolved Tier B items visible and assigned to an independent human owner.
- **Auditor eligibility:** bound missed-critical-defect rate and clean-document false-alarm rate separately; the owner approves maximum acceptable rates and minimum case counts per critical class before experiment launch. Claim no verified coverage for classes with zero gold positives. Report rare-class recall and `needs_review` independently of an overall average.
- **Flagship-level:** require a predeclared noninferiority margin for each selected primary quality/safety metric, direction and one-sided 95% confidence-interval bound meeting that margin against the pinned flagship on paired, identical cases. Provisional planning margins: at most **5 percentage points** worse in human-verified usable-resume rate and **5 percentage points** worse in critical-defect recall; the owner must accept or replace these before freeze. Noninferiority of writing does not establish noninferiority of auditing, or vice versa. Critical safety ceilings apply independently of noninferiority.
- **Efficiency:** among eligible noninferior configurations, compare observed, fully accounted cost and latency. Primary cost is `total billed writer + auditor + retry + applicable correction spend / number of independently verified usable accepted resumes`; report numerator and denominator, and `N/A` if denominator is zero. Also show cost per attempt, cost per audit, failed and blocked attempts, and stage-specific latency; disclose price/provider snapshots and confidence intervals. Auditor-only efficiency includes all attempts, not just clean correct ones.
- **Power and uncertainty:** before paid registration, justify margins in relation to the flagship's absolute performance and safety ceilings. Prospectively estimate required **independent profiles** and gold positive cases per critical defect class using the planned paired design, expected event rates and multiplicity adjustment; specify target precision/power and a maximum affordable sample size. If the calculation cannot support the margins or cost ceiling, predeclare the run descriptive, not flagship-equivalence proof. Use a paired cluster bootstrap by source profile for adequately powered continuous/common outcomes, preserving all JDs, drafts and repeats for each sampled profile; report two-sided 95% intervals and a one-sided 95% bound for noninferiority. Do not treat repeats from one profile as independent people. For rare/zero events, additionally provide exact binomial bounds only where the independent unit assumption holds, or a justified cluster-aware method; zero observations never imply zero risk. Predefine the reference comparator, missing-data handling, tie-breaking and multiple-comparison control (e.g. Holm across predeclared primary model-versus-control tests); otherwise label comparisons exploratory. If too few independent clusters or defective cases support stable inference, show descriptive results only. No automatic winner from a marginal point estimate or an uncorrected t threshold.

## 9. Cost, routing, reliability and execution controls

1. The registered plan identifies all writer, auditor, baseline, control, retry and optional correction calls, their token caps, prices by exact route, concurrency, per-call deadlines, and total approved budget. Before any live run, print a dry-run cost range and a pessimistic reservation: input tokens × pinned input rate + maximum output tokens × output rate, including documented reasoning charges and retry allowance, with conservative pricing for caching and applicable overhead. If no trustworthy maximum unit price or token bound is known, mark cost unbounded and do not dispatch that configuration. A dry run makes **no inference calls** and requires no live credentials.
2. Reserve pessimistic cost **before dispatch**, atomically across workers; permit at most a bounded number in flight. Release or reconcile only after a final known charge. Never queue the full plan while checking a spend counter that is updated only on completion. Treat timed-out requests as potentially billable, retain their reservation until reconciliation, and avoid uncancelled parallel duplicate retries. A reservation limits planned exposure but is not an absolute billing guarantee if a provider violates quoted rates or cancellation is ambiguous. Stop dispatch and report uncertainty.
3. Require explicit paid-run approval with the plan and ceiling; no automatic start. Retry policy is fixed and bounded, with each attempt charged and identified. Save progress atomically after **each** attempt; resume only missing planned IDs from a matching manifest, never overwrite a previous run or silently rerun it. A run output path must be unique; keep immutable raw results and separate versioned re-scores.
4. Record requested and actual model/provider, prompt and schema hashes, model/route configuration, run/fixture/replicate/attempt IDs, timestamps, HTTP/transport status, response ID, finish/refusal reason, latency, input/output/reasoning/cache tokens, and billed vs estimated vs unknown cost. Use actual provider usage when present; optionally reconcile generation metadata by ID; no inference of $0 when absent. Record `unknown` for unavailable fields.
5. Never publish credentials or raw sensitive payloads in logs, issue bodies, artifacts, screenshots, or commits. Private output storage must be access-controlled, retention-limited and deletion-tested. Share only reviewed aggregate tables or synthetic/minimized excerpts. No real-candidate records leave the local environment without explicit approval.

## 10. Verdicts, reports and artifacts

Use explicit, separate fields for `transport_status`, `output_status`, `tier_a_status`, `tier_b_status`, `human_adjudication_status`, and `audit_prediction`. Approved deterministic checks may produce `PASS (tier A only)` **only** with declared coverage; unknown or unchecked checks cannot become a full factuality PASS. The following require explicit handling:

| Result | Interpretation |
|---|---|
| `PASS (tier A only)` | Valid output and every applicable, implemented deterministic check passed; semantic correctness remains unproven. |
| `NEEDS_REVIEW` | Source ambiguity, uncertain evidence binding, new semantic claim, or required review still unresolved. |
| `FAIL` | Output/schema/known critical fidelity failure, or auditor failure for a required completed audit. |
| `BLOCKED` | Environmental/infrastructure failure; explicitly include in planned-run accounting and reliability. |
| `HOLDOUT (advisory)` | Rotating limited-consultation holdout observation; not an automatic release gate. |

Assign unresolved Tier B findings to a human reviewer who is not the change author; record owner, date and disposition. Model/prompt changes with new unreviewed Tier B findings are not presented as ready; escalate unresolved issues across cycles as specified by v3. Track actual review workload.

Produce a combined `RESULTS_AND_METHODOLOGY.md` and machine-readable aggregate after execution, including:

- Executive summary identifying approved control, task boundaries, experimental settings and limitations.
- Writer table: configuration, planned/valid/blocked/failed counts, critical-defect rate, required-fact retention, human usefulness/relevance, CI, median/p95 latency and cost per attempt.
- Auditor table: the **same frozen draft IDs**, clean/defective case counts, TP/FP/FN/TN, per-critical-class recall, precision, false alarms, valid audit rate, citation quality, confidence intervals and cost.
- Pair table: writer and auditor identities, unsafe-accepted and safe-rejected counts, human-verified usable outputs, end-to-end latency and cost per usable accepted resume; explicitly indicate `N/A` when denominator is zero.
- Side-by-side cost/quality plot with uncertainty and sample sizes; auditor per-class detection heatmap and false-alarm plot; pair safety-versus-total-cost plot. Never mix writer and auditor scores into one misleading metric.
- Full frozen system/user prompt templates, schema, test criteria, selected-model registry and rationale, fixture/split manifest hashes, privacy/minimization description, authoritative adjudication, exact denominators, controls, attempt/finish/provider details, spend/retries, versioned findings and reproducibility instructions. Do not embed raw candidate PII or sensitive source text.
- Keep raw restricted run artifacts separately; publish reviewed aggregates and hashes only. Benchmark results are not production approval and must be dated.

## 11. Implementation phases and definition of done

All work stays under a new folder in `/home/skystarved/dev_workspaces`; `resume_bench` is a read-only reference.

1. **Design review — $0.** Approve this spec, exact candidate/flagship configurations, prompt/schema versions, profiles/splits and privacy policy, adjudicators, safety thresholds, noninferiority margins and spending plan. Record decisions in a frozen manifest. If annotation or permission is insufficient, BLOCK T1.
2. **Build T0 — $0.** Implement isolated adapters and immutable fixtures; implement a single shared, versioned acceptance path. Add C01–C14 and positive controls; test actual end-to-end verdicts, normalization, ownership, absent/ambiguous facts, reviewer schema, nonempty sections, variable fixture minimums, sanitization, freeze drift, no-network and budget reservations. Test no accidental serialization of custom result objects. Save test evidence. No synthetic stub run can establish live model performance.
3. **Prepare writer inputs and freeze stage 1 — $0 inference spend.** Minimize approved source inputs, write independent reviewed claim/selection records, define holdout rotation, and freeze writer inputs, configuration, and the outcome-independent draft sampling rule. Independently author and label clean/seeded controls. Verify no overlap/contamination. The existing two answer keys are partial checks, not sufficient full gold.
4. **T1 pilot — paid only after approval.** Pre-register model IDs, route/parameters, bounded attempts, same input, pilot matrix and limits. Pilot outputs are diagnostic; fix problems only in development, create a new manifest, and never silently reuse a consulted holdout. Do not advertise pilot winners as flagship-equivalent.
5. **Locked writer, then auditor + pair evaluation — paid only after separate approval.** Execute frozen writers first, logging and reconciling every attempt. Sample natural drafts by the registered rule and have independent humans adjudicate. Separately build the common, non-self-authored auditor corpus; freeze its draft IDs/hashes, labels, audit prompts and analysis plan before auditor calls. Execute identical-corpus audits and eligible cross-family natural pair replays. Stop on cap or unexpected exposure; report failures and missing costs instead of dropping them. Run T2 for document-format claims.
6. **Publish.** Produce the §10 combined report, tables, plots and machine-readable aggregate. Verify the pinned flagship, candidate coverage and power, adjudication, limitations, budget and privacy. Explicitly mark noninferiority as unestablished when confidence bounds, safety limits, or required evidence fail. Do not recommend a model based solely on low cost or an auditor's own verdict.

## 12. Open approvals before implementation / spend

- Owner chooses the flagship for each role, candidate auditor list and exact providers/efforts; validate availability and actual pricing at registration.
- Owner approves which local resumes may be used, their minimization and provider policy, and any additional independently reviewed profiles and JDs.
- Owner approves safety ceilings, critical-class definitions, noninferiority margins, case counts, budget cap, and whether paid human-review time is part of the purchasing scenario.
- Owner names an independent adjudicator and signs off on selection records, mutated controls, freeze manifest and holdout rotation.

Until these are resolved, this is a draft **specification only**: no new measured result, no execution, no model recommendation and no production change.