---
id: ops.logging_errors
name: Security Logging, Log Hygiene and Error Handling
category: [ops]
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

# Security Logging, Log Hygiene and Error Handling

## Task Signals
- add logging, audit trails or alerts to a feature; decide which events to record
- write an error handler, an exception filter or an error page
- log a request, a header, a form body or an exception with its context
- show a stack trace, a database message or a debug page to a caller
- keep passwords, tokens, card numbers or personal data out of logs

## Applies When
- Code writes a log line or an audit record that includes data from a request, a user or a secret store.
- A failure path decides what the caller sees and whether the operation continues or stops.
- A reviewer must judge whether security-relevant events are recorded, and recorded safely.

## Does Not Apply When
- The task is the access decision itself: use `authz.access_control`.
- The task is how a login or session is validated: use `authn.authentication` or `authn.session`.
- The task is how secrets are stored or rotated: use `crypto.secrets`.
- The task is a flaw in text handed to an interpreter: use `input.injection`.

## Requirements
1. Record security events: logins and failures, access-control denials, input validation failures, privilege and configuration changes, and administrative actions. [ASVS v5.0.0 V16.3; OWASP Top 10 2025 A09; CWE-778]
2. Give each log record a timestamp, an event type, an outcome, the acting account and a request or correlation id. [ASVS v5.0.0 V16.2; OWASP Top 10 2025 A09]
3. Keep passwords, session ids, tokens, keys and full payment or identity numbers out of every log, and mask or drop them at the logging layer. [ASVS v5.0.0 V16.2; ASVS v5.0.0 V13.4; CWE-532]
4. Log personal data only when the purpose requires it, in the least identifying form, and set a retention period. [ASVS v5.0.0 V16.1; CWE-532]
5. Encode or escape line breaks and control characters in any value taken from a client before it goes into a log line, or use a structured format that quotes values. [ASVS v5.0.0 V16.4; CWE-117]
6. Protect logs from change and from reading by people who do not need them, and send them to a separate store when possible. [ASVS v5.0.0 V16.4; OWASP Top 10 2025 A09]
7. Return a generic message and an error id to the caller, and keep stack traces, query text, file paths and library versions in the server log only. [ASVS v5.0.0 V16.5; CWE-209; CWE-200]
8. Turn debug output and verbose error pages off in production builds and configuration. [ASVS v5.0.0 V13.4; CWE-215; NIST SSDF 1.1 PW.9]
9. Fail closed: when a security check, a parser or a dependency throws, deny the operation instead of continuing as if it had passed. [ASVS v5.0.0 V16.5; OWASP Top 10 2025 A10]
10. Handle every exception path explicitly with one central handler, and never swallow an error silently in security-relevant code. [ASVS v5.0.0 V16.5; OWASP Top 10 2025 A10]
11. Review logging and error-handling code as part of secure coding and code analysis. [NIST SSDF 1.1 PW.5; NIST SSDF 1.1 PW.7; ISO/IEC 27002:2022 8.28]

## Implementation Notes
- Decide the event list from the threat model: anything an investigator would need to rebuild who did what, and anything an alert would key on.
- Use structured logging with named fields. Values are then quoted by the format, which removes most of the line-forging risk.
- Redact by field name at the logger, not at each call site. A denylist of names such as `password`, `token`, `authorization`, `cookie` and `secret` catches most leaks; add data types known to the product.
- Log the decision and the reason code, not the sensitive input that led to it.
- Error handler shape:

```
try: do_operation()
except KnownClientError as e: respond(400, generic(e.code))
except Exception as e:
    log.error("op failed", error_id=new_id(), exc=e)   # detail stays server-side
    respond(500, {"error_id": id})                      # generic body; deny
```

- The caller-visible error should not tell an attacker which of two checks failed when that difference helps them, for example "user unknown" versus "wrong password."
- Alerts need an owner and a threshold. A log nobody reads is not detection.
- Time must come from a synchronized clock so records from different services can be ordered.
- Log writing must not break the request: a full disk or an unreachable log sink should raise an alert, and the policy for what the service does then should be written down.

