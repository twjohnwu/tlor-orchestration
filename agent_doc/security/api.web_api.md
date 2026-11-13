---
id: api.web_api
name: Web API Security (REST, GraphQL, Service Endpoints)
category: [api]
confidence: high
verified: 2026-11-13
sources:
  - name: OWASP API Security Top 10
    version: 2023
    url: https://api-security.owasp.org/editions/2023/en/0x11-t10
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
---

# Web API Security (REST, GraphQL, Service Endpoints)

## Task Signals
- add or change an endpoint, a route, a resolver or a field in a response
- bind a request body to a model, entity or DTO; add an update or patch operation
- accept an id, a filter, a page size or a sort order from the caller
- add pagination, batching, file size limits, rate limiting or quotas
- call a partner or third-party API and use what it returns
- publish, version, deprecate or document an API

## Applies When
- A service exposes operations to callers over HTTP, GraphQL or a similar protocol, and the code decides which objects, fields and volumes a caller may touch.
- A feature consumes data from another API and acts on it.
- A reviewer must judge the shape of an API against the API-specific risk list (API1 to API10, 2023 edition).

## Does Not Apply When
- The question is the general rule for who may do what: use `authz.access_control`.
- The question is how callers prove identity or how tokens and passwords work: use `authn.authentication`, or `authn.session` for session handling.
- The input is text for an interpreter such as SQL or a shell: use `input.injection`.
- The API takes a URL and the server fetches it: use `network.ssrf_outbound`.
- The API fronts a language model: use `llm.applications`.

## Requirements
1. Check, in the handler, that the caller may act on the specific object named by each id in the path, query or body, for every operation and every method. [OWASP API Security Top 10 2023 API1; CWE-639; OWASP Top 10 2025 A01]
2. Decide per field which caller roles may read it and which may write it, and return only the permitted fields, using an explicit response model rather than the stored object. [OWASP API Security Top 10 2023 API3; CWE-200]
3. Bind request data to an explicit input model that lists the writable fields; never copy a whole request body onto an entity. [OWASP API Security Top 10 2023 API3; CWE-915]
4. Put a limit on every cost the caller can drive: body size, page size, nesting depth, batch length, query complexity, concurrent requests and upload size. [OWASP API Security Top 10 2023 API4; CWE-770; CWE-400; ASVS v5.0.0 V15.2]
5. Throttle per caller and per sensitive flow (sign-up, purchase, password reset, bulk export), with a clear client error when the limit is hit. [OWASP API Security Top 10 2023 API4; OWASP API Security Top 10 2023 API6; ASVS v5.0.0 V2.4]
6. Restrict introspection, debug routes and verbose schema output in production for GraphQL and similar services, and cap query depth and cost. [ASVS v5.0.0 V4.3; OWASP API Security Top 10 2023 API8]
7. Validate every request against a schema: content type, field types, lengths, enumerations and unknown fields, rejecting what does not match. [ASVS v5.0.0 V2.2; CWE-20]
8. Keep an inventory of every API host, version and endpoint, retire old versions on a schedule, and keep non-production copies off the public network. [OWASP API Security Top 10 2023 API9]
9. Treat data from a third-party API as untrusted input: validate its shape and size, set timeouts, do not follow its redirects blindly, and do not let it choose what the server does next. [OWASP API Security Top 10 2023 API10; CWE-20]
10. Return the same generic error for a missing object and a forbidden one where the difference would reveal that an id exists, and never include internals in the body. [ASVS v5.0.0 V16.5; CWE-209]

## Implementation Notes
- The general authorization rules are in `authz.access_control` and the identity rules in `authn.authentication`; the requirements above add only what is specific to APIs.
- Object-level checks belong beside the data access, not only in a gateway: load the record scoped by the caller, or compare its owner to the caller, before using it.
- Random ids make guessing harder but do not replace the ownership check.
- Keep separate input and output models per operation (create, update, read). A shared model is how a field such as `role` or `is_admin` becomes writable.
- Use the framework's allowlist feature for binding (field lists, schema with unknown fields rejected) instead of a blocklist of dangerous names.
- Limits work best in layers: the gateway for coarse volume, the handler for business limits such as items per order.
- For GraphQL, one request can hold many operations; count aliases, batches and depth, not only HTTP requests.
- When consuming another API, wrap the client in one module that applies the timeout, size cap and validation, so each caller does not repeat them.
- Example of a binding allowlist, shown because the shape matters:

