---
id: input.injection
name: Input Validation, Injection and Output Encoding
category: [input]
confidence: high
verified: 2026-11-13
sources:
  - name: OWASP ASVS
    version: 5.0.0
    url: https://asvs.owasp.org/
  - name: OWASP Cheat Sheet Series
    version: retrieved 2026-11-13
    url: https://cheatsheetseries.owasp.org/
  - name: OWASP Top 10
    version: 2025
    url: https://top10.owasp.org/2025
  - name: MITRE CWE Top 25
    version: 2025 list
    url: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
  - name: NIST SP 800-218 SSDF
    version: 1.1
    url: https://csrc.nist.gov/pubs/sp/800/218/final
  - name: ISO/IEC 27002
    version: 2022
    url: https://www.iso.org/standard/75652.html
---

# Input Validation, Injection and Output Encoding

## Task Signals
- build a query from request data; search, filter or sort by a user-supplied field
- run a shell command, spawn a process, or call a tool with user-supplied arguments
- render user-supplied text into HTML, an attribute, a script block, a URL or a template
- user input reaches a directory query (LDAP filter) or a document query
- parse, validate or sanitize form fields, query strings, headers or JSON bodies

## Applies When
- Any value that crosses a trust boundary is placed inside a string that another interpreter will parse: SQL, shell, template engine, LDAP, HTML, JavaScript, CSS or a URL.
- A feature accepts structured input and the code must decide what a valid value is.
- A reviewer must judge whether a data flow from request to interpreter is safe.

## Does Not Apply When
- The task is about who may call an operation or read a record: use `authz.access_control`.
- The input is a file or a path, not text for an interpreter: use `files.upload_and_paths`.
- The input is a URL the server will fetch: use `network.ssrf_outbound`.
- The input is a serialized object graph: use `data.deserialization`.
- The input is text sent to a language model: use `llm.applications`.

## Requirements
1. Keep data and command separate: pass user values to a SQL engine only as bound parameters of a prepared statement, never by joining strings. [ASVS v5.0.0 V1.2; CWE-89; OWASP Top 10 2025 A05]
2. Run external programs through an API that takes an argument vector, with no shell; when a shell cannot be avoided, accept only values from a fixed allowlist. [ASVS v5.0.0 V1.2; CWE-78]
3. Never build template source from user input; give the template engine user values only as data bound to a variable, in a sandboxed or logic-less mode. [ASVS v5.0.0 V1.2; CWE-94; CWE-74]
4. Build directory (LDAP) filters and distinguished names with the library's escaping function for that exact context, or a parameterized filter API. [ASVS v5.0.0 V1.2; CWE-74]
5. Encode every untrusted value for the exact output context at the point it is written: HTML body, attribute, JavaScript, CSS and URL each need a different encoder. [ASVS v5.0.0 V1.2; CWE-79; CWE-116]
6. Prefer a framework that encodes by default; mark a raw-output escape hatch as a reviewed exception with a comment naming the source of the data. [ASVS v5.0.0 V1.2; CWE-79]
7. Validate input on the server for type, length, range and format against an allowlist, before use; reject on failure instead of repairing. [ASVS v5.0.0 V2.2; CWE-20]
8. Treat validation as a second layer, not a substitute for parameterization or encoding. [ASVS v5.0.0 V1; CWE-20]
9. Canonicalize and decode once, then validate the decoded value; never validate and then decode again. [ASVS v5.0.0 V1.1; CWE-20]
10. Pass identifiers that cannot be parameterized (table, column, sort direction) through a fixed map of allowed values. [ASVS v5.0.0 V1.2; CWE-89]
11. Run static analysis or code review for injection sinks as part of the secure-coding step. [NIST SSDF 1.1 PW.5; ISO/IEC 27002:2022 8.28]

## Implementation Notes
- Find the sinks first: every call that executes a query, spawns a process, renders a template or writes HTML. Trace each argument back to its source.
- Parameterized queries cover values only. Names of tables, columns and sort order need the allowlist map from requirement 10.
- Stored procedures and ORMs are safe only while they bind values; a raw-query escape hatch or string-built `ORDER BY` reopens the hole.
- Shell avoidance example, shown because the shape matters:

```
run(["convert", user_file, "out.png"], shell=False)   # arguments stay separate
```

