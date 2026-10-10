# platforms.md — gh vs glab mapping used by review_loop.py

Which CLI command each `review_loop.py` subcommand runs, and which JSON
fields it reads. `<ref>` is the `--pr` value (number, URL, or branch) and is
omitted when `--pr` is not given (the CLI then uses the current branch).
`<iid>` is the MR's `iid` from `glab mr view`. On GitLab, `:id` is resolved
by `glab` from the current repository.

## Platform selection

1. `--platform github|gitlab` if given.
2. Else `--url` if it starts with `http(s)://`: contains `github.com` →
   github, anything else → gitlab.
3. Else, for `preflight --branch NAME`: `git config branch.NAME.remote`
   (`origin` when unset), then `git remote get-url <that remote>`, same rule.
4. Else `git remote get-url origin`, same rule.

`parse` and `record` touch no platform. `record` reads and writes
`<repo root>/AGENTS.md` (`git rev-parse --show-toplevel`), or `--agents
<path>`; its `## Review loop` section holds `ci-wait-minutes`,
`review-job-name`, and `review-bot`.

## Command mapping

| Subcommand | GitHub (`gh`) | GitLab (`glab`) |
|---|---|---|
| `preflight` | `gh auth status` (exit code only) | `glab auth status` (exit code only) |
| `detect` | `gh pr view <ref> --json number,url,headRefOid,headRefName,body` | `glab mr view <ref> -F json` |
| `wait` | `gh pr checks <ref> --json name,state,bucket` (non-zero exit tolerated while checks are pending; empty stdout with any exit code, or non-zero exit with non-JSON stdout → no checks, `status: none`) | `glab mr view <ref> -F json` → pipeline id; then `glab api projects/:id/pipelines/<pipeline id>/jobs?per_page=100` |
| `ensure-description` | `gh pr view` (as `detect`); `gh pr edit <ref> --body-file <template>` | `glab mr view` (as `detect`); `glab api --method PUT projects/:id/merge_requests/<iid> --input <temp JSON file> -H "Content-Type: application/json"` (body `{"description": <text>}`) |
| `fetch-review` | `gh api user --jq .login` (once, to exclude the user's own comments); `gh pr view <ref> --json comments,reviews` (comments and reviews merged into one list) | `glab api user` → `username` (once, to exclude the user's own comments); `glab mr view` (for `iid`); `glab api projects/:id/merge_requests/<iid>/notes?sort=desc&order_by=created_at&per_page=100` |
| `comment` | `gh pr comment <ref> --body-file <file>` | `glab mr view` (for `iid`); `glab api --method POST projects/:id/merge_requests/<iid>/notes --input <temp JSON file> -H "Content-Type: application/json"` (body `{"body": <text>}`) |
| `set-section` | `gh pr view` (as `detect`); `gh pr edit <ref> --body-file <temp file>` | `glab mr view` (as `detect`); `glab api --method PUT projects/:id/merge_requests/<iid> --input <temp JSON file> -H "Content-Type: application/json"` (body `{"description": <text>}`) |
| `push-time` | `gh pr view` (as `detect`); `gh api repos/{owner}/{repo}/commits/<sha>/check-suites` → earliest `check_suites[].created_at` (`source: check_suite`); none → `gh api repos/{owner}/{repo}/commits/<sha>` → `commit.committer.date` (`source: commit_date`) | `glab mr view` (as `detect`) → `head_pipeline.created_at` (`source: pipeline`), only when `head_pipeline.sha` equals the MR head sha; otherwise `glab mr view` is rechecked every 30 s, up to 6 times; still no match → `glab api projects/:id/repository/commits/<sha>` → `committed_date` (`source: commit_date`) |
| `elapsed` | no platform call; `--since`/`--until` ISO 8601, `--until` defaults to now (UTC); prints `minutes` | same |

Creating the MR/PR is not a helper subcommand: the Maia runs
`gh pr create` / `glab mr create` directly, after step-1 authorization.

## JSON fields relied on

| Purpose | GitHub | GitLab |
|---|---|---|
| PR/MR number | `number` | `iid` |
| URL | `url` | `web_url` |
| Head commit | `headRefOid` | `sha`, else `diff_refs.head_sha` |
| Source branch | `headRefName` | `source_branch` |
| Description | `body` | `description` |
| Pipeline id | — | `head_pipeline.id`, else `pipeline.id` (none → no checks) |
| Pipeline commit (push-time) | — | `head_pipeline.sha`, `head_pipeline.created_at` |
| Authenticated user | `gh api user --jq .login` | `glab api user` → `username` |
| Check/job name | `name` | `name` |
| Check/job state | `bucket`, else `state` | `status` |
| Comment body | `body` | `body` |
| Comment author | `author.login` | `author.username` |
| Comment time | `createdAt` (comments), `submittedAt` (reviews) | `created_at` |
| Skip system notes | — | `system: true` |

State values are bucketed as: pending (`pending`, `running`, `created`,
`queued`, `in_progress`, `waiting_for_resource`, `preparing`, `scheduled`,
`canceling`), failed (`fail`, `failed`, `failure`, `timed_out`,
`action_required`), canceled (`cancel`, `cancelled`, `canceled`); anything
else counts as success.

When `--job` is not given, the review job is chosen by the alternatives of
`--job-pattern` in order (default `ai-code-review`, then `ai-review`, then
`code-review`, then `review`): the first alternative that matches any job
wins, whatever the job order. An exact `--job` always wins.

A failed CLI call returns `{"error": ..., "stderr": ...}`: `stderr` is the
last 500 characters of the CLI's stderr, with GitHub (`ghp_`, `gho_`, `ghu_`,
`ghs_`, `ghr_`, `github_pat_`) and GitLab (`glpat-`) tokens replaced by `[REDACTED]`.
