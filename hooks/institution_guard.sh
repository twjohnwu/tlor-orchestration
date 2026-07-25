#!/usr/bin/env bash
# Institution guard — bash fallback (active only when TLOR_INSTITUTION_GUARD=1).
# Blocks main session from editing institution files: everything under
# ~/.claude/institution/ (real paths), the ~/.claude/rules/ and
# ~/.claude/agents/ symlink aliases, and CLAUDE.md/AGENTS.md anywhere.
# Subagents (agent_id present) pass through. Fail-open on any error.
[ "${TLOR_INSTITUTION_GUARD}" = "1" ] || exit 0
set -uo pipefail
command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null) || exit 0
case "$tool_name" in
  Edit|Write|NotebookEdit) ;;
  *) exit 0 ;;
esac
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2>/dev/null) || exit 0
agent_id=$(printf '%s' "$input" | jq -r '.agent_id // empty' 2>/dev/null) || exit 0
[ -n "$file" ] || exit 0
# Subagents are allowed
[ -z "$agent_id" ] || exit 0
home="${HOME}"
# Check institution file patterns (home-anchored prefixes + router files anywhere)
case "$file" in
  "${home}/.claude/institution/"*|"${home}/.claude/rules/"*|"${home}/.claude/agents/"*|*/CLAUDE.md|CLAUDE.md|*/AGENTS.md|AGENTS.md)
    jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"Institution file: the main session must not edit ~/.claude institution files (rules/agents/hooks) or CLAUDE.md/AGENTS.md inline. Author the full new text as a recipe and dispatch it to a subagent (dispatch.md §1). This does not block dispatched subagents."}}'
    exit 0
    ;;
esac
exit 0
