---
id: network.ssrf_outbound
name: Server-Side Request Forgery and Outbound Requests
category: [network]
confidence: high
verified: 2026-11-13
sources:
  - name: OWASP Cheat Sheet Series
    version: retrieved 2026-11-13
    url: https://cheatsheetseries.owasp.org/
  - name: OWASP API Security Top 10
    version: 2023
    url: https://api-security.owasp.org/editions/2023/en/0x11-t10
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

# Server-Side Request Forgery and Outbound Requests

## Task Signals
- fetch a URL that a user typed: link preview, image import, avatar from URL, RSS or feed reader
- register a webhook or callback URL and send events to it
- proxy, relay or screenshot a page on behalf of a user
- follow redirects in an HTTP client; resolve a host name from request data
- run on a cloud host where an instance metadata service answers on a local address

## Applies When
- The server makes a network request whose destination, or any part of it, comes from a client or from stored user data.
- A feature stores a URL now and requests it later, for example a webhook target.
- An HTTP client follows redirects or resolves names while handling untrusted input.

## Does Not Apply When
- The server fetches a fixed, configured address only: no entry needed beyond normal transport hardening.
- The input is a path to a local file: use `files.upload_and_paths`.
- The input is text for a shell, query or template: use `input.injection`.
- The concern is the credentials the outbound call carries: use `crypto.secrets`.
- The URL is returned to the browser and the browser fetches it: use `api.web_api` or `input.injection` for the rendering side.

## Requirements
1. Allow outbound requests only to destinations named in a server-side allowlist of hosts, ports and schemes, and refuse everything else. [ASVS v5.0.0 V1.3; OWASP Top 10 2025 A01; OWASP API Security Top 10 2023 API7; CWE-918]
2. Accept only the `https` scheme where possible, and block other schemes such as `file`, `gopher` and `ftp` before the client library sees them. [ASVS v5.0.0 V1.3; ASVS v5.0.0 V5.3; OWASP API Security Top 10 2023 API7; CWE-918]
3. Resolve the host name yourself, check the resulting address against a deny list of loopback, private, link-local and metadata ranges, and connect to that same address. [CWE-918; OWASP API Security Top 10 2023 API7]
4. Apply the address check again for every redirect hop, or turn redirect following off and handle redirects explicitly. [CWE-918; CWE-601]
5. Treat IPv6, IPv4-mapped IPv6, decimal, octal and hexadecimal address forms as the same targets as their dotted forms, by parsing them with a real address library. [CWE-918]
6. Block the cloud instance metadata address and require the hardened token-based metadata mode where the platform offers one. [CWE-918; OWASP API Security Top 10 2023 API7]
7. Run outbound fetchers from a network segment or proxy that has no route to internal services, as a second layer behind the application check. [OWASP API Security Top 10 2023 API7; ISO/IEC 27002:2022 8.26]
8. Set short connect and read timeouts, a response size cap and a content-type check on fetched data. [CWE-918; CWE-770]
9. Return a generic error for a refused or failed fetch, and never echo the fetched body or the internal error to the caller. [CWE-918; CWE-209]
10. For webhooks, validate the target when it is registered and again when each delivery is sent, and sign the payload instead of sending internal credentials. [OWASP API Security Top 10 2023 API7; CWE-918]
11. Review each outbound HTTP call that takes outside data as part of secure coding. [NIST SSDF 1.1 PW.5; NIST SSDF 1.1 PW.7]

## Implementation Notes
- Validate the parsed URL, not the raw string: parse with a standard library, read the host and port from the parser, and ignore look-alike text such as a user-info part (`https://trusted.example@evil.example`).
- Check-then-fetch has a time gap. A name can resolve to a safe address during the check and to an internal one during the request. Pin the connection to the address you checked, or use a resolver hook in the client.
- A deny list alone is the weaker design: new address forms keep appearing. Prefer an allowlist of known hosts, and add the address deny list as backup for features that must reach arbitrary public sites.
- When arbitrary public destinations are a real requirement, such as a link preview, run the fetch in an isolated worker with no credentials and no internal routes.
- Redirect handling shape:

```
for hop in range(MAX_HOPS):
    addr = resolve_and_check(url)       # deny private, loopback, link-local
    resp = get(url, connect_to=addr, follow=False)
    if not resp.is_redirect: break
    url = resolve_relative(url, resp.location)
```

- Blind SSRF gives no response body, yet timing and error differences can still map an internal network. Return the same error for all failures.
- Log the destination host of refused fetches, with control characters escaped; see `ops.logging_errors`.

