---
id: llm.applications
name: LLM Applications and Agents
category: [llm]
confidence: high
verified: 2026-11-13
sources:
  - name: OWASP Top 10 for LLM Applications
    version: 2025
    url: https://genai.owasp.org/llm-top-10/
  - name: OWASP Cheat Sheet Series
    version: retrieved 2026-11-13
    url: https://cheatsheetseries.owasp.org/
  - name: MITRE CWE
    version: 2025 list
    url: https://cwe.mitre.org/data/definitions/1427.html
---

# LLM Applications and Agents

## Task Signals
- build a prompt from user text, retrieved documents, web pages, emails or tool output
- send application or customer data to a model, or store conversations and embeddings
- show, render, store or execute what a model returns (HTML, SQL, shell, code, JSON for a tool call)
- give a model tools, an agent loop, a browser, a code runner or access to files and accounts
- write a system prompt, set token or cost limits, or add a human approval step

## Applies When
- Text from outside the developer's control reaches a model, directly from a user or indirectly through a document, page or tool result.
- Model output drives a decision, a rendered page, a stored record or an action in another system.
- A model can call tools or act for a user, and a reviewer must judge what it is allowed to do.

## Does Not Apply When
- The task is a classic interpreter injection with no model involved: use `input.injection`.
- The task is general authorization of users and operations: use `authz.access_control`.
- The task is a plain web endpoint that happens to sit in front of a model: use `api.web_api` for the endpoint part.
- The task is the choice and pinning of ordinary code libraries: use `supply.dependencies`.
- The task is secrets and keys, including model provider keys: use `crypto.secrets`.

## Requirements
1. Assume any text a model reads can carry instructions, including documents, web pages, emails and tool results; do not rely on wording in the prompt as the control. [OWASP LLM Top 10 2025 LLM01; CWE-1427]
2. Keep trusted instructions apart from untrusted content with clear structure and labels, and treat that separation as one layer that can fail. [OWASP LLM Top 10 2025 LLM01; CWE-1427]
3. Treat every model output as untrusted input: validate it against a schema and encode it for the place it goes (HTML, SQL, shell, URL) before use. [OWASP LLM Top 10 2025 LLM05; CWE-1426]
4. Never run model-produced code, queries or commands directly; run them only in a sandbox with no secrets and a narrow allowlist of operations. [OWASP LLM Top 10 2025 LLM05; CWE-1426; CWE-77]
5. Give each tool and agent the least privilege for its task: a small tool set, scoped credentials, read-only where possible, and the end user's own rights instead of a service account's. [OWASP LLM Top 10 2025 LLM06]
6. Require human approval, shown with the exact action and its arguments, for any high-impact step: sending messages, spending money, deleting or changing data, or changing permissions. [OWASP LLM Top 10 2025 LLM06]
7. Enforce authorization in the application, outside the model, on every tool call and every data retrieval, using the identity of the person who asked. [OWASP LLM Top 10 2025 LLM06; OWASP LLM Top 10 2025 LLM02]
8. Send the model only the data the task needs, redact secrets and personal data first, and filter what leaves in a response. [OWASP LLM Top 10 2025 LLM02]
9. Keep secrets, keys and access rules out of the system prompt, and assume the prompt can be revealed. [OWASP LLM Top 10 2025 LLM07]
10. Limit tokens, context size, requests, tool-call depth, loop count and spend per user and per task, and stop runs that exceed them. [OWASP LLM Top 10 2025 LLM10]
11. Log prompts, tool calls and approvals in a form that supports audit, without storing secrets or raw personal data. [OWASP LLM Top 10 2025 LLM02; OWASP LLM Top 10 2025 LLM06]

## Implementation Notes
- OWASP ASVS 5.0.0 has no chapter for AI features, so the requirement ids come from the LLM Top 10 2025 and from CWE.
- Draw the data-flow map first: who writes each piece of text the model sees, and which tools and outputs it can reach. Risk sits where an untrusted writer and a powerful tool meet.
- Indirect injection is the hard case: the attacker never talks to the model but plants text in a page, a file or a record that a user later asks the model to read.
- No filter reliably detects injection. Plan for the model to be fooled and limit what a fooled model can do.
- Prefer narrow tools (`get_invoice(id)`) over broad ones (`run_sql(text)`, `fetch_url(url)`); broad tools bring in `input.injection` and `network.ssrf_outbound` risks.
- Show approval prompts that state the real action from the tool call, not the model's own description of it.
- Markdown images and links in model output can leak data through their URLs; render them only from an allowlist of hosts.
- Retrieved documents and embeddings need the same access control as the source records; check the asker's rights at query time.
- Example of validating a tool call before running it, shown because the order matters (check, authorize, run):

