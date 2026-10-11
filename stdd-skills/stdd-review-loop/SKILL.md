---
name: stdd-review-loop
description: 'STDD AI-review loop for a GitHub PR or GitLab MR. After a feat or bug-fix MR/PR is opened: wait for CI, repair failing CI jobs from their logs, read the AI code-review comment, fix every real finding above Nit/Low (reply to false positives), push, and repeat (up to the max-rounds cap) until LGTM or only Nit/Low findings remain, then write an "AI Review Fixes" summary into the MR/PR description. Triggers: the user opens or asks to open an MR/PR for a feat or bug fix, "review loop", "fix until LGTM", "修到 LGTM", "/stdd-review-loop".'
---

# stdd-review-loop — Beacons of Gondor 烽火台

Opt-in skill (installed from `stdd-skills/`, not auto-loaded from the
plugin's `skills/` directory). It drives the review loop that follows an
opened feat or bug-fix MR/PR: CI runs, an AI code-review job posts a
comment, failing CI jobs get repaired, blocking findings get verified and
fixed, the branch is pushed, and the cycle repeats until the reviewer is
satisfied or the round cap is hit. The loop ends with a summary table
written into the MR/PR description.

The mechanical parts (CLI checks, CI polling, CI job logs, comment fetching,
severity parsing, description edits, settings recording, the test queue)
live in one helper:

```
python3 <skill-dir>/references/review_loop.py <subcommand> [flags]
```

`<skill-dir>` is this skill's installed directory (e.g.
`~/.claude/skills/stdd-review-loop`); step 0 resolves it to an absolute
path once. Every subcommand prints exactly one
JSON object; on failure it prints `{"error": "..."}` and exits 1 — treat an
`error` object as a STOP-and-report, never guess past it (one exception:
a `job-log` error in step 4b marks only that job unresolved). The PR/MR-scoped
subcommands accept `--pr` (number, URL, or branch), `--url`, and
`--platform github|gitlab`; without them the platform comes from the
`origin` remote and the PR/MR from the current branch. The gh/glab command
behind each subcommand, and the JSON fields relied on, are in
`references/platforms.md`.

**Who does what.** The Maia (main session) runs the helper, pushes,
posts reply comments, and edits the description itself — these are
covered by the step-1 authorization and need this session's context.
Subagents do the field work: `eagle-sentinel` verifies findings, and
`gondor-builder` or `codex (Maia-direct, dispatch.md §3d)` writes the fixes
(routing per `~/.claude/rules/dispatch.md`). Every one of those dispatch
prompts carries this line verbatim, except that the Maia MUST replace
`<REVIEW_LOOP>` with the absolute path of `review_loop.py` resolved in
step 0 before dispatching (a subagent cannot see this skill's directory,
so a prompt that still contains `<REVIEW_LOOP>` is malformed):

> Tests only through `python3 <REVIEW_LOOP> run-tests --timeout 240 [--cmd '<cmd>']`, called with the Bash tool parameter `timeout: 600000` (600000 ms, the maximum), foreground, one at a time; never run tests in parallel or in the background. On `{"status":"timeout"}` retry once later, then report instead of running tests another way. If AGENTS.local.md says `tests: never` (or has no `tests`), do not run tests at all.

Pushes and comments are
outward-facing T1 actions under `~/.claude/rules/risk-tiers.md`; step 1 is
the one place that authorization is obtained.

## 0. CLI check

First, once per session, resolve `<skill-dir>` to an absolute path: the
directory holding this `SKILL.md` (e.g. `~/.claude/skills/stdd-review-loop`
with `~` expanded to the value of `$HOME`). Check that
`<skill-dir>/references/review_loop.py` exists; its absolute path is
`<REVIEW_LOOP>`, substituted into every dispatch prompt's test line (see
"Who does what"). If the file is missing, stop and report.

When the user gives an MR/PR link or a branch name, run:

```
python3 <skill-dir>/references/review_loop.py preflight --url <link>
python3 <skill-dir>/references/review_loop.py preflight --branch <name>
```

