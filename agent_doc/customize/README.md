# agent_doc/customize — user-owned overlay

Files here are NEVER touched by install.sh or plugin upgrades once they
exist. A role that reads `~/.claude/agent_doc/<name>.md` also reads
`~/.claude/agent_doc/customize/<name>.md` when it exists — put
machine-specific detail (local script paths, version-pinned flag behavior)
here and keep the base file generic.
