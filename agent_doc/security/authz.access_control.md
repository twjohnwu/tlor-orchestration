---
id: authz.access_control
name: Authorization, Object-Level Access and Tenant Isolation
category: [authz]
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

# Authorization, Object-Level Access and Tenant Isolation

## Task Signals
- fetch, update or delete a record by an id taken from the URL, query or body
- add an admin-only route, a role, a permission or a feature flag by plan
- list records for the current user, team, organization or tenant
- hide a button or menu item for users who lack a right
- share a resource with another user, or accept a user id in a request
- bind request fields straight onto a model object

## Applies When
- The caller is known and the code must decide whether this caller may perform this action on this object.
- Several users or tenants keep data in the same store and must not see each other's data.
- A reviewer must judge whether a missing check lets one user reach another user's resource.

## Does Not Apply When
- The task is about proving who the caller is: use `authn.authentication`.
- The task is about the session or token that carries identity: use `authn.session`.
- The task is about schema, rate and field exposure of an API as a whole: use `api.web_api`.
- The task is about file names and paths on disk: use `files.upload_and_paths`.

## Requirements
1. Check authorization on the server for every request, in code that the client cannot skip; a hidden control in the user interface is not a check. [ASVS v5.0.0 V8.2; CWE-862; OWASP Top 10 2025 A01]
2. Deny by default: an operation with no explicit rule for the caller is refused, and a new route starts closed. [ASVS v5.0.0 V8.2; CWE-284; OWASP Top 10 2025 A01]
3. Check function-level rights at each operation, so that an ordinary user cannot reach an administrative action by calling its URL. [ASVS v5.0.0 V8.2; CWE-862; CWE-285]
4. Check object-level rights on each lookup: the record must belong to the caller or be shared with them, not merely exist. [ASVS v5.0.0 V8.2; CWE-639; CWE-863]
5. Take the caller identity and tenant from the verified session or token, never from a request field the caller controls. [ASVS v5.0.0 V8.2; CWE-639]
6. Scope data queries by tenant or owner inside the data layer or a shared helper, so a forgotten filter cannot expose rows. [ASVS v5.0.0 V8.4; CWE-863]
7. Return the same not-found answer for a resource the caller may not see and one that does not exist, where the difference would leak facts. [ASVS v5.0.0 V8.2; CWE-639]
8. Allow only listed fields to be set from a request body, and keep role, owner and tenant fields out of that list. [ASVS v5.0.0 V8.2; CWE-915]
9. Re-check rights at the moment of use rather than at login alone, so role changes and removals take effect at once. [ASVS v5.0.0 V8.3]
10. Define roles or attributes in one place and give least privilege to each; require an explicit grant to raise privilege. [ASVS v5.0.0 V8.2; CWE-269; CWE-284]
11. Do not rely on an unguessable identifier as the access control; random ids are a supplement only. [ASVS v5.0.0 V8.2; CWE-639]
12. Review authorization code and keep a test for each rule, as part of secure-coding review. [NIST SSDF 1.1 PW.5; ISO/IEC 27002:2022 8.26; ISO/IEC 27002:2022 8.28]

## Implementation Notes
- Prefer one central policy point (middleware, a policy class, a database row-level rule) over checks scattered through handlers.
- Write the check next to the data load: `get_for_user(id, user)` is harder to misuse than `get(id)` followed by an optional check.
- For lists, filter in the query, not after fetching; filtering in memory leaks counts and burns resources.
- Multi-tenant stores can enforce the tenant at the database with row-level rules, so an application bug does not cross tenants.
- Background jobs, exports, webhooks and admin tools carry authority too; give each a caller identity and apply the same rules.
- Batch endpoints and GraphQL resolvers need the check per item, not per request.
- Write an access matrix (role by operation by object type) and turn each cell into a test.
- Return 403 or 404 consistently according to the rule above; log denials for detection, see `ops.logging_errors`.

## Review Checklist
- [ ] List every route or handler (grep `@app.route`, `router.`, `@GetMapping`, `[HttpGet]`, `app.get(`); each one has an authorization check or a documented public reason.
- [ ] Grep for lookups by id (`findById`, `get(`, `objects.get`, `WHERE id =`) fed from a request; the same call or its caller checks owner or tenant.
- [ ] Grep for `user_id`, `userId`, `tenant_id`, `org_id` read from `request.`, `params`, `body` or `query`; identity must come from the session instead.
- [ ] Read each list query; the tenant or owner condition is in the query itself.
- [ ] Grep for `isAdmin`, `role ==`, `hasRole`, `@PreAuthorize`, `permission`; confirm admin routes check on the server and the default is deny.
- [ ] Grep for `update(request`, `**request.`, `Object.assign(`, `fill(`, `@RequestBody` onto entities; an allowlist of fields exists and excludes role and owner.
- [ ] Read batch, export and background-job code paths; each applies the same rule as the single-object path.
- [ ] Grep for middleware ordering and `skip`, `exempt`, `permitAll`, `AllowAnonymous`; each exception is justified.
- [ ] Check that tests exist for the cases under Test Ideas.

## Common Failure Modes
- The check runs in the front end only; the API accepts any call.
- Object lookup by id alone, so changing the number in the URL reaches another user's record.
- The user or tenant id arrives in the body or a header and is trusted.
- Admin pages hidden but not guarded; a new route added with no check.
- Updates bind the whole request to the model, so a caller sets `role` or `owner`.
- A list endpoint filters after the fetch, or an export job ignores tenant boundaries.
- Authorization checked once at login; a revoked user keeps access until the token expires.
- Different error answers reveal which ids exist.

## Test Ideas
- Log in as user A, request user B's object by id on read, update and delete; each is refused.
- Call each admin route as an ordinary user and as an anonymous caller; each is refused.
- Send a request that names another tenant in a field or header; the server uses its own tenant.
- Add `role` or `owner` to an update body; the stored value is unchanged.
- List resources as tenant A; no row of tenant B appears, and counts match.
- Remove a user's role, then call with the old token; the action is now refused.
- Request an id that does not exist and one that belongs to someone else; the answers are identical.
- Run a batch or export as a low-privilege user; items the user may not see are absent.

## Related Entries
- authn.authentication: identity must be established before rights can be checked.
- authn.session: the verified session is the only trusted source of caller identity.
- api.web_api: field-level exposure, mass assignment and API inventory.
- files.upload_and_paths: access to files and paths, where a path acts as an object key.
- input.injection: a query injection can defeat row filters.
- ops.logging_errors: record denied attempts without exposing data.

## Sources
- OWASP ASVS 5.0.0, chapter V8 Authorization (sections 8.2 General Authorization Design, 8.3 Operation Level Authorization, 8.4 Other Authorization Considerations): https://asvs.owasp.org/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- OWASP Top 10:2025, A01:2025 Broken Access Control: https://top10.owasp.org/2025
- MITRE CWE: CWE-269, CWE-284, CWE-285, CWE-639, CWE-862, CWE-863, CWE-915 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
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
