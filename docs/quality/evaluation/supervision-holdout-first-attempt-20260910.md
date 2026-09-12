# Supervision holdout: first evaluation attempt

## Frozen corpus

- Corpus: `supervision-holdout-20260910.json`
- SHA-256 before the run: `BDCECC3B930DF912BCE03B79B50A2069CD06E6D7389B2D0AF6C6940CE9BA0245`
- Cases: 16; expected tasks: 16; task-free announcements: 3.
- This corpus is independently authored synthetic Chinese course-notice text. It is not a real-student accuracy estimate, OCR evaluation, random sample, or usability study.

## Exact first-run command and result

```powershell
& .\.venv\Scripts\python.exe scripts/evaluate_independent_notices.py docs/quality/evaluation/supervision-holdout-20260910.json docs/quality/evaluation/supervision-holdout-initial-20260910.json
```

The command exited with code `1`. It stopped at `holdout-16-correction-cancelled-old-deadline`; no aggregate output file was created. The current deadline parser raised an uncaught `ProviderError` when it encountered the explicitly revoked historical text `10月31日24:00`:

```text
ProviderError: 检测到无效时间：24:00
```

The corpus and implementation were not changed after this failure. Therefore there is no valid 16-case aggregate score to report as a first result.

## Read-only case diagnostics after the aborted run

A separate non-writing probe ran the same current `extract_case` path for each frozen case to identify the failure surface. It is diagnostic evidence only, not a substitute aggregate score: it caught the same exception for case 16 and did not alter inputs or code.

For cases 01--15, strict evaluator-contract counts were: name TP `5`, FP `8`, FN `10`; explicitly dated deadlines correct `3/9`; ambiguous/null deadlines correct `0/6`. These partial totals exclude case 16 and must not be combined with a claimed 16-case score.

| Case | Observed candidate issue |
| --- | --- |
| 01 transfer | Candidate had the right `9月11日17:00` but shortened the object to “上传报名表”; strict name mismatch. |
| 02 correction | Produced a false task from the correction preamble (with wrong inferred `9月16日23:59`) and treated `22:00前` as `23:59`; no exact expected name. |
| 04 two tasks | Found both actions, but turned “9月18日中午前” into `23:59` although the annotation intentionally leaves the time unknown. |
| 05 cross-line | Collapsed the document content into “上传至课程群文件” and invented `23:59` from a date-only deadline. |
| 07 relative tomorrow | Resolved the `16:30` correctly but extracted a trailing-condition fragment as the task title. |
| 08 relative next week | Omitted the bring-materials task. |
| 10 cross-month relative | Used the stated recovery date as a `23:59` deadline even though “课前” had no class time. |
| 11 missing date | Detected a task but named it from the target audience instead of “补全联系方式”. |
| 12 missing time | Named the destination (“提交到教学系统”) and invented `23:59` for a date-only deadline. |
| 13 two actions | Detected “确认选题” only; omitted “填写组员分工”. |
| 14 cancellation plus replacement | Merged two replacement actions into “完成视频”, so both labeled tasks were missed by strict matching. |
| 16 revoked old time | The full run aborts before scoring due to the historical `24:00` text, despite an explicit new valid deadline. |

Cases 03 and 15 correctly produced no candidates for cancellation/information-only notices. Case 06 also correctly produced no candidate for a room change. Case 09 exactly matched its task and explicit cross-month time. These are small synthetic observations, not reliability proof.

## Actionable reliability conclusion

The current implementation cannot yet be called robust on correction/cancellation notifications: a revoked invalid historical timestamp can terminate the entire batch. For completed cases it also overfills date-only or underspecified deadlines with `23:59`, loses action/object boundaries across lines, and merges multi-action replacement notices. Keep this corpus frozen. Any implementation change should be tested against it only as a now-known regression set, and any new generalization claim needs a separately authored holdout plus real-notice/OCR/user evidence.

## Phase 1: evaluator containment, before production repair

