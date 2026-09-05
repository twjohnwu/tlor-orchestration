# prose-domains.md — venue-specific rules for five professional-writing domains

Distilled from sepia (github.com/Nanako0129/sepia, v0.8.0, MIT, Nanako Tsai):
`domains/{release-notes,dev-replies,postmortems,tickets,tech-articles}.md`.
Same instinct per venue — state the decision, back it with an artifact,
match real conventions, never pad for symmetry. Fiction: `agent_doc/
fiction-narrative.md`; generic de-AI patterns: `agent_doc/en_us/patterns.md`
/ `agent_doc/zh_tw/patterns.md`.

## Release notes & announcements

Reader is deciding whether to upgrade and what will break — everything
serves that decision.

- Breaking changes first, with the exact migration step (command, config
  key, renamed flag).
- Every claim carries its artifact: issue/PR number, commit range, exact
  version string, a real benchmark with conditions — no artifact, no claim.
- One line per change, verb-first, no adjectives — delete the journey
  intro and the road-ahead closer.
- Credit people plainly ("thanks @name for #398"), no gratitude paragraphs;
  length follows the release — a patch release is three lines.

## PR / issue replies and review comments

Read the thread first and match its register; absent a thread, default to
direct and proportional.

- Answer first, in sentence one; reasoning after, only if needed.
- Cite the artifact: `file.py:214`, the commit SHA, the error text verbatim.
- Disagree plainly with a reason, no apology wrapper, no praise sandwich.
- Say "I don't know" or "won't fix" when true, one reason and a link — no
  softening it into ambiguity the reporter has to decode.
- Thank people when genuinely warranted, not as a reflex opener; vary
  comment length by stakes.

## Incident postmortems

Blameless toward people, merciless toward mechanisms.

- Timeline in absolute times and timezone, including the wrong turns — the
  40 minutes on a bad hypothesis is the instructive part, not the filler.
- The failure mechanism at code/config level (exact query, flag, race); if
  you don't know it, that's a question for the team, not prose.
- Impact in numbers first (duration, requests failed, users affected),
  narrative second, from the incident data — never rounded to sound complete.
- Commit to the causal chain you believe; mark the unknown part unknown.
  Self-praise adverbs ("swiftly identified") out — timestamps carry the
  speed judgment (see `agent_doc/adverbs.md`).
- End at the action items (owner + date); no moralizing conclusion.

## Tickets & work orders

The assignee should start without asking a question and know when they're
done.

- Title states the outcome, not the activity ("Retry queue drops jobs on
  redeploy", not "Investigate queue issue").
- Bug tickets: exact repro (versions, commands, input), expected vs. actual
  with real output pasted, frequency.
- Acceptance criteria are testable or they aren't criteria — a command and
  the output that means done, not "works correctly".
- Link instead of repeating prior tickets/design doc/alert; empty is a
  valid field value, not something to pad with prose.

## Technical articles & blog posts

Motivated by a real problem the author actually hit; uneven by design.

- Open at the incident or the number that made you look, not a topic
  survey of the thing every reader already knows.
- One stated opinion, as yours, with the condition that would change it
  ("if your writes are under 1k/s, ignore all of this").
- Depth budget by interest, not symmetry — the surprising section gets far
  more space than the setup steps; include what broke and what you tried
  first, since no failure anywhere reads as fabricated confidence.
- Numbers carry conditions (machine, version, dataset size, run count);
  code is real and tested, or marked as a sketch.
- End on the recommendation or open question you actually have, not a
  both-sides summary plus a generic future-outlook paragraph.
