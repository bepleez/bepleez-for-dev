# For coding agents

You are helping a developer build an app that negotiates a price with bepleez's seller agent. This file tells you where to start and what not to get wrong. Read `README.md` first for the model, then `a2a/README.md`.

## Start here

1. The developer has put two values in a `.env` file (never in the repo): `BEPLEEZ_A2A_URL` (ends with `/a2a`) and `BEPLEEZ_API_KEY` (starts with `bpz_test_`). If they are missing, stop and ask the developer to create them in the dashboard (My shop > Integration); do not guess an address.
2. Use the library, do not rewrite it: `a2a/bepleez_a2a.py` (standard library only). Add `a2a/` to `sys.path` or copy the file, then:

```python
from bepleez_a2a import Thread, negotiate, A2AError
result = negotiate(Thread(url, key), product, budget=118, steps=(0.8, 0.9, 1.0))
```

3. Products: take them from `catalog/catalog.json` for a first run; in the developer's real app they come from the developer's own backend. The sandbox has no catalogue to browse.
4. Install `cryptography` in a virtual environment (`python3 -m venv .venv && .venv/bin/pip install cryptography`) so the seller's signatures are verified; without it they are reported as unchecked.
5. Run it for real once. A seller turn takes 9 to 30 s, the opening up to 60 s, so a full negotiation takes minutes: use a timeout of at least 150 s per call and 10 minutes for a run.

## Rules

- **Never print, log or commit the key.** Load `.env` yourself; keep `.env` out of git; never put the key in a web page or mobile app.
- **The product record comes from the developer's backend** and is frozen when the negotiation opens (`sku`, `title`, `price` > 0, `currency`, `description`, `stock`). The seller states nothing that is not in `description`.
- **Only a firm offer can be accepted.** Never accept an indicative one. Accept only if the price is within the shopper's budget.
- **Never put the shopper's maximum budget in a message** to the seller (it is private); say the situation (use, deadline), not the ceiling.
- The seller may send a `question` act. Answering is optional (`negotiate(..., answer_question=fn)`); if you answer, set `in_reply_to` to the question's `message_id`.
- The test plan allows 100 negotiations in total and 50 a day. Do not loop over many products "to see": each one counts.
- Errors raise `A2AError` (`401 invalid_api_key`: wrong key or wrong address; `429 quota_exceeded`; `422`: malformed act or missing product record). Codes are listed in `ERRORS.md` (MCP names; the meanings are the same).
- Before honouring a price on a server, verify the agreement: the signed `commit` act (A2A, checked against the keys of the seller's UCP profile) or the `deal_token` (MCP, see `verify-token/`).

## A starter prompt for the developer to paste

> Build a small app that negotiates the price of products from my catalogue with bepleez, using the examples in this repository (https://github.com/bepleez/bepleez-for-dev). My `.env` has `BEPLEEZ_A2A_URL` and `BEPLEEZ_API_KEY`. Follow `AGENTS.md`. Take 3 products from `catalog/catalog.json` with a budget each (one reachable, one borderline, one too low), run it once for real, and write the outcome of each negotiation to `deals.json`.
