# Sample catalogue

`catalog.json` is a ready-made product list for trying bepleez without a shop. The sandbox has **no catalogue of its own**:
on every negotiation your backend sends the product record (sku, title, price > 0, currency, description, stock), and bepleez
freezes it when the negotiation opens. The seller states nothing that is not in `description`.

Start with this file; when you are ready, replace the one function that reads it (`get_product(sku)` in the example app)
with a call to your own database or catalogue API. Nothing else changes.

## Budgets to try (observed on the sandbox, not guaranteed)

The seller's limit is set by the merchant and can change; these are what we saw, so you can pick test budgets that end in an agreement, a near miss, or a walk-away. Climbing in steps `(0.8, 0.9, 1.0)` gets lower prices than offering the budget at once.

| sku | list price | agreement seen at | no agreement seen at |
|---|---|---|---|
| `DRILL-18V` | 129.90 | 118 (climbing), 127 (at once) | 100 |
| `VAC-ROBOT` | 249.00 | not reached at 215 (last firm offer 226) | 172 |
| `KETTLE-1L` | 39.90 | not reached at 36 or 30 (last firm offers 38.70, 34.85) | 24 |
| `HEADPHONES-NC` | 189.00 | not reached at 100 (firm offer 183.33) | 100 |