```
call = parse_schema(model_output, ToolCall)       # reject anything off-schema
require(user_can(call.name, call.args))           # app-side permission check
if call.high_impact: wait_for_human_approval(call)
```

## Review Checklist
- [ ] Read each place a prompt is assembled; list which parts come from users, documents, web pages or tools, and confirm they are labelled as data.
- [ ] Grep for model output flowing to `eval(`, `exec(`, `subprocess`, `os.system`, `execute(`, `innerHTML` or `dangerouslySetInnerHTML`; each hit validates and encodes first or uses a sandbox.
- [ ] Read the tool registry; each tool has a narrow purpose, scoped credentials and an owner, and none runs arbitrary code, SQL or URLs without limits.
- [ ] Grep tool definitions for `delete`, `send`, `pay`, `write`, `admin`; each has human approval or a stated reason it needs none.
- [ ] Read the tool-call handler; it checks the asker's permission in application code, not by trusting the model's request.
- [ ] Read the retrieval code; documents are filtered by the asker's access rights before they enter the prompt.
- [ ] Grep system prompts and prompt templates for keys, tokens, internal URLs and access rules; none are present.
- [ ] Grep for `max_tokens`, timeouts, loop or step caps, and per-user quotas; each model call and agent loop has an upper bound.
- [ ] Read the logging for model calls; prompts and tool calls are recorded without secrets or raw personal data.

## Common Failure Modes
- Treating "ignore instructions in documents" in the system prompt as the defence.
- Giving an agent one broad service account, so a tricked model acts with more rights than the user has.
- Rendering model output as HTML or Markdown with active links, or feeding it to a shell or database call.
- An approval step that shows the model's summary, so the user approves text that differs from the real call.
- Putting API keys, business rules or other users' data in the system prompt or the shared context.
- Retrieval over a shared index with no per-user filter, so one user's question surfaces another's documents.
- No cap on agent loops, tool retries or context size; one request becomes a large bill or a stalled service.
- Trusting a tool result from a web page or an external API as if it came from the user.

## Test Ideas
- Place instruction text in a document, a web page and a tool result that the model will read; the model's tool calls and output do not follow it, or the action is blocked by the application layer.
- Ask the model to reveal its system prompt and hidden context; nothing sensitive is exposed, because nothing sensitive is there.
- Make the model emit HTML with a script, a SQL fragment and a shell string; downstream code treats each as inert text or rejects it.
- Request a high-impact tool call as a low-privilege user; the application refuses it regardless of what the model says.
- Check the approval prompt against the actual call arguments; they match exactly.
- Ask a question whose answer sits in another user's document; the retrieval step returns nothing from it.
- Send an oversized input and a prompt that loops tool calls; limits trigger and the run stops with an error.

## Related Entries
- input.injection: the same data-versus-instruction mistake for SQL, shell and templates.
- authz.access_control: the permission checks the application must make for the model.
- api.web_api: limits, schemas and mass assignment on the endpoint in front of a model.
- network.ssrf_outbound: tools that fetch URLs chosen by the model.
- crypto.secrets: provider keys and tool credentials.
- ops.logging_errors: audit logging without secret leakage.
- supply.dependencies: models, plug-ins, datasets and agent frameworks as supply chain items.

## Sources
- OWASP Top 10 for LLM Applications 2025, index with LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt Leakage, LLM10 Unbounded Consumption: https://genai.owasp.org/llm-top-10/
- OWASP Top 10 for LLM Applications 2025, LLM01 page: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OWASP Top 10 for LLM Applications 2025, resource page: https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- MITRE CWE: CWE-77, CWE-1426, CWE-1427 (names at https://cwe.mitre.org/data/definitions/N.html, N = the number); CWE-1427: https://cwe.mitre.org/data/definitions/1427.html

## License Provenance
- This entry is an original paraphrase, published under this repository's MIT licence. No text is copied from the cited works; they are named as evidence and for ids and titles only.
- OWASP Top 10 for LLM Applications 2025: CC BY-SA 4.0.
- OWASP Cheat Sheet Series: CC BY-SA 4.0.
- MITRE CWE: CWE is a trademark of The MITRE Corporation. CWE ids and names are used under the CWE terms of use (https://cwe.mitre.org/about/termsofuse.html), which require reproducing MITRE's copyright designation and licence; that designation belongs to The MITRE Corporation, and the full notice is on the terms page.
