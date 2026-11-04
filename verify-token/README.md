# Verify the agreement token

`accept_offer` returns `agreement.deal_token`, a JWT signed **RS256**. Your backend must verify it before charging the negotiated price:

1. signature, against the public key published at `agreement.jwks_url` (pick the key whose `kid` is in the token header);
2. `iss` equals `https://api.bepleez.com`;
3. `exp` not passed;
4. `product_id` is your sku, and `price` / `currency` are what you are about to charge.

Never trust a price sent by the browser; take it from the verified claims.

```bash
pip install "pyjwt[crypto]"
python3 verify.py "<deal_token>" "<jwks_url>" --sku DEMO-1          # prints the verified price
node verify.mjs  "<deal_token>" "<jwks_url>" --sku DEMO-1          # Node 18+, no dependency
```

Claims you can rely on: `product_id`, `price`, `currency`, `offer_id`, `exp`, `iss`. (`agreement.verify_url` is a convenience check done by bepleez; your own verification is the one that counts.)
