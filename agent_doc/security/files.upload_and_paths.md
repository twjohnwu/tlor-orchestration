---
id: files.upload_and_paths
name: File Upload, Path Handling and Archive Extraction
category: [files]
confidence: high
verified: 2026-11-13
sources:
  - name: OWASP ASVS
    version: 5.0.0
    url: https://asvs.owasp.org/
  - name: OWASP Cheat Sheet Series
    version: retrieved 2026-11-13
    url: https://cheatsheetseries.owasp.org/
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

# File Upload, Path Handling and Archive Extraction

## Task Signals
- accept a file from a user: image, document, avatar, import file, attachment
- build a file path from a request parameter, a file name or an identifier
- unzip, untar or otherwise extract an archive that a user supplied
- serve, download or preview a stored file; set its content type or headers
- choose where uploaded content is stored on disk or in object storage

## Applies When
- A client controls the bytes, the declared type, the size or the name of a file the server will keep.
- Any part of a filesystem path or object key is derived from request data.
- The server unpacks an archive or reads a file whose location came from outside.

## Does Not Apply When
- The value is text for a SQL, shell or template interpreter: use `input.injection`.
- The server will fetch the file from a user-supplied URL: use `network.ssrf_outbound`.
- The file holds a serialized object graph or a document format with entities: use `data.deserialization`.
- The question is who may read or replace a stored file: use `authz.access_control`.

## Requirements
1. Check every upload on the server for size, count and allowed type before storing it, and reject anything outside a fixed allowlist. [ASVS v5.0.0 V5.2; CWE-434]
2. Decide the file type from the content and an allowlist of extensions, and never trust the client-sent content type or the extension alone. [ASVS v5.0.0 V5.2; CWE-434]
3. Generate the stored file name on the server, for example a random identifier, and keep the original name only as metadata. [ASVS v5.0.0 V5.3; CWE-73]
4. Resolve any path built from outside data to its canonical form and confirm it still sits inside the intended base directory before opening it. [ASVS v5.0.0 V5.3; CWE-22; CWE-23]
5. Prefer an indirect reference, such as a database id mapped to a stored path, over passing paths or names from the client. [ASVS v5.0.0 V5.3; CWE-73]
6. Store uploads outside the web root and outside any location where the server executes code, with no execute permission on the files. [ASVS v5.0.0 V5.3; CWE-434]
7. During archive extraction, check every entry's resolved destination against the target directory and skip links that point outside it. [ASVS v5.0.0 V5.2; CWE-22]
8. Cap the total unpacked size, the entry count and the nesting depth when extracting, and stop the job when a cap is hit. [ASVS v5.0.0 V5.2; CWE-770]
9. Serve user files with a fixed content type, a download disposition and a no-sniff header, preferably from a separate origin. [ASVS v5.0.0 V5.4; CWE-434]
10. Scan or re-encode risky formats such as images and office files where the product allows, and treat the scan as one layer only. [ASVS v5.0.0 V5.2; CWE-434]
11. Review each upload and file-read path as part of secure coding and code review. [NIST SSDF 1.1 PW.5; NIST SSDF 1.1 PW.7; ISO/IEC 27002:2022 8.28]

## Implementation Notes
- Order of checks: size first (cheap), then name and extension, then content sniffing, then any scan. Reject early and store nothing on failure.
- Canonical-path check shape, shown because the order matters:

```
base = realpath(upload_dir)
target = realpath(join(base, name))
if not target.startswith(base + sep): reject
```

- Compare after resolving links; a prefix test on the raw string is bypassed by `..` segments, encoded separators and symbolic links.
- Decode a request parameter once before the path check. Do not decode again after it.
- Content sniffing helps but is not proof: a file can be valid in two formats at once. Pair it with safe serving headers.
- Archive libraries differ in whether they sanitize entry names. Assume they do not and check each destination yourself.
- Object storage keys have no real directories, yet a key built from user text can still overwrite another user's object. Use generated keys.
- Image processing libraries parse hostile input; keep them patched, see `supply.dependencies`.
- Do not log the full client-sent name unescaped; see `ops.logging_errors`.