Output: `platform`, `branch`, `cli` (`gh` or `glab`), `installed`,
`logged_in`, `hint`. With `--branch` the platform comes from that branch's
upstream remote (`origin` when none is configured); `--url` and `--branch`
are mutually exclusive.

- `installed: false` → ONE AskUserQuestion with three options:
  "install for me (`brew install gh`|`brew install glab`)" / "I'll install it
  myself" / "stop". Run the brew install only on the first option; on the
  second, wait for the user and rerun `preflight`; on "stop", stop.
- `logged_in: false` → login is interactive. Tell the user to type
  `! gh auth login` or `! glab auth login` (the `hint` field carries the
  exact line), then rerun `preflight`.
- Never ask for, read, paste, store, or pass a token. Authentication is
  the CLI's job, done by the user.

## 1. Authorize

Run `detect` (add `--pr <link|branch>` when the user named one):

```
python3 <skill-dir>/references/review_loop.py detect --pr <ref>
```

Output: `platform`, `number`, `url`, `head_sha`, `branch`, `description`.
If no MR/PR exists yet the command returns an `error`; then the MR/PR is
still to be created.

Ask ONE AskUserQuestion showing:

- the branch name;
- the commit list (`git log --oneline <target-branch>..HEAD`);
- the MR/PR URL — or, if not yet created, the proposed title and
  description.

One "yes" is **branch-level authorization until merge**. It covers: creating
the MR/PR if it does not exist yet (`gh pr create` / `glab mr create`),
every review-fix and CI-repair push on this branch, reply comments,
description updates, and the AGENTS.md settings commit (step 3). It does not carry over to
another branch, another MR/PR, or this branch after merge. "No" → stop.
Never push before this answer.

After "yes", if the description is empty:

```
python3 <skill-dir>/references/review_loop.py ensure-description --pr <ref> \
  --template <skill-dir>/references/mr-description-default.md
```

Output: `written` (true only if the description was empty). The skeleton
headings are fixed; the Maia then writes the content of Summary, Changes,
and Test plan from the commits and diff — via `set-section --heading
"## Summary"` (and likewise for the other two) with a file holding the full
section including its heading, or by editing the description directly.

## 2. Wait for CI

After every push (and for a freshly created MR/PR with no new push), read
the learned settings:

```
python3 <skill-dir>/references/review_loop.py record --show
```

It merges the repo's `AGENTS.md` and this machine's `AGENTS.local.md`
(both `## Review loop`). Output: `path`, `ci_wait_minutes`,
`review_job_name`, `review_bot`, `test_command`, `lint_command` (each
`null` when absent), `max_rounds` (default 10), and `tests` (`never` /
`serial`; absent = `never`). An `error` (e.g. an invalid `max-rounds` or
`tests` value) → stop and report. X = `ci_wait_minutes`, default **10**.

- `max_rounds` is the round cap for step 7. In round 1, if `AGENTS.md` has
  no `max-rounds` line, run `record --max-rounds 10`; the change rides in
  the `chore: record CI settings` commit (step 3).
- `tests` is set by the user by hand in `AGENTS.local.md` (per machine,
  gitignored, never committed). Never write it yourself; `record --local
  --tests serial|never` exists only for when the user asks.

Run `wait` with the Bash tool's `run_in_background` — never a foreground
sleep:

```
python3 <skill-dir>/references/review_loop.py wait --pr <ref> --minutes X \
  [--job <review_job_name>]
```

The script sleeps X minutes and checks once; while CI is still running it
sleeps another X, up to 3 extensions (`--max-extensions`, default 3).
Pass `--job` only when `review_job_name` is recorded (exact name); otherwise
the default `--job-pattern` (`ai-code-review|ai-review|code-review|review`)
applies. Output: `status` (`running` / `success` / `failed` / `canceled` /
`none`), `review_job`, `review_job_status`, `failed_jobs`, `canceled_jobs`,
`waited_minutes`, `extensions`.

