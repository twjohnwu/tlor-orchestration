---
id: data.deserialization
name: Deserialization of Untrusted Data and Safe Parsing
category: [data]
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

# Deserialization of Untrusted Data and Safe Parsing

## Task Signals
- load an object, session, cache entry, queue message or job payload from bytes
- use a native serializer: Java object streams, Python `pickle`, PHP `unserialize`, .NET binary formatters, Ruby `Marshal`
- parse XML, YAML, JSON or another structured format that comes from a client or a partner
- read a cookie, a token body or a stored blob that the server once wrote and a client can now change
- map a request body onto a typed object or model

## Applies When
- Bytes from outside the trust boundary are turned into live objects, or into data that selects which code runs.
- A parser may expand entities, resolve external references or instantiate types named in the input.
- A format carries type information that the reader follows.

## Does Not Apply When
- The data is a plain string that goes into a query, command or page: use `input.injection`.
- The data is an uploaded file whose type, name or location is the issue: use `files.upload_and_paths`.
- The structured data is a signed token or session value: use `authn.session`.
- The structured data is an API request body and the issue is schema or mass assignment: use `api.web_api`.
- A parser fetches a remote address named in the input: use `network.ssrf_outbound`.

## Requirements
1. Never pass untrusted bytes to a native object serializer that can instantiate arbitrary types; use a data-only format instead. [ASVS v5.0.0 V1.5; CWE-502]
2. When a native serializer cannot be removed, accept only an explicit allowlist of classes and reject every other type before construction. [ASVS v5.0.0 V1.5; CWE-502]
3. Verify an integrity signature or MAC over serialized data before parsing it, and keep the key out of the data's reach. [ASVS v5.0.0 V1.5; OWASP Top 10 2025 A08; CWE-502]
4. Parse structured input with a strict schema that fixes field names, types, lengths and allowed values, and reject unknown fields. [ASVS v5.0.0 V2.2; CWE-20]
5. Disable document type definitions, external entity resolution and external schema loading in every XML parser. [ASVS v5.0.0 V1.5; CWE-611]
6. Use the safe loading mode of a YAML or similar parser that cannot create arbitrary objects. [ASVS v5.0.0 V1.5; CWE-502]
7. Limit input size, nesting depth, element count and entity expansion before and during parsing. [CWE-770]
8. Do not let input choose a class, a function name or a type tag that is then looked up by reflection, except through a fixed map. [CWE-502; CWE-94]
9. Treat data read back from a client-held place such as a cookie or a hidden field as untrusted, even if the server wrote it. [OWASP Top 10 2025 A08; CWE-502]
10. Fail closed on any parse or validation error: reject the whole input and return a generic error. [ASVS v5.0.0 V1.5; CWE-502]
11. Review deserialization calls and parser settings as part of secure coding and code analysis. [NIST SSDF 1.1 PW.5; NIST SSDF 1.1 PW.7; ISO/IEC 27002:2022 8.28]

## Implementation Notes
- First choice is a plain data format (JSON with a schema, a typed message format) that produces only maps, lists and scalars, followed by an explicit conversion into your own types.
- Native binary serializers are a code-execution risk, not just a data-corruption risk: crafted input can run code during reading, before any of your checks.
- A signature check protects data your server wrote. It does not make a third party's payload safe.
- XML parser hardening differs by library; read the library's setting names and turn off DTD processing and external resolution explicitly, then test it.
- Schema validation shape:

```
data = json.loads(body, max_size=LIMIT)
validate(data, SCHEMA)          # unknown fields and wrong types fail
obj = Model(**data)             # only after validation
```

- Polymorphic type handling in JSON and YAML libraries (type tags, default typing) brings the native-serializer risk back; keep it off or fixed to a safe base type.
- Do not catch a parse failure and fall back to a lenient parser.
- Log the failure class, not the payload; see `ops.logging_errors`.