```
fields = pick(request.body, ["name", "email"])   # role, owner_id and price are never copied
user.update(fields)
```

## Review Checklist
- [ ] Read each handler that takes an id; it compares the object's owner or scope to the caller before reading or changing it.
- [ ] Grep for whole-body binding (`**request`, `Object.assign(`, `update(request.body`, `fromJson`, `@RequestBody` onto an entity, `permit!`); each hit uses an explicit field list.
- [ ] Read the response code; it builds the output from a response model and does not serialize the stored entity directly.
- [ ] Grep for `limit`, `page_size`, `maxDepth`, `max_body`, `rate`, `throttle` across the routes; each list or batch endpoint has an upper bound.
- [ ] Read the rate-limit configuration; it covers sign-up, reset, purchase and export flows per caller, not only a global cap.
- [ ] Grep GraphQL configuration for `introspection`, `depthLimit` and `complexity`; production disables or limits them.
- [ ] Read the API description file (OpenAPI or schema); it lists every route that exists, and no route exists that it omits.
- [ ] Grep for outbound client calls to partner APIs; each has a timeout, a size cap and validation of the response before use.
- [ ] Read the error handlers; messages for missing and forbidden objects do not leak existence or internals.

## Common Failure Modes
- Authorization checked for `GET /orders/{id}` but not for `PUT`, `DELETE` or a bulk endpoint on the same resource.
- A user-update endpoint that accepts the whole stored record, including role or balance fields.
- Responses that return the full object and rely on the front end to hide fields.
- Only the first page size is capped; a filter, sort or batch parameter lets a caller request everything.
- Rate limiting by IP only, so many callers share a limit and one caller with many addresses has none.
- An old API version left running, without the checks added to the new one.
- A staging or debug host reachable from the internet with real data.
- Trusting a partner API because it is a "known" partner: following its redirect, accepting its huge reply, or acting on its field without checks.

## Test Ideas
- Log in as user A, call each operation with user B's object id; every call is refused or returns nothing.
- Send an update that adds `role`, `owner_id`, `price` or `is_admin`; the stored value is unchanged.
- Compare each response with the output model; no field outside it appears, including nested objects.
- Request a page size, depth, batch length or body size far above the limit; the service answers with a client error and stays responsive.
- Repeat a sensitive flow quickly from one account and from several; the limit triggers in both cases.
- Compare the live route list with the API description; nothing is missing or extra, and retired versions return an error.
- Point a test double for the partner API at slow, oversized and redirecting replies; the client times out, caps and rejects them.

## Related Entries
- authz.access_control: the general rules for object, function and role checks.
- authn.authentication: how callers prove identity, including API keys and tokens.
- input.injection: request values that reach an interpreter.
- network.ssrf_outbound: server-side requests built from API input, and redirects from third-party APIs.
- ops.logging_errors: logging of rejected requests and of limit hits.
- supply.dependencies: third-party API clients and SDKs as dependencies.
- llm.applications: APIs that pass user data to a language model.

## Sources
- OWASP API Security Top 10 2023, list API1 to API10: https://api-security.owasp.org/editions/2023/en/0x11-t10
- OWASP API Security Top 10 2023, API10:2023 Unsafe Consumption of APIs: https://api-security.owasp.org/editions/2023/en/0xaa-unsafe-consumption-of-apis/
- OWASP ASVS 5.0.0, chapter V4 API and Web Service (section 4.3 GraphQL), chapter V2 Validation and Business Logic (sections 2.2 Input Validation, 2.4 Anti-automation), chapter V15 Secure Coding and Architecture (section 15.2 Security Architecture and Dependencies), and chapter V16 Security Logging and Error Handling (section 16.5 Error Handling): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/GraphQL_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- OWASP Top 10:2025, A01:2025 Broken Access Control: https://top10.owasp.org/2025/A01_2025-Broken_Access_Control
- MITRE CWE: CWE-20, CWE-200, CWE-209, CWE-400, CWE-639, CWE-770, CWE-915 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP API Security Top 10 2023: CC BY-SA 4.0.
- OWASP ASVS 5.0.0: CC BY-SA 4.0.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- OWASP Top 10 2025: the published site pages state CC BY 3.0; the repository LICENSE file states CC BY-SA 4.0. Both statements are recorded here because the conflict was not resolved.
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