The original aborted-run section above is retained unchanged. The evaluator now catches an exception per case, records its type/code/message, supplies no predicted tasks for that case, and scores every expected task as missed. An expected explicit deadline remains in the exact-date denominator and an expected null deadline remains in the null-deadline denominator.

Complete pre-repair output: `supervision-holdout-current-before-invalid-time-fix-20260910.json`.

| Metric | Complete pre-repair result |
| --- | --- |
| Task names | TP 5 / FP 8 / FN 11 |
| Explicit deadline exactness | 3 / 10 |
| Annotated-null deadline exactness | 0 / 6 |
| Candidate-producing notices | 11 / 13 positive; 3 / 3 negative stayed empty |
| Case errors | 1 / 16 |

The single error is case 16: `ProviderError`, code `INVALID_TIME`, message `抽取到无效时间：24:00`. It contributes one missed task and one missed explicit deadline. The corpus hash remained `BDCECC3B930DF912BCE03B79B50A2069CD06E6D7389B2D0AF6C6940CE9BA0245`.

The existing product contract intentionally assigns `23:59` to a date-only due expression and labels it `TIME_DEFAULTED_TO_END_OF_DAY`. The holdout annotations deliberately leave underspecified course-notice times null to measure that policy difference. Neither the corpus labels nor the end-of-day policy were changed to improve these numbers.

## Phase 2: invalid historical-time repair

The local parser now treats an invalid clock mention as an `INVALID_TIME` review warning, without coercing it to a plausible time and without aborting the surrounding notice. A replacement task following an explicitly revoked malformed historical clause retains `INVALID_TIME` and `need_review`; its source quote is the direct live replacement clause, while the complete unmodified notification remains the material source. A cancelled or revoked historical clause does not become a task candidate.

Verified post-repair output: `supervision-holdout-after-invalid-time-fix-verified-20260910.json`.

| Metric | Pre-repair | Post-repair |
| --- | --- | --- |
| Task names | TP 5 / FP 8 / FN 11 | TP 6 / FP 8 / FN 10 |
| Explicit deadline exactness | 3 / 10 | 4 / 10 |
| Annotated-null deadline exactness | 0 / 6 | 0 / 6 |
| Candidate-producing notices | 11 / 13 positive | 12 / 13 positive |
| Case errors | 1 | 0 |

The only intended score change is case 16: it now creates the live `提交实验报告` candidate with the explicitly stated `2026-11-02 09:30` local deadline and an `INVALID_TIME` review warning; the cancelled old deadline is not a second candidate. No title-cleanup or broad extraction tuning was made. The remaining errors in the first-attempt table are still outstanding.

Targeted verification after the repair: `25 passed` across `test_independent_evaluation_metrics.py`, `test_notice_action_safety.py`, and `test_notification_extraction.py`; the run emitted one pre-existing Starlette/httpx deprecation warning. This is targeted regression evidence only, not a complete backend or frontend validation.

## Supervisor review: conflicting invalid dates and unquantified time limits

The supervisor found that skipping an invalid deadline could accidentally select a valid but unrelated answer-session time in the same source. The parser now retains all invalid-time warnings and returns an ambiguous null deadline unless there is direct replacement evidence. An invalid mention combined with multiple valid conflicting dates also retains its original warnings.

Date expressions followed by an unquantified earlier limit, such as “中午前” or “上课前”, now require review instead of defaulting to the end of the day. Ordinary date-only deadlines retain the documented 23:59 convention. An explicit numeric time followed by a separate “课后补填” clause remains unchanged.

Final known-corpus output: `supervision-holdout-after-time-constraint-guard-20260910.json`. Task-name TP/FP/FN: **6/8/10**; explicit deadlines **4/10**; annotated-null deadlines **1/6**; case errors **0**. These strict scores include naming differences and date-only policy differences; no semantic accuracy claim is made. The frozen corpus hash did not change. The final targeted run passed **33** tests; later integrated results are recorded in the Web supervision report.