## Review Checklist
- [ ] Grep for logger calls (`log.`, `logger.`, `console.log`, `print(`, `Log.`, `slog`) that include `password`, `token`, `secret`, `authorization`, `cookie`, `card`, or a whole request or body object; each is redacted or removed.
- [ ] Read the logger configuration; a redaction filter or masking rule exists, and debug level is not the production default.
- [ ] Grep for `printStackTrace`, `traceback`, `exc_info`, `stack`, `err.message` or exception text inside response bodies; none reaches the caller.
- [ ] Read the central error handler or exception filter; it returns a generic body and an error id and logs the detail privately.
- [ ] Grep for empty or silent handlers (`except: pass`, `catch {}`, `catch (e) { }`, `_ = err`, `.catch(() => {})`) in authentication, access and parsing code; each is removed or justified.
- [ ] Read each security check's error path; an exception results in denial, not in the protected code running.
- [ ] Grep for debug switches (`DEBUG = True`, `debug: true`, `app.debug`, `ASPNETCORE_ENVIRONMENT`, dev error pages); production settings turn them off.
- [ ] Read where log lines are built from client values (user agent, name, URL, header); line breaks and control characters are escaped or the format quotes values.
- [ ] Read the event list in the code; login results, access denials, validation failures and admin changes are each recorded with account and correlation id.
- [ ] Check that tests exist for the cases listed under Test Ideas.

## Common Failure Modes
- Logging the full request, including the password field, the bearer token or the session cookie, "for debugging."
- Writing raw client text into a line-based log, so a name containing a line break forges a second record.
- Returning the exception text or a database error to the caller, which reveals table names, paths or versions.
- An empty catch around a check, so a failure silently lets the operation through.
- Logging nothing about denials or failed logins, leaving no trail for investigation.
- Logs readable by every developer or service account, or editable by the application that writes them.
- Keeping personal data in logs with no retention limit.
- Different error text for "no such user" and "wrong password," or for found and not-found records the caller may not see.

## Test Ideas
- Log in with a known test password and a bearer token, then search all log output for those values; none is found.
- Send a username containing a line break and a fake log prefix; the log shows one record with the characters escaped or quoted.
- Trigger an unhandled exception in a request; the response has a generic message and an error id, and the log holds the detail under that id.
- Force a failure in an authorization or validation component; the request is denied.
- Run a failed login, an access denial and a validation failure; each leaves one record with time, event, outcome, account and correlation id.
- Start the service with production settings and request a missing route and a malformed body; no debug page, trace or version string appears.
- Make the log sink unavailable; the service behaves as the written policy says and raises an alert.

## Related Entries
- input.injection: log injection is injection into a log interpreter; also validation failure events.
- authn.authentication: events and generic messages for login, reset and lockout.
- authn.session: never log session ids or tokens.
- authz.access_control: record denials and privilege changes.
- crypto.secrets: secrets that must never reach logs.
- data.deserialization: log failure classes, not hostile payloads.
- files.upload_and_paths: escape client-supplied file names in logs.
- network.ssrf_outbound: generic errors for refused outbound requests.

## Sources
- OWASP ASVS 5.0.0, chapter V16 Security Logging and Error Handling (sections 16.1 Security Logging Documentation, 16.2 General Logging, 16.3 Security Events, 16.4 Log Protection, 16.5 Error Handling) and chapter V13 Configuration (section 13.4 Unintended Information Leakage): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Vocabulary_Cheat_Sheet.html
- OWASP Top 10:2025, A09:2025 Security Logging and Alerting Failures and A10:2025 Mishandling of Exceptional Conditions: https://top10.owasp.org/2025
- MITRE CWE: CWE-117, CWE-200, CWE-209, CWE-215, CWE-532, CWE-778 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); CWE-200 is item 20 in the 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
- NIST SP 800-218 v1.1, practices PW.5 Create Source Code by Adhering to Secure Coding Practices, PW.7 Review and/or Analyze Human-Readable Code to Identify Vulnerabilities and Verify Compliance with Security Requirements, and PW.9 Configure Software to Have Secure Settings by Default: https://csrc.nist.gov/pubs/sp/800/218/final
- ISO/IEC 27002:2022, control 8.28 Secure coding (number and title only): https://www.iso.org/standard/75652.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP ASVS 5.0.0: CC BY-SA 4.0.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- OWASP Top 10 2025: the published site pages state CC BY 3.0; the repository LICENSE file states CC BY-SA 4.0. Both statements are recorded here because the conflict was not resolved.
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
- NIST SP 800-218: not subject to copyright in the United States; attribution given.
- ISO/IEC 27002:2022: copyrighted by ISO; only the control number and title are cited, never its text or guidance.
