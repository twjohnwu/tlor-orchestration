# Security playbook: standards map

This page maps standard numbers to playbook entry ids. It gives numbers and titles only, never control text.

- ISO/IEC 27002:2022 titles rest on agreeing secondary sources, not on the ISO text, which was not read.
- ISO/IEC 27034 is listed by part number and year only: Part 1 (2011), Part 2 (2015), Part 3 (2018), Part 5 (2017), Part 5-1 (2018), Part 6 (2016), Part 7 (2018). No entry maps to it.
- "process-level; no entry" means the item concerns how an organisation works, not a code or design task an entry can guide.
- "no entry yet" means the item is a code or design concern that no current entry cites.

## ISO/IEC 27002:2022, controls 8.25 to 8.34

| Control | Title | Entry ids |
|---|---|---|
| 8.25 | Secure development life cycle | process-level; no entry |
| 8.26 | Application security requirements | authn.authentication, authz.access_control, network.ssrf_outbound |
| 8.27 | Secure system architecture and engineering principles | process-level; no entry |
| 8.28 | Secure coding | input.injection, authn.authentication, authn.session, authz.access_control, crypto.secrets, data.deserialization, files.upload_and_paths, ops.logging_errors |
| 8.29 | Security testing in development and acceptance | process-level; no entry |
| 8.30 | Outsourced development | supply.dependencies |
| 8.31 | Separation of development, test and production environments | process-level; no entry |
| 8.32 | Change management | supply.dependencies |
| 8.33 | Test information | process-level; no entry |
| 8.34 | Protection of information systems during audit testing | process-level; no entry |

## NIST SP 800-218 SSDF v1.1, all 19 practices

An initial public draft of SP 800-218 Rev. 1 (SSDF 1.2, December 2025) exists and is not final; this page maps v1.1 only.

| Practice | Title | Entry ids |
|---|---|---|
| PO.1 | Define Security Requirements for Software Development | process-level; no entry |
| PO.2 | Implement Roles and Responsibilities | process-level; no entry |
| PO.3 | Implement Supporting Toolchains | supply.dependencies |
| PO.4 | Define and Use Criteria for Software Security Checks | process-level; no entry |
| PO.5 | Implement and Maintain Secure Environments for Software Development | supply.dependencies |
| PS.1 | Protect All Forms of Code from Unauthorized Access and Tampering | supply.dependencies |
| PS.2 | Provide a Mechanism for Verifying Software Release Integrity | supply.dependencies |
| PS.3 | Archive and Protect Each Software Release | supply.dependencies |
| PW.1 | Design Software to Meet Security Requirements and Mitigate Security Risks | process-level; no entry |
| PW.2 | Review the Software Design to Verify Compliance with Security Requirements and Risk Information | process-level; no entry |
| PW.4 | Reuse Existing, Well-Secured Software When Feasible Instead of Duplicating Functionality | supply.dependencies |
| PW.5 | Create Source Code by Adhering to Secure Coding Practices | input.injection, authn.authentication, authn.session, authz.access_control, crypto.secrets, data.deserialization, files.upload_and_paths, network.ssrf_outbound, ops.logging_errors |
| PW.6 | Configure the Compilation, Interpreter, and Build Processes to Improve Executable Security | process-level; no entry |
| PW.7 | Review and/or Analyze Human-Readable Code to Identify Vulnerabilities and Verify Compliance with Security Requirements | data.deserialization, files.upload_and_paths, network.ssrf_outbound, ops.logging_errors |
| PW.8 | Test Executable Code to Identify Vulnerabilities and Verify Compliance with Security Requirements | process-level; no entry |
| PW.9 | Configure Software to Have Secure Settings by Default | ops.logging_errors |
| RV.1 | Identify and Confirm Vulnerabilities on an Ongoing Basis | supply.dependencies |
| RV.2 | Assess, Prioritize, and Remediate Vulnerabilities | supply.dependencies |
| RV.3 | Analyze Vulnerabilities to Identify Their Root Causes | process-level; no entry |

v1.1 has no PW.3.

## OWASP Top 10:2025

| Id | Title | Entry ids |
|---|---|---|
| A01:2025 | Broken Access Control | authz.access_control, api.web_api, network.ssrf_outbound |
| A02:2025 | Security Misconfiguration | no entry yet |
| A03:2025 | Software Supply Chain Failures | supply.dependencies |
| A04:2025 | Cryptographic Failures | crypto.secrets |
| A05:2025 | Injection | input.injection |
| A06:2025 | Insecure Design | no entry yet |
| A07:2025 | Authentication Failures | authn.authentication, authn.session |
| A08:2025 | Software or Data Integrity Failures | data.deserialization, supply.dependencies |
| A09:2025 | Security Logging and Alerting Failures | ops.logging_errors |
| A10:2025 | Mishandling of Exceptional Conditions | ops.logging_errors |

## License Provenance
- This page is an original mapping, published under this repository's MIT licence. It copies no text from the cited works; it uses numbers and titles only.
- NIST SP 800-218 v1.1 (https://csrc.nist.gov/pubs/sp/800/218/final): not subject to copyright in the United States; attribution given.
- ISO/IEC 27002:2022 (https://www.iso.org/standard/75652.html) and ISO/IEC 27034: copyrighted by ISO; only control numbers, titles, part numbers and years are cited, never text or guidance.
- OWASP Top 10 2025 (https://top10.owasp.org/2025): the published site pages state CC BY 3.0; the repository LICENSE file states CC BY-SA 4.0. Both statements are recorded here because the conflict was not resolved.
