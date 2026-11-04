# Sample catalogue

`catalog.json` is a ready-made product list for trying bepleez without a shop. The sandbox has **no catalogue of its own**:
on every negotiation your backend sends the product record (sku, title, price > 0, currency, description, stock), and bepleez
freezes it when the negotiation opens. The seller states nothing that is not in `description`.

Start with this file; when you are ready, replace the one function that reads it (`get_product(sku)` in the example app)
with a call to your own database or catalogue API. Nothing else changes.