- Encode late, at output, for the context in use. Data encoded early for HTML is wrong in a JavaScript or URL context.
- A Content-Security-Policy header limits the damage of a missed encoding; it does not replace encoding.
- Log rejected input at a level that cannot itself be used for log injection; see `ops.logging_errors`.

## Review Checklist
- [ ] Grep for `execute(`, `query(`, `raw(`, `exec(` and `Statement` near string concatenation, `+`, `f"` or `format(`; every hit must pass values as bound parameters.
- [ ] Grep for `shell=True`, `os.system`, `Runtime.exec`, `child_process.exec`, `popen` and backticks; each hit has no user data or uses an allowlist.
- [ ] Grep for template calls that take a string source (`render_template_string`, `Template(`, `eval(`); the source must be a constant.
- [ ] Grep for raw-output markers (`innerHTML`, `dangerouslySetInnerHTML`, `|safe`, `v-html`, `<%-`, `Html.Raw`); each has a comment and a trusted source.
- [ ] Read each LDAP search call; the filter uses an escape function or parameters.
- [ ] Read each `ORDER BY` or dynamic column; the name comes from a fixed map.
- [ ] Read the validation code at each entry point; it checks type, length and allowlist on the server, and failure rejects the request.
- [ ] Check that a test exists for each sink class found (see Test Ideas).

## Common Failure Modes
- Parameterizing the `WHERE` value but concatenating the sort column or a `LIMIT` value.
- Escaping quotes by hand and calling it safe; encoding for the wrong context.
- Validating on the client only; the server trusts the form.
- Passing user text to `sh -c` to get globbing or pipes, or building a command string with quotes.
- Encoding on input and storing the encoded form, then double-encoding or under-encoding at output.
- Blocklist filters (strip `<script>`, forbid `;`) bypassed by case, encoding or alternative syntax.
- Trusting a value because it came from a database, a header or an internal service, when an earlier user wrote it.

## Test Ideas
- Send a quote, a comment marker and a boolean tautology through every string field; the response and row count must be unchanged from a benign value.
- Send shell metacharacters (`;`, `|`, `$(`, backtick, newline) to each command-running feature; no extra process starts and the value is treated as one argument.
- Send template expression syntax for the engine in use; the output shows the text unevaluated.
- Send markup and script as a profile field; the rendered page shows text, and the same value in an attribute and a script context stays inert.
- Send LDAP filter metacharacters (`*`, `(`, `)`, `\`) as a username; the lookup matches nothing extra.
- Send an unknown sort column and an overlong, wrong-type or empty value; each is rejected with a client error.

## Related Entries
- authz.access_control: injection that bypasses a filter often defeats authorization checks that rely on the same query.
- data.deserialization: untrusted structured data that becomes code or objects.
- network.ssrf_outbound: user input that steers a server-side request.
- files.upload_and_paths: path and file-name inputs.
- ops.logging_errors: log injection and error messages that echo input.
- api.web_api: request schema validation and mass assignment at the API layer.
- llm.applications: prompt injection, a similar data-versus-instruction confusion.

## Sources
- OWASP ASVS 5.0.0, chapter V1 Encoding and Sanitization (sections 1.1 Encoding and Sanitization Architecture, 1.2 Injection Prevention) and chapter V2 Validation and Business Logic (section 2.2 Input Validation): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- OWASP Top 10:2025, A05:2025 Injection: https://top10.owasp.org/2025/A05_2025-Injection
- MITRE CWE: CWE-20, CWE-74, CWE-78, CWE-79, CWE-89, CWE-94, CWE-116 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
- NIST SP 800-218 v1.1, practice PW.5 Create Source Code by Adhering to Secure Coding Practices: https://csrc.nist.gov/pubs/sp/800/218/final
- ISO/IEC 27002:2022, control 8.28 Secure coding (number and title only): https://www.iso.org/standard/75652.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP ASVS 5.0.0: CC BY-SA 4.0.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- OWASP Top 10 2025: the published site pages state CC BY 3.0; the repository LICENSE file states CC BY-SA 4.0. Both statements are recorded here because the conflict was not resolved.
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
- NIST SP 800-218: not subject to copyright in the United States; attribution given.
- ISO/IEC 27002:2022: copyrighted by ISO; only the control number and title are cited, never its text or guidance.
