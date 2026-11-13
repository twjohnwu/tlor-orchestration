---
id: authn.session
name: Session Management, Tokens, JWT and CSRF
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

# Session Management, Tokens, JWT and CSRF

## Task Signals
- issue, store or read a session cookie or a bearer token after login
- set cookie flags, token lifetime, idle timeout or "remember me"
- sign out, revoke a token, or end all sessions after a password change
- create, sign or verify a JSON Web Token (JWT) or another self-contained token
- protect a state-changing browser request against cross-site forgery
- choose between server-side sessions and stateless tokens

## Applies When
- The server keeps a caller logged in across requests by means of an id or a token.
- A token carries identity or claims and the server must decide whether to trust it.
- A browser sends credentials automatically (cookies) to an endpoint that changes state.

## Does Not Apply When
- The task is about the login step, password rules or recovery: use `authn.authentication`.
- The task is about what the signed-in user may access: use `authz.access_control`.
- The task is about general key handling or algorithm choice outside tokens: use `crypto.secrets`.
- The task is about API-wide design such as versioning or schemas: use `api.web_api`.

## Requirements
1. Generate session ids and opaque tokens with a cryptographically secure random source, with enough length that guessing is impractical, and carry no meaning in the value. [ASVS v5.0.0 V7.2; CWE-330]
2. Issue a new session id at login and at any privilege change, and refuse ids that the server did not create. [ASVS v5.0.0 V7.2; CWE-384]
3. Set session cookies with the Secure and HttpOnly attributes, a restrictive SameSite value, a narrow path and no wide domain. [ASVS v5.0.0 V3.3; CWE-614; CWE-1004]
4. Keep session state on the server, or in a token the server can verify; never trust a session value that the client can edit. [ASVS v5.0.0 V7.2]
5. Enforce an idle timeout and an absolute lifetime on the server, chosen from the risk of the application, and re-ask for a credential before sensitive actions. [ASVS v5.0.0 V7.3; OWASP Top 10 2025 A07]
6. Make logout end the session on the server, delete the cookie, and revoke any refresh or long-lived token. [ASVS v5.0.0 V7.4]
7. End or revoke other sessions after a password change, a factor change or an account takeover report. [ASVS v5.0.0 V7.4]
8. Verify a JWT before use: check the signature with a key and algorithm fixed by the server, reject `none` and any algorithm the header asks for, and check issuer, audience, expiry and not-before. [ASVS v5.0.0 V9.1; ASVS v5.0.0 V9.2; CWE-287]
9. Select the verification key by a trusted key id from a server-controlled set; never take a key or key URL from the token. [ASVS v5.0.0 V9.1; CWE-287]
10. Keep access tokens short-lived, rotate refresh tokens on use and detect their reuse, and keep a revocation path for stateless tokens. [ASVS v5.0.0 V7.3; ASVS v5.0.0 V7.4]
11. Put no secret or needless personal data in a token payload; a signed token is readable by its holder. [ASVS v5.0.0 V9.2]
12. Protect every state-changing request that relies on cookies with a CSRF defense: a per-session unpredictable token or a framework equivalent, plus SameSite cookies, and never change state on a GET. [ASVS v5.0.0 V3.5; CWE-352]
13. Review session and token code during secure-coding review. [NIST SSDF 1.1 PW.5; ISO/IEC 27002:2022 8.28]

## Implementation Notes
- A server-side session store gives easy revocation; a stateless token trades that for scale, so add a deny list or a short lifetime to compensate.
- Do not place a bearer token in a URL, where logs, history and referrer headers keep it. Use the Authorization header or a cookie.
- In a browser, a token held in script-readable storage is exposed to any script injection; an HttpOnly cookie is not, though it then needs CSRF protection.
- Fix the accepted algorithm list in configuration, not in the token. With a library, pass the expected algorithm to the verify call explicitly.
- Compare issuer and audience to exact expected values; a token minted for another service must fail here.
- Clock skew allowance for expiry checks should be small and stated.
- A CSRF token must be bound to the session and checked on the server; a double-submit value alone is weaker unless it is signed or bound.
- Cross-origin read access (CORS) is not CSRF protection; do not widen it to make a form work.

