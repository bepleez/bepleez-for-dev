# Errors

An error comes with `isError: true` and `structuredContent.messages[0].code`. Authentication failures are always `401 invalid_api_key`.

| Code | Meaning | What to do |
|---|---|---|
| `product_missing` | `request_offer` without `product` | send the product record |
| `product_price_missing` | price absent, zero or unreadable | send a price > 0; the seller never invents one |
| `product_invalid` | a field is malformed, or `sku` differs from the requested one | fix the record |
| `quota_exceeded` | daily limit or test plan reached | wait, or ask us to raise it; running negotiations continue |
| `idempotency_key_required` | `counter_offer` without key | add a unique `idempotency_key` |
| `invalid_arguments` | missing or malformed argument | check `tools/list` |
| `turn_in_progress` | the seller is still answering | poll `get_thread`, then retry |
| `unknown_thread` | not one of your negotiations | check `thread_id` |
| `offer_not_acceptable` | no firm offer yet, or unknown `offer_id` | wait for a `firm` offer |
| `option_required` | the offer is a menu | pass the chosen `option_id` |
| `offer_expired` | offer no longer valid | call `get_thread` for the latest offer |
| `no_active_strategy` | no active strategy for this product | contact us |
| `seller_refused` | the seller refused the act | read the message |
| `seller_unavailable` | temporary failure on our side | retry with the same `idempotency_key` |

`status` of a result: `ready` (the seller answered), `in_progress` (poll `get_thread`), `error` (see `turn_error`, resend the same call with the same key).
