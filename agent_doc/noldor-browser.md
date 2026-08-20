# Browser use — read-only subset (noldor-loremaster)

Read `~/.claude/agent_doc/customize/noldor-browser.md` too if it exists.

- WebFetch first; reach for the browser ONLY when the page is JS-rendered
  (WebFetch returns an empty shell or an "enable JavaScript" stub).
- Allowed: navigate, snapshot, screenshot, network_requests, and click —
  click strictly for pagination or expanding collapsed content on the page.
- FORBIDDEN: filling forms, typing, logging in, submitting, purchasing, or
  any interaction that changes external state. If a page demands any of
  those to show its content, report that and stop.
- Do not use captured network_requests to call API endpoints that
  robots.txt disallows; cite the rendered page, not reverse-engineered APIs.
- When your browser work is done, call browser_close before reporting —
  a later dispatch reopens it in seconds. Skip closing ONLY when the
  dispatch prompt explicitly says to keep the browser open.

## Blocked by a bot verifier (CAPTCHA / anti-bot wall)

You cannot solve it and MUST NOT try to evade it. Instead:

1. Do NOT call browser_close — leave the browser open with the challenge
   page visible (an explicit exception to the close-when-done rule above).
2. STOP searching that site and report: the URL, what the verifier demands,
   and that the browser was left open for a human pass.
3. The dispatching Maia asks the user; a human solves the challenge in the
   open browser window, and the Maia then RESUMES the same noldor agent
   (dispatch.md §4, resume case 2) to continue in the same browser session
   with the verified state intact.
4. Meanwhile, if other sources can answer the question, keep working those
   and mark the blocked site's findings as unverified in your report.
