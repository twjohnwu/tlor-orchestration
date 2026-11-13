---
id: authn.authentication
name: Authentication, Password Storage and Credential Recovery
category: [authn]
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

# Authentication, Password Storage and Credential Recovery

## Task Signals
- add or change a login, sign-up, or "log in with" flow
- store, hash, compare or migrate user passwords
- set a password policy, a lockout rule or a login rate limit
- add a second factor (one-time code, authenticator app, hardware key)
- build "forgot password", account recovery or email-change confirmation
- protect an endpoint that must only be reached by a signed-in user

## Applies When
- The code decides who a caller is, using a password, a code, a key or another credential.
- A credential, a hash of one, or a reset token is created, stored, checked or replaced.
- A reviewer must judge whether login and recovery paths resist guessing and stuffing.

## Does Not Apply When
- The task is about what happens after login (cookies, tokens, logout, CSRF): use `authn.session`.
- The task is about what a known user may do or see: use `authz.access_control`.
- The task is about choosing a cipher, a key store or a random source in general: use `crypto.secrets`.
- The task is logging of login events or error text: use `ops.logging_errors`.

## Requirements
1. Require authentication on every route and operation that is not meant to be public, and fail closed when the identity cannot be established. [ASVS v5.0.0 V6.3; CWE-306; CWE-287; OWASP Top 10 2025 A07]
2. Store passwords only as output of a slow, salted, purpose-built password hash (Argon2id, scrypt, bcrypt or PBKDF2), with cost settings reviewed on a schedule. [ASVS v5.0.0 V11.4; CWE-916; CWE-759]
3. Never store a password in plaintext or in a reversible form, and never write it to a log or an error message. [ASVS v5.0.0 V11.4; ASVS v5.0.0 V16.2; CWE-256]
4. Accept long passphrases, allow all printable characters and spaces, and reject only known-breached or obviously weak values; do not impose composition rules or forced periodic changes. [ASVS v5.0.0 V6.2; CWE-521]
5. Let the user paste into the password field and use a password manager; never truncate or silently alter the value before hashing. [ASVS v5.0.0 V6.2; CWE-521]
6. Compare secrets and hashes with a constant-time function and give the same response, status and timing shape for an unknown user and a wrong password. [ASVS v5.0.0 V6.3; CWE-287]
7. Limit repeated failed attempts per account and per source with throttling or temporary lockout, and watch for credential stuffing across many accounts. [ASVS v5.0.0 V6.3; CWE-307; OWASP Top 10 2025 A07]
8. Offer a second factor and require it for privileged or high-impact actions; accept only a factor the server verifies, never a client-reported result. [ASVS v5.0.0 V6.5; CWE-287]
9. Make recovery no weaker than login: send a single-use, random, short-lived reset token to a verified channel, store only its hash, and invalidate it after use. [ASVS v5.0.0 V6.4; CWE-640]
10. Do not use knowledge questions or reveal whether an account exists during recovery; show the same message either way. [ASVS v5.0.0 V6.4; CWE-640]
11. Require the current credential or a fresh second factor before changing a password, email address or factor, and end other sessions afterwards. [ASVS v5.0.0 V6.2; ASVS v5.0.0 V7.5; CWE-287]
12. Remove default, shared and hard-coded accounts and credentials before release. [ASVS v5.0.0 V6.3; CWE-798]
13. Review login, hashing and recovery code against the secure-coding practice and the application security requirements. [NIST SSDF 1.1 PW.5; ISO/IEC 27002:2022 8.28; ISO/IEC 27002:2022 8.26]

## Implementation Notes
- Use the hashing function of the framework or a maintained library; do not write a custom scheme or chain fast hashes by hand.
- Store the algorithm, cost and salt with each hash so the cost can be raised later; rehash at the next successful login when the stored cost is below target.
- When migrating from a weak hash, wrap the old hash inside the new one, or rehash at login, and plan the end date for old rows.
- Check the breached-password list at set time through a local list or a range-style lookup that never sends the full password out.
- A lockout that can be triggered by anyone is itself a denial-of-service tool; prefer delays and per-source limits, and notify the owner.
- Keep recovery tokens out of URLs that reach logs or referrer headers where possible, and set a short expiry.
- Prefer phishing-resistant factors (hardware keys, passkeys) over codes sent by SMS or email for sensitive accounts.
- Session creation after a successful login belongs to `authn.session`; renew the session id at that moment.

