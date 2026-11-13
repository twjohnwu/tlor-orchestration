---
id: crypto.secrets
name: Cryptography, Randomness, Key Management and Secrets Handling
category: [crypto]
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

# Cryptography, Randomness, Key Management and Secrets Handling

## Task Signals
- encrypt, decrypt, sign, hash or verify data in application code
- generate a token, nonce, salt, key, reset code or other unpredictable value
- store, load, rotate or share an API key, database password, signing key or certificate
- read a secret from config, an environment variable or a secret manager
- find a password, key or token written in source, a config file, an image or a log
- choose TLS settings or a cipher mode for data at rest or in transit

## Applies When
- The code protects data with a cryptographic primitive, or needs a value that an attacker must not predict.
- A secret must reach the running program, be kept, be changed or be removed.
- A reviewer must judge whether keys and credentials are exposed through code, config, history or logs.

## Does Not Apply When
- The task is password hashing, login policy or recovery: use `authn.authentication`.
- The task is session ids, cookies or JWT validation: use `authn.session`.
- The task is which fields appear in logs or error text: use `ops.logging_errors`.
- The task is checking third-party packages for known flaws: use `supply.dependencies`.

## Requirements
1. Use well-reviewed algorithms from a maintained library: an authenticated encryption mode for data at rest, modern hashes for integrity, and a standard signature scheme; never invent a primitive or a protocol. [ASVS v5.0.0 V11.3; CWE-327]
2. Refuse broken or risky algorithms and modes (MD5, SHA-1 for security use, DES, RC4, ECB mode) and keys too short for the purpose. [ASVS v5.0.0 V11.3; CWE-327; CWE-326]
3. Draw every security-relevant random value (tokens, nonces, salts, keys, codes) from the platform's cryptographically secure generator, not from a general-purpose one. [ASVS v5.0.0 V11.5; CWE-330]
4. Never reuse a nonce or initialization vector where the mode forbids it; take a fresh random or counter value for each message. [ASVS v5.0.0 V11.3]
5. Keep a list of where cryptography is used, which algorithm and key each use relies on, and a plan to swap them. [ASVS v5.0.0 V11.1]
6. Generate keys with the secure source, keep them out of application memory dumps and storage where practical, and use a key manager or hardware module for high-value keys. [ASVS v5.0.0 V11.1; ASVS v5.0.0 V13.3]
7. Separate keys by purpose and environment, rotate them on a schedule and after any suspected exposure, and support rollover without downtime. [OWASP Top 10 2025 A04]
8. Keep secrets (credentials, keys, tokens) out of source code, images, client bundles and version history; supply them at run time from a secret store or the environment. [ASVS v5.0.0 V13.3; CWE-798; CWE-259; CWE-321]
9. Give each service its own least-privilege, revocable credential, and prefer short-lived credentials over long-lived static ones. [ASVS v5.0.0 V13.3; CWE-798]
10. Keep secrets out of logs, error messages, URLs, debug output and crash reports. [ASVS v5.0.0 V13.3; ASVS v5.0.0 V13.4; CWE-532; CWE-215]
11. Encrypt sensitive data at rest and in transit, and do not send or store it in clear text. [CWE-311; CWE-312; CWE-319; OWASP Top 10 2025 A04]
12. Treat a leaked secret as compromised: rotate it first, then clean history; deletion from the repository alone is not remediation. [ASVS v5.0.0 V13.3; CWE-798]
13. Review cryptographic and secrets code during secure-coding review and static analysis. [NIST SSDF 1.1 PW.5; ISO/IEC 27002:2022 8.28]

## Implementation Notes
- Use a high-level library API (a sealed-box or AEAD helper) so the nonce, tag and mode are not chosen by hand.
- Derive several keys from one master secret with a key-derivation function and distinct context labels, not by reusing the same key.
- Compare MACs and tokens in constant time.
- Secret scanning in pre-commit and in CI catches most leaks early; run it over history once when adopting it.
- Environment variables are an acceptable carrier, yet they show up in process listings and crash dumps; a secret manager with audit is better for high-value secrets.
- A key shipped to a browser or mobile app is public. Anything that needs a real secret belongs on the server.
- Plan crypto agility: store an algorithm id or version with each ciphertext or signature.
- Test fixtures should use obviously fake values, never copies of real credentials.

## Review Checklist
- [ ] Grep for `md5`, `sha1`, `DES`, `RC4`, `ECB`, `Cipher.getInstance("AES")`, `createCipher(`; each hit is justified or replaced.
- [ ] Grep for `Math.random`, `random.random`, `rand()`, `java.util.Random`, `new Random(` near token, key, salt, nonce or code; each must use a secure generator.
- [ ] Grep for fixed `iv`, `nonce`, `salt` values and `iv =` set to a constant or zeros; none allowed.
- [ ] Grep for `password =`, `secret`, `api_key`, `apikey`, `token =`, `BEGIN PRIVATE KEY`, `AKIA` in source, config, Dockerfiles and test data; none are real.
- [ ] Read `.env`, `docker-compose`, CI files and image build steps; secrets are injected at run time, and `.env` is ignored by version control.
- [ ] Grep for `log`, `print`, `console.` calls that include a key, token, password or full request headers.
- [ ] Read key-loading code; keys come from a store, are separated by purpose and have a rotation path.
- [ ] Grep for `verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify`, `http://` to services holding sensitive data; none without a documented reason.
- [ ] Check for a secret-scanning step in CI or pre-commit configuration.
- [ ] Check that tests exist for the cases under Test Ideas.

## Common Failure Modes
- A homemade scheme, or a fast hash used for something that needs a keyed construction.
- ECB mode, a fixed IV, or a repeated nonce under one key.
- Predictable "random" values for reset codes, invitations or API keys, seeded from the clock.
- One key for every environment, copied into code, and never rotated.
- A credential committed once, then removed in a later commit but still in history.
- Secrets baked into a container image, mobile app or front-end bundle.
- Tokens and full connection strings printed by debug logging or error pages.
- Certificate checks turned off to get past a test failure and left on.

## Test Ideas
- Run the secret scanner over the working tree and over full history; it reports nothing real.
- Generate many tokens; none repeat, and their format shows no timestamp or counter pattern.
- Encrypt the same plaintext twice; the ciphertexts differ and each decrypts correctly.
- Flip one byte of a ciphertext or tag; decryption fails instead of returning data.
- Start the app with the secret missing; it fails clearly and does not fall back to a default.
- Trigger an error and a debug path with a secret in scope; the output has no secret.
- Rotate a key in a test environment; old data still reads through the old key id and new data uses the new one.
- Connect to the service with an invalid certificate; the client refuses.

## Related Entries
- authn.authentication: password hashing and credential recovery use these primitives.
- authn.session: token signing, session id randomness and JWT keys.
- ops.logging_errors: keep secrets out of logs and error pages.
- supply.dependencies: crypto libraries need updates and a trusted source.
- data.deserialization: signed or encrypted blobs must still be treated as untrusted until verified.
- api.web_api: API keys and transport protection at the API layer.

## Sources
- OWASP ASVS 5.0.0, chapter V11 Cryptography (sections 11.1 Cryptographic Inventory and Documentation, 11.3 Encryption Algorithms, 11.5 Random Values), chapter V13 Configuration (sections 13.3 Secret Management, 13.4 Unintended Information Leakage): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html
- OWASP Top 10:2025, A04:2025 Cryptographic Failures: https://top10.owasp.org/2025
- MITRE CWE: CWE-215, CWE-259, CWE-311, CWE-312, CWE-319, CWE-321, CWE-326, CWE-327, CWE-330, CWE-532, CWE-798 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
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