## Review Checklist
- [ ] Grep for HTTP client calls (`requests.get`, `http.Get`, `fetch(`, `axios`, `HttpClient`, `urlopen`, `curl`) and Read each; list those whose URL or host comes from request or stored user data.
- [ ] Read the validation around each such call; it uses a host allowlist or an address check on the resolved IP, not a string `startswith` or `contains` test.
- [ ] Grep for redirect settings (`follow_redirects`, `allow_redirects`, `FollowRedirects`, `maxRedirects`); each is off or re-validates every hop.
- [ ] Grep for `169.254`, `metadata`, `127.0.0.1`, `localhost`, `::1`, `10.`, `192.168`; the deny logic covers each range and uses an address parser.
- [ ] Read the webhook registration and delivery code; the target is validated at both moments and delivery uses a short timeout.
- [ ] Grep for timeout and size options on the client; connect and read timeouts and a body cap are set.
- [ ] Read the error path of each fetcher; no fetched body, stack trace or internal host name reaches the caller.
- [ ] Check that tests exist for the cases listed under Test Ideas.

## Common Failure Modes
- Checking the host name text and then letting the client resolve it again, so a rebinding name reaches an internal address.
- Blocking `127.0.0.1` and `localhost` only, while `0.0.0.0`, IPv6 loopback, mapped addresses and numeric forms pass.
- Following redirects blindly: a public page answers with a redirect to an internal address.
- Matching a host with `endswith` or `contains`, so `trusted.example.evil.example` passes.
- Validating a webhook URL once at registration, then delivering to it for years after its DNS changed.
- Leaving the instance metadata service reachable with its older, token-free mode.
- Returning the fetched response or a detailed connection error, which turns a blind flaw into a visible one.
- Letting the application's own credentials or auth headers ride along on requests to user-chosen hosts.

## Test Ideas
- Submit loopback, private-range, link-local and metadata addresses in dotted, decimal, hexadecimal, IPv6 and mapped forms; every one is refused.
- Submit a URL with a user-info part and with a look-alike host suffix; the server picks the real host and refuses it.
- Serve a public page that redirects to an internal address; the second hop is refused.
- Point a test name at a safe address first and an internal one second, with a very short lifetime; the request is pinned to the checked address or refused.
- Register a webhook to an allowed host, then change its resolution to a private address; the delivery is refused.
- Request a very large response and a slow-drip response; the size cap and timeout end the call.
- Compare the error for a closed internal port and an unreachable host; the caller sees the same message.

## Related Entries
- input.injection: validating the URL as data before any request is made.
- files.upload_and_paths: fetching an upload from a URL and storing it.
- crypto.secrets: keeping credentials off requests to untrusted hosts.
- api.web_api: API-level handling of URL parameters and webhook features.
- ops.logging_errors: safe logging of refused destinations and generic errors.
- supply.dependencies: HTTP client and URL parser versions.

## Sources
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- OWASP API Security Top 10 2023, API7:2023 Server Side Request Forgery: https://api-security.owasp.org/editions/2023/en/0xa7-server-side-request-forgery/
- OWASP ASVS 5.0.0, chapter V1 Encoding and Sanitization (section 1.3 Sanitization) and chapter V5 File Handling (section 5.3 File Storage): https://asvs.owasp.org/
- OWASP Top 10:2025, A01:2025 Broken Access Control: https://top10.owasp.org/2025/A01_2025-Broken_Access_Control
- MITRE CWE: CWE-918, CWE-601, CWE-209, CWE-770 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); CWE-918 is item 22 in the 2025 Top 25 list: https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html
- NIST SP 800-218 v1.1, practices PW.5 Create Source Code by Adhering to Secure Coding Practices and PW.7 Review and/or Analyze Human-Readable Code to Identify Vulnerabilities and Verify Compliance with Security Requirements: https://csrc.nist.gov/pubs/sp/800/218/final
- ISO/IEC 27002:2022, control 8.26 Application security requirements (number and title only): https://www.iso.org/standard/75652.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- OWASP API Security Top 10 2023: CC BY-SA 4.0.
- OWASP ASVS 5.0.0: CC BY-SA 4.0 (named only to record the gap).
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
- NIST SP 800-218: not subject to copyright in the United States; attribution given.
- ISO/IEC 27002:2022: copyrighted by ISO; only the control number and title are cited, never its text or guidance.
