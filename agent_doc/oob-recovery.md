# oob-recovery.md — A subagent edited outside its dispatch scope

Back up the bad state FIRST (`cp X X.bak-YYYYMMDD`). Inside a version-
controlled project, use `git diff` to identify and revert ONLY the
out-of-scope hunks — never whole-file `git checkout`, which destroys
in-scope uncommitted work. Outside version control, restore from the
pre-edit backup the T2 protocol required; if none exists, treat as T1 data
loss and tell the user before touching anything else.
