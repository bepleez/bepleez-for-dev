# bepleez for dev

Test a bepleez price negotiation from your own backend in about 15 minutes, without Shopify.

Your server calls bepleez's seller agent over **MCP** or **A2A** (both JSON-RPC over HTTPS, same key, same agent). The agent negotiates a price with your shopper, within a limit you set, and returns a **signed agreement token** that your backend verifies before charging that price. The price shown on your site does not change.

> Status: test environment. Test negotiations and product records are not kept as production data. Contract version: see [CHANGELOG.md](CHANGELOG.md).

## What you need

- the **MCP address** of your seller agent and a **test key**, both in your dashboard (dash.bepleez.com > My shop > Integration). You generate the key yourself; it is shown once.
- Python 3 (the quickstart has no dependency) and/or Node 18+.

## Two ways in

| | MCP | A2A |
|---|---|---|
| Example | `quickstart/python/app.py` | `a2a/app.py` |
| You send | tool calls (`request_offer`, `counter_offer`, `accept_offer`) | protocol acts (`request`, `counter`, `accept`) in `message/send` |
| Product | `product` argument | `message.metadata["com.bepleez.shopping.product"]` |
| Slow turns | `async: true` + `get_thread` | none: the call waits (up to ~60 s for the opening) |
| Retries | mandatory `idempotency_key` | resend the same act (same `message_id`) |
| Proof of agreement | `deal_token`, RS256 JWT, see [verify-token/](verify-token/) | signed `commit` act (ES256), checked against the keys of the seller's UCP profile, see [a2a/README.md](a2a/README.md) |

MCP is the simpler contract (structured results, coded errors); choose A2A if your agents already speak the protocol.

## Run it

```bash
export BEPLEEZ_MCP_URL="https://<host>/agents/<seller-id>/mcp"
export BEPLEEZ_API_KEY="bpz_test_..."

python3 quickstart/python/app.py --auto --budget 118   # full negotiation in the terminal
python3 quickstart/python/app.py                       # local mini-site (chat + acceptance)

# A2A (address of the /a2a endpoint instead of /mcp)
export BEPLEEZ_A2A_URL="https://<host>/agents/<seller-id>/a2a"
python3 a2a/app.py --budget 118                        # signatures of the seller's acts are checked (pip install cryptography)
```

Edit `PRODUCT` at the top of each `app.py` to try your own product, or take one from [catalog/catalog.json](catalog/catalog.json). The product always comes from your backend: the sandbox has no catalogue to browse.

## Keep the key safe

- The key lives on your **server** only: never in a web page, a mobile app or browser JavaScript.
- Put it in environment variables or your secret manager. Never commit it (`.env` is git-ignored).
- If it leaks, revoke it in the dashboard (immediate effect) and generate another.

## How a negotiation goes

1. `request_offer`: you send the product **from your backend** (sku, title, price, currency, description) and the shopper's words. The record is frozen when the negotiation opens; a missing or zero price is refused.
2. `counter_offer`: you relay the shopper's answer, with a mandatory `idempotency_key`. After a timeout, resend with the same key: nothing is repeated.
3. `accept_offer`: only after the shopper explicitly agrees. The response carries `agreement.deal_token`.
4. **Verify the token on your server** before charging: see [verify-token/](verify-token/).

A seller turn takes 9 to 17 s (the first up to 60 s): pass `async: true`, then poll `get_thread` until `status` is `ready`. Only a `firm` offer can be accepted. If the offer has `options` (a menu), show every option and pass the chosen `option_id`.

The seller states nothing that is not in the product `description`. You see the acts exchanged, never the seller's internal reasoning.

## Limits of the test plan

100 negotiations in total, 50 per day. Beyond that: `quota_exceeded` (running negotiations continue).

## More

- [catalog/](catalog/): sample product list to send with your calls (the sandbox has no catalogue of its own)
- [a2a/README.md](a2a/README.md): A2A in detail
- [quickstart/curl.md](quickstart/curl.md): the same calls with curl
- [ERRORS.md](ERRORS.md): error codes and what to do
- [CHANGELOG.md](CHANGELOG.md)
- Protocol specification: the `intent-commerce-protocol` repository
- Docs page: https://www.bepleez.com/en/support/developers
- Questions: hello@bepleez.com

## License

The examples in this repository are under the [MIT license](LICENSE). Use of the bepleez service is governed by its terms of use.
