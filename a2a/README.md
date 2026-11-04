# A2A example

`app.py` negotiates a price with the seller agent over A2A, Python 3.9+, standard library only. Install `cryptography` to have the seller's signatures verified (the example says so when it is missing).

```bash
export BEPLEEZ_A2A_URL="https://<host>/agents/<seller-id>/a2a"
export BEPLEEZ_API_KEY="bpz_test_..."
python3 app.py --budget 118 --gradual
```

With a budget the seller can reach, the run ends with an agreement; with a budget below its limit, the shopper walks away after the firm offer.

## Use it from your own code

`bepleez_a2a.py` is the library (standard library only); `app.py` is a thin script around it. Copy `bepleez_a2a.py` next to your code, or add this folder to `sys.path`:

```python
import sys; sys.path.insert(0, "bepleez-for-dev/a2a")
from bepleez_a2a import Thread, negotiate, A2AError

product = {"sku": "DRILL-18V", "title": "18V cordless drill", "price": 129.9, "currency": "EUR",
           "description": "New, 2-year warranty, 2 batteries and a charger.", "stock": 40}   # from YOUR catalogue
try:
    result = negotiate(Thread(a2a_url, key), product, budget=118, steps=(0.8, 0.9, 1.0))
except A2AError as e:       # HTTP / JSON-RPC error, or an invalid signature on a seller's act
    ...
# result: {"status": "agreed", "price": 106.2, "currency": "EUR", "code": "BPZ-...", "expires_at": "...", "list_price": 129.9}
#      or {"status": "walked_away", "last_firm_offer": 183.33} / {"status": "no_offer"} / {"status": "no_commit"}
```

- `steps` = share of the budget offered at each counter. `(1.0,)` (default) offers the whole budget at once: the seller then answers with a firm offer close to the list price. `(0.8, 0.9, 1.0)` climbs gradually (in our few runs it ended at 106.20 for a budget of 118, where offering 118 at once met a firm offer of 118.84 or more; too few runs to say it always ends lower).
- `opening_text` / `counter_text`: the words sent with the request and with each counter (a string, or `counter_text=lambda price: ...`). Say the situation, never the ceiling.
- `answer_question` (optional function) answers the seller's `question` act, see below. `Thread(url, key, log=print)`: pass your own `log` function, or `lambda *_: None` to silence it.
- The loop (`negotiate`) is short; read it and adapt it (ask your shopper between rounds, for instance).

## What goes on the wire

- `POST <A2A url>` with `Authorization: Bearer <key>`, JSON-RPC `message/send` (or `SendMessage`). The act is a `data` Part under the key `com.bepleez.shopping.intent`; the text is a separate `text` Part.
- **The product record goes in `message.metadata["com.bepleez.shopping.product"]`** of the opening act (`sku`, `title`, `price` > 0, `currency`, `description`, `stock`). It comes from your backend and is frozen when the negotiation opens. It is never part of the shopper's act.
- Acts you send: `request` (need: sku and quantity), `counter` (an indicative offer with your price, `responds_to` the seller's offer id), `say`/`answer` (words), `accept` (`offer_id`, plus `option_id` if the offer is a menu), `close`.
- Your acts are not signed: the key authenticates you. The seller's acts are signed.

## The seller's side

- First answer: an `offer` at the list price (indicative). After your `counter`, a `counter` that can be **firm** (`binding: "firm"`). Only a firm offer can be accepted.
- `accept` is answered by a **`commit`** act: `commitment.code` (a reference such as `BPZ-…`), `total`, `expires_at`, and `signature`. No coupon is created in your system.
- Every seller act carries `signature`: a detached JWS, **ES256**, over the JCS (RFC 8785) form of the act without its `signature` field. The public keys are in the `keys` array of the seller's UCP profile, at `/agents/<seller-id>/.well-known/ucp`. `app.py` implements the check; do the same on your server before honouring the price.
- A seller turn takes 9 to 30 s, the first one (the opening) up to 60 s; configure a timeout of at least 150 s on the call.

## The seller asks a question

From time to time a response contains, after its `offer` or `counter`, a separate act `question` (signed like the others), for example `{"topic": "buyer_batna"}` with the question in `text` ("Have you seen a comparable drill elsewhere?"). The same question is usually already written at the end of the preceding offer's text: show it once. A question can also exist **only in the text** of an offer, with no `question` act: then there is nothing to answer by reference, and your next `counter` (or a `say` with your words) is enough.

- **Answering is optional.** An unanswered question never blocks the thread, and a firm offer already issued stays valid. You can simply send your next `counter` or `accept`.
- **To answer**, send an `answer` act whose `in_reply_to` is the `message_id` of the question (always set it; we have not tested an `answer` without it), with the words in `text`. `body.data` can stay empty (`{"data": {}}`): the seller reads your `text`.
- **What comes back**: a new `offer` (firm, in our test) that takes your answer into account. Run on the sandbox: after "it is for a weekend project, I need it this week", the seller answered with a new firm offer of 113.47 EUR (previous firm offer: 118.84 EUR).
- **Never answer with the shopper's maximum budget or other private limits**: tell the seller about the situation (use, deadline, alternative seen), not your ceiling.

With the library: `negotiate(..., answer_question=lambda q: "It is for a weekend project, I need it this week.")`.

Errors come back as a JSON-RPC `error` (HTTP status in `error.data.status`): `401 invalid_api_key`, `429 quota_exceeded`, `422` for a malformed act or missing product record. The full list of codes is in [../ERRORS.md](../ERRORS.md) (MCP names; the meanings are the same).
