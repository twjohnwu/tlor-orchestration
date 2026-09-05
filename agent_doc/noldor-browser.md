# Browser use — dual-path (noldor-loremaster)

Read `~/.claude/agent_doc/customize/noldor-browser.md` too if it exists.

Tier order: WebFetch first; reach for a browser ONLY when the page is
JS-rendered (WebFetch returns an empty shell or an "enable JavaScript"
stub). Then ego-browser; fall back to the Playwright subset only if
ego-browser is unavailable. State which path you used in your report.

## ego-browser (primary)

Every heredoc round starts with `useOrCreateTaskSpace(name)` — the runtime
resets between heredocs, so reuse the same space across rounds; name it
after the research goal. Allowed: `openOrReuseTab`, `snapshotText`,
`captureScreenshot`, `scrollBy`/`scrollToBottomUntil`, `drainEvents`
(network observation). `click` strictly for pagination or expanding
collapsed content — same limit as the Playwright rule below. Finish with a
dedicated final heredoc, `completeTaskSpace(id, { keep: false })`, unless
the dispatch prompt says to keep the session open.

**Login-state rule**: a task space inherits the user's login state — do
not exploit it. Prefer public URLs; if content is visible only because of
the user's login, report that instead of quoting it as public
documentation.

**Fallback trigger**: if `command -v ego-browser` fails, or the CLI errors,
use the Playwright subset instead.

### Blocked by a bot verifier (ego path)

Never evade it. Call `await handOffTaskSpace(task.id)` so a human can solve
it; report the URL and what the verifier demands. The dispatching Maia
asks the user; once cleared, the resumed dispatch reclaims the space with
`await takeOverTaskSpace(task.id)` and continues.

## Playwright subset (fallback)

Allowed: navigate, snapshot, screenshot, network_requests, and click —
click strictly for pagination or expanding collapsed content on the page.
Call browser_close when done — skip only if the dispatch prompt explicitly
says to keep the browser open.

### Blocked by a bot verifier (Playwright path)

Do NOT call browser_close — leave the browser open with the challenge page
visible (an explicit exception to the close-when-done rule above). STOP
searching that site and report: the URL, what the verifier demands, and
that the browser was left open for a human pass. The dispatching Maia asks
the user; a human solves the challenge in the open browser window, and the
Maia then RESUMES the same noldor agent (dispatch.md §4, resume case 2) to
continue in the same browser session with the verified state intact.

## Both paths

- FORBIDDEN: filling forms, typing, logging in, submitting, purchasing, or
  any interaction that changes external state. If a page demands any of
  those to show its content, report that and stop.
- Do not use captured network data to call API endpoints that robots.txt
  disallows; cite the rendered page, not reverse-engineered APIs.
- If other sources can answer the question while one site is blocked, keep
  working those and mark the blocked site's findings as unverified in your
  report.