## Review Checklist
- [ ] Grep for `Math.random`, `rand(`, `random.random`, `uuid1`, timestamps used to build a session id or token; each must be a secure random source.
- [ ] Grep for `Set-Cookie`, `set_cookie`, `cookie(`, `session.cookie`; read the flags for Secure, HttpOnly, SameSite, path and domain.
- [ ] Read the login success path; the session id is regenerated there (grep `regenerate`, `rotate`, `invalidate`, `changeSessionId`).
- [ ] Read the logout handler; the server-side record or token is destroyed, not only the client cookie.
- [ ] Grep for `jwt.decode`, `verify=False`, `algorithms`, `alg`, `none`, `ignoreExpiration`; verification runs, the algorithm list is fixed, and expiry is checked.
- [ ] Grep for `jwk`, `jku`, `kid` handling; keys come from a server-side set only.
- [ ] Grep for `exp`, `iat`, `aud`, `iss` in token creation and checks; lifetimes are short and audience and issuer are compared.
- [ ] Grep for `localStorage`, `sessionStorage` near `token`; any hit is a decision recorded with its injection risk.
- [ ] Grep for `csrf`, `xsrf`, `SameSite`, `csrf_exempt`, `@csrf`; every cookie-authenticated state-changing route is covered, and exemptions are justified.
- [ ] Grep for route handlers that change data on `GET`; none should exist.
- [ ] Check that tests exist for the cases under Test Ideas.

## Common Failure Modes
- Session id kept unchanged across login, so a planted id becomes an authenticated one.
- JWT decoded without verifying the signature, or verified with the algorithm named in the header.
- Tokens that never expire, or logout that only clears the browser copy.
- Refresh token reused forever, or stolen and never detected.
- A shared signing key between services with different trust levels, or a key committed to the repo.
- Missing Secure or HttpOnly flags on the cookie, or SameSite set to none without need.
- CSRF check skipped for JSON endpoints on the belief that JSON is safe by itself.
- Sensitive claims kept in the payload and trusted without checking server data.

## Test Ideas
- Log in with a pre-set session id; after login the id differs and the old one no longer works.
- Log out, then replay the old cookie or token against a protected route; it is refused.
- Change the password in one session; the second session is ended.
- Send a JWT with `alg` set to `none`, one with a changed payload and old signature, and one with a wrong audience; each is refused.
- Send an expired token and one with a future not-before; each is refused.
- Read the response headers after login; the cookie has Secure, HttpOnly and a SameSite value.
- Submit a state-changing request from a foreign origin without the CSRF token; it fails. With a token from another session, it also fails.
- Use a refresh token twice; the second use fails and the family is revoked.

## Related Entries
- authn.authentication: how the user proved identity before the session began.
- authz.access_control: a valid session does not grant permission to every object.
- crypto.secrets: signing keys, random sources and secret storage.
- api.web_api: token use in API clients and cross-origin settings.
- input.injection: script injection steals tokens that script can read.
- ops.logging_errors: keep tokens and session ids out of logs.

## Sources
- OWASP ASVS 5.0.0, chapter V7 Session Management (sections 7.2 Fundamental Session Management Security, 7.3 Session Timeout, 7.4 Session Termination), chapter V9 Self-contained Tokens (sections 9.1 Token source and integrity, 9.2 Token content), and chapter V3 Web Frontend Security (sections 3.3 Cookie Setup, 3.5 Browser Origin Separation): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html
- OWASP Top 10:2025, A07:2025 Authentication Failures: https://top10.owasp.org/2025
- MITRE CWE: CWE-287, CWE-330, CWE-352, CWE-384, CWE-614, CWE-1004 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
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
