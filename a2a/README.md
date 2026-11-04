# A2A example

`app.py` negotiates a price with the seller agent over A2A, Python 3.9+, standard library only. Install `cryptography` to have the seller's signatures verified (the example says so when it is missing).

```bash
export BEPLEEZ_A2A_URL="https://<host>/agents/<seller-id>/a2a"
export BEPLEEZ_API_KEY="bpz_test_..."
python3 app.py --budget 118
```

With a budget the seller can reach, the run ends with an agreement; with a budget below its limit, the shopper walks away after the firm offer.

## What goes on the wire

- `POST <A2A url>` with `Authorization: Bearer <key>`, JSON-RPC `message/send` (or `SendMessage`). The act is a `data` Part under the key `com.bepleez.shopping.intent`; the text is a separate `text` Part.
- **The product record goes in `message.metadata["com.bepleez.shopping.product"]`** of the opening act (`sku`, `title`, `price` > 0, `currency`, `description`, `stock`). It comes from your backend and is frozen when the negotiation opens. It is never part of the shopper's act.
- Acts you send: `request` (need: sku and quantity), `counter` (an indicative offer with your price, `responds_to` the seller's offer id), `say`/`answer` (words), `accept` (`offer_id`, plus `option_id` if the offer is a menu), `close`.
- Your acts are not signed: the key authenticates you. The seller's acts are signed.

## The seller's side

- First answer: an `offer` at the list price (indicative). After your `counter`, a `counter` that can be **firm** (`binding: "firm"`). Only a firm offer can be accepted.
- `accept` is answered by a **`commit`** act: `commitment.code` (a reference such as `BPZ-…`), `total`, `expires_at`, and `signature`. No coupon is created in your system.
- Every seller act carries `signature`: a detached JWS, **ES256**, over the JCS (RFC 8785) form of the act without its `signature` field. The public keys are in the `keys` array of the seller's UCP profile, at `/agents/<seller-id>/.well-known/ucp`. `app.py` implements the check; do the same on your server before honouring the price.
- A seller turn takes 9 to 30 s; configure a timeout of at least 150 s on the call.

Errors come back as a JSON-RPC `error` (HTTP status in `error.data.status`): `401 invalid_api_key`, `429 quota_exceeded`, `422` for a malformed act or missing product record. The full list of codes is in [../ERRORS.md](../ERRORS.md) (MCP names; the meanings are the same).