## Review Checklist
- [ ] Grep for native serializer calls (`ObjectInputStream`, `readObject`, `pickle.load`, `pickle.loads`, `unserialize`, `Marshal.load`, `BinaryFormatter`, `yaml.load`); each input is trusted by construction or restricted by an allowlist.
- [ ] Grep for `yaml.load(` without a safe loader, and for `ObjectMapper` with `enableDefaultTyping`, `activateDefaultTyping` or `TypeNameHandling`; each is absent or restricted.
- [ ] Grep for XML parser creation (`DocumentBuilderFactory`, `SAXParser`, `XMLReader`, `etree`, `lxml`, `XmlReader`); each disables DTDs and external entities.
- [ ] Read how session, cache and queue data is read back; it is signed or authenticated before parsing and the key is not client-readable.
- [ ] Read each request parser; it validates against a schema, rejects unknown fields and bounds size and depth.
- [ ] Grep for reflection on input (`Class.forName`, `getattr`, `__import__`, `eval`, `Activator.CreateInstance`) fed by parsed data; each uses a fixed map.
- [ ] Read the catch block around each parse; the failure returns a generic error and does not continue with partial data.
- [ ] Check that tests exist for the cases listed under Test Ideas.

## Common Failure Modes
- Reading a cookie, cache entry or message body with a native serializer because "only our server writes it."
- Using a general loader for YAML configuration that also accepts user-supplied documents.
- Leaving XML parser defaults on, so a document with an external entity reads a local file or reaches an internal host.
- Allowing the JSON library to honor type names in the payload.
- Validating after construction, when a constructor or setter has already run on hostile values.
- No size or depth limit, so a nested or self-expanding document exhausts memory.
- Accepting unknown fields and passing the whole map onward, which lets a client set internal attributes.
- A broad catch that logs and then continues with a half-built object.

## Test Ideas
- Feed each parser an input with an unexpected type tag or class name; it is rejected without any object of that type being built.
- Send an XML document with an external entity that points to a local file and one that points to an internal address; the content is not returned and no request is made.
- Send an XML document with deeply nested or repeated entities; parsing stops at the limit.
- Modify a signed blob by one byte, and replace it with a well-formed blob signed by another key; both are refused before parsing.
- Send a JSON body with an extra field, a wrong type, a huge number and a very deep nesting; each returns a client error.
- Send a YAML document that uses an object-construction tag; the safe loader refuses it.
- Truncate a valid payload; the response is a generic error and no partial state is saved.

## Related Entries
- input.injection: text values that reach interpreters after parsing.
- files.upload_and_paths: uploaded documents and archive formats.
- network.ssrf_outbound: parsers or libraries that fetch addresses named in the data.
- authn.session: signed cookies and session blobs.
- api.web_api: request schemas and mass assignment at the API layer.
- supply.dependencies: patching serializer and parser libraries.
- ops.logging_errors: generic failures and safe logging of rejected payloads.

## Sources
- OWASP ASVS 5.0.0, chapter V1 Encoding and Sanitization (section 1.5 Safe Deserialization) and chapter V2 Validation and Business Logic (section 2.2 Input Validation): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- OWASP Top 10:2025, A08:2025 Software or Data Integrity Failures: https://top10.owasp.org/2025
- MITRE CWE: CWE-502, CWE-611, CWE-20, CWE-94, CWE-770 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); CWE-502 is item 15 in the 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
- NIST SP 800-218 v1.1, practices PW.5 Create Source Code by Adhering to Secure Coding Practices and PW.7 Review and/or Analyze Human-Readable Code to Identify Vulnerabilities and Verify Compliance with Security Requirements: https://csrc.nist.gov/pubs/sp/800/218/final
- ISO/IEC 27002:2022, control 8.28 Secure coding (number and title only): https://www.iso.org/standard/75652.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP ASVS 5.0.0: CC BY-SA 4.0.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- OWASP Top 10 2025: the published site pages state CC BY 3.0; the repository LICENSE file states CC BY-SA 4.0. Both statements are recorded here because the conflict was not resolved.
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
- NIST SP 800-218: not subject to copyright in the United States; attribution given.
- ISO/IEC 27002:2022: copyrighted by ISO; only the control number and title are cited, never its text or guidance.