`wait` results are handled in step 4. `status: none` means the PR/MR has
no checks (on GitHub, `gh pr checks` exiting non-zero with no JSON also
lands here).

After `wait` returns, get the push time; steps 3 and 4 need it. Run it
here, not right after `git push`: by now the pipeline for the new head
commit exists, so GitLab's `head_pipeline` belongs to this push and not to
the previous one.

```
python3 <skill-dir>/references/review_loop.py push-time --pr <ref>
```

Output: `head_sha`, `pushed_at` (ISO 8601 UTC), `source` (`check_suite` /
`pipeline` / `commit_date` — `commit_date` is the fallback and may be earlier
than the real push). On GitLab `head_pipeline.created_at` is used only when
`head_pipeline.sha` equals the MR head commit; otherwise the script rechecks
every 30 seconds, up to 6 times, then falls back to `commit_date`.

## 3. Record settings (first round only)

In the first round only, once the review comment is found (step 4):

- M = `elapsed --since <pushed_at> --until <comment created_at>` → `minutes`.
  Run `record --minutes M`. The script writes `ci-wait-minutes` into the repo's
  `AGENTS.md` `## Review loop` section only when it is absent or differs by
  more than 20% (`minutes_written` in the output says which).
- The review job name found by `wait` (`review_job`) → `record --job NAME`
  (`job_written` says whether it changed).
- The review comment's `author` → `record --bot LOGIN`, stored as
  `review-bot` (`bot_written` says whether it changed). Later rounds pass it
  to `fetch-review --author`.

The `max-rounds` default (step 2) and a first-time `lint-command` (steps
4b and 6) are recorded the same way. `max_rounds_written` stays `false`
when the recorded value equals the default, so decide by `git status
--porcelain AGENTS.md`, not by the `*_written` flags. If `AGENTS.md`
changed, make ONE separate commit `chore: record CI settings` staging only
`AGENTS.md`. Ordering:

- If a fix push follows (step 6 or 4b), the settings commit rides with
  that push.
- If no fix push follows (the loop stops at step 7), push it alone at the
  end with the message `chore: record CI settings [skip ci]`, so that push
  starts no new CI run and no new review round.

Both pushes are covered by the step-1 authorization.

## 4. Read the review

Handle the `wait` result, first matching line wins:

- `status: running` after the last extension → extensions exhausted: stop
  and report (URL, minutes waited).
- `status: failed` or `canceled` with `failed_jobs` non-empty (jobs other
  than the review job failed) → step 4b. If a review job is also
  present, fetch its comment below as well; the round's review findings are
  handled in steps 5–6 alongside the CI repair.
- `canceled_jobs` non-empty and `failed_jobs` empty (non-review jobs were
  canceled; nothing to repair, likely superseded or cancelled by hand) →
  if the review job finished (present, `review_job_status` not canceled),
  still fetch its comment below and handle it (steps 5–6); then stop and
  summarize, reporting the canceled jobs. Otherwise report the canceled
  jobs and stop.
- `review_job: null` (no job matched the recorded name or the default
  pattern; also `status: none`) → no review job: report the CI result and
  stop.
- Review job present → fetch its comment, run in the background (the LLM
  provider behind the review job may lag behind the job itself):

```
python3 <skill-dir>/references/review_loop.py fetch-review --pr <ref> \
  --since <push time> --retries 5 --interval 180 [--author <review_bot>]
```

