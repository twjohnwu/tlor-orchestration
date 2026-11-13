---
id: supply.dependencies
name: Dependencies, Build Pipeline and Supply Chain Integrity
category: [supply]
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

# Dependencies, Build Pipeline and Supply Chain Integrity

## Task Signals
- add, upgrade, remove or pin a package, module, plugin, container image or GitHub Action
- edit a lockfile, a manifest, a registry or mirror setting, or an install script
- download a binary, archive or script and run or unpack it
- change a CI job, a build script, a release step or the way artefacts are published
- produce a software bill of materials, or react to a vulnerability scanner report

## Applies When
- The code or the build pulls in a component written by someone outside the project.
- A task changes what the pipeline fetches, runs, signs or publishes.
- A reviewer must judge whether a new or updated dependency is acceptable.

## Does Not Apply When
- The task is about secrets stored in the pipeline or in code: use `crypto.secrets`.
- The task is about parsing an untrusted object graph a library provides: use `data.deserialization`.
- The task is about calling a third-party web API at run time: use `api.web_api`.
- The task is about a language model, its plug-ins or its data sources: use `llm.applications`.

## Requirements
1. Add a dependency only after checking that it is needed, maintained, from the expected publisher and under an acceptable licence; prefer reusing what the project already has. [ASVS v5.0.0 V15.2; CWE-1104; CWE-1357; NIST SSDF 1.1 PW.4]
2. Pin every dependency to an exact version and commit the lockfile, so two builds of one commit install the same tree. [OWASP Top 10 2025 A03]
3. Install from one approved registry, and make each internal package name resolve to the internal source, never to a public package of the same name. [OWASP Top 10 2025 A03; CWE-829]
4. Verify the digest or signature of every downloaded binary, archive, image and build tool before it runs, and fail the step when the check fails. [CWE-494; NIST SSDF 1.1 PS.2]
5. Reference third-party CI actions, base images and scripts by an immutable id (commit hash or image digest), not by a movable tag or `latest`. [OWASP Top 10 2025 A03; CWE-829]
6. Run a known-vulnerability scan on the lockfile for every change and on a schedule, and set an owner and a time limit for each finding. [ASVS v5.0.0 V15.2; CWE-1395; NIST SSDF 1.1 RV.1; NIST SSDF 1.1 RV.2]
7. Never run package install scripts or build steps with production credentials in reach; give each pipeline job the smallest token and network access it needs. [OWASP Top 10 2025 A03; NIST SSDF 1.1 PO.5]
8. Protect the source repository and the build definition with required review, branch protection and logged changes, so one account cannot alter what ships. [NIST SSDF 1.1 PS.1; ISO/IEC 27002:2022 8.32]
9. Build releases in a clean, reproducible environment, then sign them and store each one with its checksums. [NIST SSDF 1.1 PS.2; NIST SSDF 1.1 PS.3; OWASP Top 10 2025 A08]
10. Generate a software bill of materials for each release and keep it with the artefact. [OWASP Top 10 2025 A03; NIST SSDF 1.1 PS.3]
11. Hold outside suppliers of code to the same checks as internal code, written into the contract or intake step. [ISO/IEC 27002:2022 8.30; NIST SSDF 1.1 PO.3]

## Implementation Notes
- Start from an inventory: list manifests and lockfiles, then registries, CI files and every place that downloads and runs something.
- A range such as `^1.2.0` in a manifest is acceptable only while the lockfile pins the exact version and CI installs from the lockfile with the frozen or locked flag.
- Upgrade in small, reviewed commits; read the changelog and the diff of the lockfile, not only the version number.
- Scanner results need triage: a finding is judged by whether the vulnerable function is reachable, but the decision and its date go in the ticket.
- Pin pipeline actions by hash and let an update bot propose new hashes, so pinning does not freeze fixes.
- A typo-squatted or newly transferred package looks normal in a diff; check age, publisher and download history on the registry page.
- Prefer removing a dependency over patching around it when the project uses one small function from a large package.
- Example of a digest check, shown because the order matters (verify, then run):

```
curl -fsSLO "$URL" && echo "$EXPECTED_SHA256  tool.tgz" | sha256sum -c - && tar -xzf tool.tgz
```