## Review Checklist
- [ ] Grep for `md5`, `sha1`, `sha256`, `hashlib`, `MessageDigest` near `password`; any plain or fast hash of a password is a finding.
- [ ] Grep for `bcrypt`, `argon2`, `scrypt`, `pbkdf2`, `PasswordEncoder`; read the cost parameters and confirm a salt is generated per user.
- [ ] Grep for `==` or `equals(` comparing a password, token or hash; each must use a constant-time compare.
- [ ] Read the login handler; unknown user and wrong password return the same body, status and similar timing.
- [ ] Grep for `maxlength`, `max_length`, `substring` and regex rules on password fields; no short cap, no composition rules, no silent truncation.
- [ ] Read the rate-limit or lockout code on login, reset and one-time-code endpoints; each endpoint has a limit.
- [ ] Read the reset flow; the token is random, hashed at rest, single-use, expires, and the response does not reveal account existence.
- [ ] Grep for route definitions and middleware lists; every non-public route passes through the authentication check.
- [ ] Grep for `password =`, `admin`, `default` in source, seeds and config; no shipped credentials.
- [ ] Check that tests exist for the cases under Test Ideas.

## Common Failure Modes
- A fast general-purpose hash, or one global salt, protects passwords.
- Login says "no such user" for one case and "wrong password" for another, and timing differs as well.
- No limit on the reset, one-time-code or API-key endpoints, so the second factor is brute-forced.
- Recovery by security question, or a reset link that stays valid after use or after a new request.
- Second factor checked on the page but not on the server call that does the work.
- One endpoint added later without the authentication middleware.
- A password change that does not need the old password and leaves old sessions alive.
- Passwords or reset tokens appear in request logs or analytics.

## Test Ideas
- Log in with a real user and a wrong password, then with an unknown user; compare status, body and response time.
- Send many wrong passwords for one account and then one wrong password for many accounts; the throttle reacts in both cases.
- Set a 64-character passphrase with spaces and Unicode; it is accepted and verifies later.
- Set a password from a known breached list; it is refused.
- Request a reset twice, use the first token; it fails. Use the second token twice; the second use fails.
- Request a reset for an unknown email; the response matches the response for a known email.
- Call a protected endpoint with no credential and with an expired one; each gets an authentication error.
- Skip the second-factor step by calling the final endpoint directly; the call is refused.

## Related Entries
- authn.session: what to issue and how to expire it after a successful login.
- authz.access_control: the next question after identity, what the user may do.
- crypto.secrets: hashing primitives, randomness for tokens and key handling.
- ops.logging_errors: what to record about failed logins without recording secrets.
- api.web_api: API keys and tokens for machine callers.
- input.injection: injection in the login query is a bypass of everything above.

## Sources
- OWASP ASVS 5.0.0, chapter V6 Authentication (sections 6.2 Password Security, 6.3 General Authentication Security, 6.4 Authentication Factor Lifecycle and Recovery, 6.5 General Multi-factor authentication requirements), chapter V7 Session Management (section 7.5 Defenses Against Session Abuse), chapter V11 Cryptography (section 11.4 Hashing and Hash-based Functions) and chapter V16 Security Logging and Error Handling (section 16.2 General Logging): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.html
- OWASP Top 10:2025, A07:2025 Authentication Failures: https://top10.owasp.org/2025
- MITRE CWE: CWE-256, CWE-287, CWE-306, CWE-307, CWE-521, CWE-640, CWE-759, CWE-798, CWE-916 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
- NIST SP 800-218 v1.1, practice PW.5 Create Source Code by Adhering to Secure Coding Practices: https://csrc.nist.gov/pubs/sp/800/218/final
- ISO/IEC 27002:2022, controls 8.26 Application security requirements and 8.28 Secure coding (numbers and titles only): https://www.iso.org/standard/75652.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP ASVS 5.0.0: CC BY-SA 4.0.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- OWASP Top 10 2025: the published site pages state CC BY 3.0; the repository LICENSE file states CC BY-SA 4.0. Both statements are recorded here because the conflict was not resolved.
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
- NIST SP 800-218: not subject to copyright in the United States; attribution given.
- ISO/IEC 27002:2022: copyrighted by ISO; only the control number and title are cited, never its text or guidance.