Output: `found`, `body`, `author`, `created_at`, `attempts`. Only comments
strictly newer than `--since` count; on GitHub both PR comments and PR
reviews are searched. Comments written by the authenticated CLI user (the
Maia's own replies) are always excluded: the script looks up that login
once per call (`gh api user` / `glab api user`). In the first round, record
the found comment's `author` as `review-bot` (step 3); on every later round,
and whenever `review_bot` is already recorded, pass `--author <review_bot>`.

- `found: false` after all retries → report and stop, unless step 4b runs
  this round: then the round continues as a CI-repair-only round and the
  next round looks for the comment again.

A failed review job by itself does not stop the loop: many review bots fail
their job on purpose to signal findings. Its comment is what counts.

## 4b. CI repair

For each job in `failed_jobs`:

1. Fetch its log tail (redacted):

   ```
   python3 <skill-dir>/references/review_loop.py job-log --pr <ref> \
     --job <name> [--lines N]
   ```

   Output: `job`, `log_tail`, `empty`. An `error` here is the one
   exception to the stop-on-`error` rule: the job's log cannot be fetched
   (for example "not a GitHub Actions job" for an external status such as
   `codecov/patch`, or any other `job-log` failure). Do not stop the loop:
   mark that job **log unavailable** — unresolved, resolution `Not fixed —
   fix failed (see report)`, named in the user report with the `error`
   text — skip items 2–5 for it, and go on with the other failed jobs and
   the round's review findings.
2. Stop and report instead of repairing when:
   - `empty: true`, or the log looks like infrastructure (runner system
     failure, timeout, no runner available);
   - the fix needs secrets or CI configuration the agent cannot see;
   - the same job failed with the same first error line in the previous
     round as well (two consecutive rounds).
3. Dispatch `gondor-builder` with the job name and `log_tail` as the
   acceptance context: make that job pass.
4. Verify locally: lint first (`lint_command`; if none is recorded, find
   the project's lint command and `record --lint-command <cmd>` — it rides
   in the `chore: record CI settings` commit, step 3), then tests per the
   policy in step 6.
5. If the builder could not make the job pass (or local verification still
   fails after its attempt): leave that job unresolved, make no CI-repair
   commit for it, and do not retry within the round. Record it for the
   summary with resolution `Not fixed — fix failed (see report)` and name
   it in the user report.

After every failed job has been attempted (repaired, left unresolved, or
log unavailable):

- Review comment found this round → continue with step 5; the CI repair
  is committed with the round's review fixes in step 6.
- Otherwise, if at least one job was repaired, make ONE commit
  `fix: repair CI (<job>[, <job>…]) round <R>` (repaired jobs only)
  staging only the touched files, push normally (covered by the step-1
  authorization; never force-push, never `--no-verify`), and apply the
  step 7 table. If no job was repaired, there is nothing to commit or
  push and nothing else is actionable this round: apply the step 7 table
  directly (row 4).

A CI-repair round counts against `max_rounds` like any other round.

## 5. Classify

Pipe the comment `body` into `parse` (stdin):

```
python3 <skill-dir>/references/review_loop.py parse < <body file>
```

Output: `verdict` (`lgtm` / `changes` / `unknown`), `blocking_count`, and
`findings[]` with `n`, `severity`, `blocking`, `path`, `line`, `text`.

- Blocking: Critical, High, Medium, Major, Warning, Error, and `P0`–`P2`.
- Non-blocking: Low, Nit, Minor, Info, Suggestion, Trivial, and `P3` or
  higher.
- Any other severity word is blocking (fail-safe): an unrecognized format
  must not end the loop early.

How `parse` reads a comment:

- A finding is a bullet, a numbered item, or a `**#N**` item. Its severity
  comes from a tag at the start of the item text — after the list marker,
  bold markers, or `#N —` — written as `[X]`, `X:`, `**X**:`, `**X**`, or
  `(X)`; or from a `Severity: X` label anywhere in the item. Words elsewhere
  in the item do not count, and markdown links `[text](url)` are ignored.
- Under a heading that starts with a severity (`### High`, `#### Low (2)`,
  `### P1: correctness`), the heading's severity applies to each item
  unless the item's own leading tag overrides it. The severity word may be
  followed only by a count, a parenthetical, a colon, or one of "issues",
  "findings", "severity", "priority"; headings such as `### Error handling`
  or `## No high-severity issues` set no severity. An item with neither a
  heading severity nor its own tag is not a finding.
- `verdict: lgtm` needs an unconditional LGTM, "Looks good to me", or a
  standalone "Approve(d)" line. Negated forms ("not LGTM", "not quite /
  not yet / not really LGTM", "isn't LGTM" — any "not" earlier in the same
  sentence) or conditional ones ("LGTM once / after / pending / except /
  but / if …") do not count.
  "Request changes", "Needs changes", "Changes requested", or any blocking
  finding make the verdict `changes`.

If `verdict` is `changes` or `unknown` but `parse` found 0 findings, the
format may not be recognized: read the comment yourself, list its findings
by hand, and treat every finding without a recognizable non-blocking
severity as blocking. A hand reading can also find nothing (for example
"No issues found.").

Then take the round's **new blocking findings** (N): the blocking findings
from `parse` or from the hand reading, minus those already answered as
false positives in an earlier round. What happens next is decided by the
table in step 7.

## 6. Handle blocking findings

For each finding in N (step 5):

1. **Verify.** Dispatch `eagle-sentinel` with a fresh context: the finding
   text and the code at its `path:line` (plus whatever surrounding code it
   needs). It returns holds / does not hold with `file:line` evidence.
2. **Holds → fix.** Dispatch `gondor-builder`, or run
   `codex (Maia-direct, dispatch.md §3d)`, with the verified findings as
   acceptance criteria. Verify per this machine's `tests` policy (step 2):
   - `never` → lint only (`lint_command`; if none is recorded, find the
     project's lint command and `record --lint-command <cmd>`, step 3).
     CI runs the tests.
   - `serial` → lint, then the tests through the machine-wide queue, in
     the foreground (never `run_in_background`), with the Bash tool
     parameter `timeout: 600000` (600000 ms, the Bash tool's maximum) and
     `--timeout 240` (seconds to wait in the queue):
     `python3 <skill-dir>/references/review_loop.py run-tests --timeout 240 [--cmd <cmd>]`
     (default command: `test_command`; output `status` `ok` / `failed` /
     `timeout`, `exit_code`, `stdout_tail`, `stderr_tail`). It refuses
     with an `error` when `tests` is `never`. On `{"status": "timeout"}`
     (another test run held the queue for 240 s), retry once later; if it
     times out again, report it instead of running the tests any other way.
     Honest limit: the queue wait plus the test run must finish within the
     Bash tool's 10-minute ceiling. A suite that, with its queue wait, needs
     more than ~10 minutes cannot run in the foreground — report that to the
     user; never move it to the background to get around the limit.
3. **Does not hold → reply once.** Write the reason and the `file:line`
   evidence to a file and post it:
   `python3 <skill-dir>/references/review_loop.py comment --pr <ref> --body-file <file>`.
   A finding that repeats one already answered in an earlier round is not
   in N (step 5) and gets no new reply.

After all findings of the round are handled:

- If any finding was fixed or a CI repair (step 4b) is pending: make ONE
  commit per round, staging only the files the fixes touched (plus the
  `chore: record CI settings` commit from step 3 if pending, as its own
  commit). Message (R = round number): `fix: address AI review round <R>`
  for review fixes only; `fix: repair CI (<job>[, <job>…]) round <R>` for
  a CI repair only; `fix: repair CI (<job>[, <job>…]) and address AI
  review round <R>` for both.
- If a fix commit was made, push normally. Never force-push, never
  `--no-verify`. If nothing was fixed, do not push (a pending settings
  commit waits for step 7).
- Then apply the step 7 table (`push-time` runs in step 2, after `wait`,
  when the table sends you there).

## 7. Stop and summarize

Apply this table after step 5, and again after the round's push decision
(step 6, or step 4b when the round had no review comment). N is the round's
new blocking findings (step 5); "CI repair pending" means step 4b repaired
jobs this round that are not yet committed; "CI repair failed" means step 4b
left at least one failed job unresolved (the builder could not make it
pass); a job whose log was unavailable (step 4b item 1) is not a failed CI
repair — it is named in the report and the round goes on, so it stops the
loop only through row 4's CI-repair-only case (nothing else was actionable);
the round cap is `max_rounds`
(step 2).
Take the first row whose condition holds:

| # | When | Condition | Next |
|---|---|---|---|
| 1 | after step 5 | N is not empty | Step 6. |
| 2 | after step 5 | N is empty and a CI repair is pending | Step 6's commit and push only (CI-repair message), then rows 4–7. |
| 3 | after step 5 | N is empty and no CI repair pending (a failed CI job left unresolved by step 4b is named in the report): `verdict` is `lgtm`, only non-blocking findings, only false positives already answered, or the hand reading found nothing | Stop and summarize. If `verdict` was `unknown`, say so in the user report. |
| 4 | after the push decision | A finding in N held but no fix for it landed (the builder could not fix it), or a CI repair failed, or a CI-repair-only round (no review comment) repaired no job — every failed job failed to repair or had its log unavailable — and nothing was pushed | Stop and summarize; tell the user which findings and CI jobs remain unresolved, and that any fixes pushed this round were not re-reviewed. |
| 5 | after the push decision | Nothing was pushed: every finding in N was judged a false positive and replied to, and there was no CI repair attempted (a job whose log was unavailable is named in the report but is no attempt) | Stop and summarize. |
| 6 | after the push decision | A fix (review, CI repair, or both) was pushed and this was round `max_rounds` | Round cap: stop, summarize, and tell the user that round's fixes were pushed but not re-reviewed. |
| 7 | after the push decision | A fix was pushed in an earlier round | Back to step 2 (next round). |

These rows cover every case: after step 5, N is either non-empty (row 1)
or empty, with a CI repair pending (row 2) or not (row 3); after the push
decision, either a held finding or a failed CI repair was left unfixed, or
a CI-repair-only round repaired nothing (row 4),
or every held finding was fixed and then nothing was pushed (row 5) or a fix was pushed,
in round `max_rounds` (row 6) or earlier (row 7). The loop never waits on
anything else.

To stop and summarize (the early stops in steps 2, 4, and 4b — extensions
exhausted, no review job, no review comment, an unrepairable or repeating
CI failure — also run this when at least one
round has completed; otherwise they only report):

1. Write the summary section to a file in the format of
   `references/summary-format.md` — columns
   `Round | # | Severity | File:Line | Finding | Resolution | Commit`, one
   row for EVERY finding from every round, non-blocking ones included;
   Resolution is one of `Fixed`, `Fixed — CI repair` (one row per repaired
   job), `Not fixed — false positive (see comment)`, `Not fixed —
   non-blocking (<severity>)`, `Not fixed — fix failed (see report)` for a
   finding that held but whose fix did not land, or a failed CI job that
   was not repaired or whose log was unavailable, or `Fixed — not
   re-reviewed (round cap)` for a last-round fix pushed after the last
   review — and apply it:
   `python3 <skill-dir>/references/review_loop.py set-section --pr <ref> --file <file>`
   (default `--heading "## AI Review Fixes"`; an existing section is
   replaced, otherwise appended; output `replaced`).
2. Push the pending `chore: record CI settings` commit if it has not gone
   out yet, with the message `chore: record CI settings [skip ci]` (step 3).
3. Report to the user: MR/PR URL, blocking/non-blocking counts per round,
   the CI jobs repaired per round, the false positives and where they were
   answered, and the remaining non-blocking findings.

## Honest limits

- Not yet exercised against a real PR/MR end to end; the helper is covered
  by unit tests with stubbed CLIs only.
- The helper depends on specific gh/glab JSON field names, listed in
  `references/platforms.md`. Those names have only been exercised against
  fake CLIs, not live accounts; if a CLI version renames one, the helper
  misreads or reports an `error` — check that table first.
- Review bots format their comments differently. `parse` recognizes
  headings, bullets, `**#N**` items, leading `[X]` / `X:` / `**X**` /
  `(X)` tags, `[P0]`–`[P3]` tags, and `Severity: X` labels (step 5);
  anything it reads as an unknown severity is blocking, and a comment with
  no parsed findings and no unconditional LGTM is read by hand before the
  step 7 table decides (step 5).