## Review Checklist
- [ ] Read the diff of every manifest and lockfile; each new package has a stated reason and a plausible publisher.
- [ ] Grep manifests for `latest`, `*`, `>=`, `git+` and URL sources without a hash; each hit is justified or pinned.
- [ ] Read the install command in CI and Dockerfiles; it uses the lockfile in frozen mode (`npm ci`, `--frozen-lockfile`, `--require-hashes`, `go mod verify`).
- [ ] Grep CI files for `uses:` and `FROM`; each third-party reference is a hash or digest.
- [ ] Grep scripts for `curl`, `wget` and `| sh` or `| bash`; each download is checked by digest or signature before use.
- [ ] Read registry configuration (`.npmrc`, `pip.conf`, `settings.xml`, `GOPROXY`); internal names resolve to the internal source.
- [ ] Read the pipeline for secrets and tokens; each job gets only what it uses, and pull-request builds from forks get none.
- [ ] Check that a vulnerability scan job exists, fails or alerts on new findings, and has an owner.
- [ ] Check that the release job signs artefacts and publishes an SBOM, and that the build definition needs review to change.

## Common Failure Modes
- A lockfile that is ignored, regenerated on each build, or listed in `.gitignore`.
- Pinning direct dependencies while transitive ones float.
- A private package name also free on the public registry, so the public one wins at install time.
- Trusting a mutable tag (`v3`, `latest`) for a CI action that holds deploy credentials.
- Fetching an install script from a URL and piping it to a shell without a check.
- Scanner noise ignored until nobody reads the report; or every finding closed as "not reachable" without a record.
- Pipeline tokens with write access to the repository and the registry, available to every job and to builds of untrusted pull requests.
- Signing done on a developer laptop, so the signature proves only who owns that laptop.

## Test Ideas
- Delete `node_modules` or the equivalent and install in CI mode; the tree must match the lockfile exactly, and an edit to the manifest alone must fail the install.
- Change one byte of a pinned download; the pipeline step must stop before running it.
- Add a package name that exists on both the public and the internal registry; the internal one must win.
- Open a pull request from a fork that prints the environment; no secret appears.
- Feed the scanner a lockfile with a dependency that has a known advisory; the job reports it and the build follows the stated policy.
- Rebuild a tagged release twice; the artefact digests match, or the difference is explained.

## Related Entries
- crypto.secrets: tokens, keys and signing material used by the pipeline.
- data.deserialization: libraries that load untrusted object graphs are a common source of vulnerable dependencies.
- ops.logging_errors: build and scan results must be logged and kept for audit.
- api.web_api: consumption of third-party APIs follows its own rules.
- llm.applications: models, plug-ins and datasets are supply chain items for model features.

## Sources
- OWASP ASVS 5.0.0, chapter V15 Secure Coding and Architecture (section 15.2 Security Architecture and Dependencies): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Vulnerable_Dependency_Management_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Dependency_Graph_SBOM_Cheat_Sheet.html
- OWASP Top 10:2025, A03:2025 Software Supply Chain Failures: https://top10.owasp.org/2025/A03_2025-Software_Supply_Chain_Failures
- OWASP Top 10:2025, A08:2025 Software or Data Integrity Failures: https://top10.owasp.org/2025
- MITRE CWE: CWE-494, CWE-829, CWE-1104, CWE-1357, CWE-1395 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number)
- NIST SP 800-218 v1.1, practices PO.3, PO.5, PS.1, PS.2, PS.3, PW.4, RV.1, RV.2: https://csrc.nist.gov/pubs/sp/800/218/final
- ISO/IEC 27002:2022, controls 8.30 Outsourced development and 8.32 Change management (numbers and titles only): https://www.iso.org/standard/75652.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP ASVS 5.0.0: CC BY-SA 4.0.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- OWASP Top 10 2025: the published site pages state CC BY 3.0; the repository LICENSE file states CC BY-SA 4.0. Both statements are recorded here because the conflict was not resolved.
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
- NIST SP 800-218: not subject to copyright in the United States; attribution given.
- ISO/IEC 27002:2022: copyrighted by ISO; only the control number and title are cited, never its text or guidance.