## Review Checklist
- [ ] Grep for upload handlers (`multipart`, `FormFile`, `request.files`, `MultipartFile`, `upload`) and Read each; size, type and count limits run before the file is written.
- [ ] Grep for `Content-Type`, `mimetype`, `content_type` used as the only type decision; the extension and content must also be checked against an allowlist.
- [ ] Grep for `open(`, `readFile`, `sendFile`, `File(`, `Path(`, `join(` whose argument contains request data; each is preceded by a canonical-path and base-directory check.
- [ ] Grep for `..`, `normalize`, `realpath`, `getCanonicalPath` near those calls; a string `replace("..", "")` is a failure, not a defense.
- [ ] Read where uploads are stored; the directory is outside the web root, not executable, and the name on disk is generated.
- [ ] Grep for `extractall`, `ZipFile`, `tarfile`, `unzip`, `ZipEntry`, `untar`; each extraction checks entry paths and caps total size and entry count.
- [ ] Read the download or preview endpoint; it sets a fixed content type, `Content-Disposition` and `X-Content-Type-Options: nosniff`.
- [ ] Read the access check on the download endpoint; a guessed id or name does not return another user's file.
- [ ] Check that a test exists for each class listed under Test Ideas.

## Common Failure Modes
- Trusting the `Content-Type` header or the file extension, so a script uploaded as an image is stored and later run or rendered.
- Keeping the client's file name on disk, which allows overwriting, path segments and odd characters.
- Checking for `..` as text, then decoding the value, so an encoded form passes.
- Prefix checks on an un-resolved path, defeated by symbolic links or sibling directories that share a name prefix.
- Extracting archives without checking entry names, so an entry escapes the target directory or overwrites a program file.
- No cap on unpacked size, so a small archive fills the disk or memory.
- Serving user HTML or SVG from the main origin, which lets uploaded script act as the site.
- Storing uploads inside the web root or a code-loading directory.

## Test Ideas
- Upload a script file renamed with an image extension and an image content type; the server rejects it or stores it inert with a generated name.
- Upload a file over the size limit and a request with too many parts; both are refused before anything is written.
- Request a file with `../`, an encoded `%2e%2e%2f`, a double-encoded form, an absolute path and a backslash variant; each returns an error and no content outside the base directory.
- Create a symbolic link inside the storage directory pointing outside it; reading through it is refused.
- Extract an archive with an entry named `../../x`, an absolute entry and a link entry; nothing lands outside the target directory.
- Extract a highly compressed archive; the cap stops the job with a clear error.
- Download an uploaded HTML or SVG file; the browser saves it or shows plain text and runs no script.

## Related Entries
- input.injection: file names and paths reaching a shell, a query or a template.
- network.ssrf_outbound: fetching a file from a user-supplied URL.
- data.deserialization: formats that carry objects or external entities.
- authz.access_control: who may fetch or replace a stored file.
- supply.dependencies: patching image, archive and document parsers.
- ops.logging_errors: logging client-controlled names safely.

## Sources
- OWASP ASVS 5.0.0, chapter V5 File Handling (sections 5.2 File Upload and Content, 5.3 File Storage, 5.4 File Download): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- OWASP Cheat Sheet Series has no dedicated path traversal sheet in its index of 137 sheets as retrieved 2026-11-13; path handling rests on ASVS V5 and the CWE entries below.
- MITRE CWE: CWE-22, CWE-23, CWE-73, CWE-434, CWE-770 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
- NIST SP 800-218 v1.1, practices PW.5 Create Source Code by Adhering to Secure Coding Practices and PW.7 Review and/or Analyze Human-Readable Code to Identify Vulnerabilities and Verify Compliance with Security Requirements: https://csrc.nist.gov/pubs/sp/800/218/final
- ISO/IEC 27002:2022, control 8.28 Secure coding (number and title only): https://www.iso.org/standard/75652.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP ASVS 5.0.0: CC BY-SA 4.0.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
- NIST SP 800-218: not subject to copyright in the United States; attribution given.
- ISO/IEC 27002:2022: copyrighted by ISO; only the control number and title are cited, never its text or guidance.
