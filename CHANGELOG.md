# Versions and changelog

This page tells you which version of the bepleez test API you are talking to, what counts as a change, how long a version stays usable, and what changed and when. Status: **test environment**, no availability guarantee (see the terms of use of the test environment).

## Versioning policy

**Two version numbers, both dates.**

| Number | Where you see it | What it versions |
|---|---|---|
| `contract_version` (today `2026-11-02`) | in every MCP result and in the description of every tool | the MCP tools: names, arguments, result fields, error codes |
| `version` of the protocol (today `2026-10-25`) | in every A2A act (`"version"`) | the acts and their fields (the Intent Commerce protocol) |

**What changes the version (breaking).** A new `contract_version` is issued when an existing tool, argument, result field or error code is removed, renamed, or changes meaning or type; when a required argument is added; or when a behaviour you may rely on changes (for example, idempotency or the rule that only a firm offer can be accepted). The A2A protocol `version` changes on the same kind of change to an act.

**What does not (additive).** New tools, new optional arguments, new fields in a result, new error codes, new values in an open list (such as the `topic` of a question), and wording changes of seller messages are added **without a new version**. Write your code to ignore fields it does not know and to treat an unknown error code as a generic failure.

**How long a version stays usable.** A version remains usable for **12 months after the next one is published**. Its retirement is announced **at least 90 days in advance**, in this file and by e-mail to the address of your account. This is a commitment about the contract, not about the availability of the test environment, which can be interrupted or reset at any time.

**Where to follow it.** Read `contract_version` in the results you receive; read this file; the examples in this repository are updated with the contract (the section "Examples and documentation" lists their changes, which are not contract changes).

**Entries.** Each entry says what changed and whether it is breaking, additive, a fix, or a documentation change. Dates are the day the change reached the test environment.

---

## Contract

### 2026-11-02 — first contract version (current)

MCP (`/agents/<seller-id>/mcp`, key in `Authorization: Bearer`):
- `request_offer`: opens a negotiation. The product record (`sku`, `title`, `price` > 0, `currency`, `description`, `stock`) comes from **your** backend and is frozen at opening. `async: true` returns at once with `status: "in_progress"`.
- `counter_offer`: relays the shopper's answer, with a mandatory `idempotency_key`; resending the same key repeats nothing.
- `accept_offer`: only for a firm offer; returns `agreement.deal_token` (RS256 JWT, public key at `agreement.jwks_url`). Pass `option_id` when the offer is a menu.
- `get_thread`: state of a negotiation; used to poll after `async: true`.
- Every result carries `contract_version`, `thread_id`, `state`, `status` (`ready`, `in_progress`, `error`); structured output schemas are published with the tools; errors are coded (see [ERRORS.md](ERRORS.md)); menus of options (`options`, `option_id`).
- Test plan limits: 100 negotiations in total, 50 per day (`quota_exceeded` beyond).

A2A (`/agents/<seller-id>/a2a`, same key): acts of protocol version `2026-10-25` in `message/send`; the product record goes in `message.metadata["com.bepleez.shopping.product"]` of the opening act; seller acts are signed (ES256) and an accepted firm offer is answered by a signed `commit` act. See [a2a/README.md](a2a/README.md).

### Changes within `2026-11-02` (additive or fixes, no new version)

- **2026-11-05 — fix (A2A).** When a seller's offer already ends with a question and the seller also sends the separate `question` act, the `text` Part that A2A adds for text-only readers is no longer repeated for the `question` act. The `data` Part (the signed act, with its text) is unchanged. Clients that read the acts see no difference; clients that print every `text` Part no longer show the question twice.

---

## Examples and documentation (not contract changes)

### 2026-11-05
- `a2a/bepleez_a2a.py`: importable library (`Thread`, `negotiate()`, `A2AError`) split out of `a2a/app.py`; `Thread.send(act, product=…)` takes the product as an argument. `negotiate()` accepts `steps`, `answer_question`, `opening_text` and `counter_text`; its default texts never state the shopper's budget.
- `AGENTS.md`: where a coding agent should start, rules, and a prompt to paste.
- `catalog/`: sample product list and budgets observed on the test environment.
- `a2a/README.md`: the seller's `question` act and how to answer it; use from your own code.

### 2026-11-04
- First public version of the repository: MCP and A2A examples, `verify-token/`, `ERRORS.md`, this file.
