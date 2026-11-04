#!/usr/bin/env python3
"""Verify a bepleez agreement token. pip install "pyjwt[crypto]"

    python3 verify.py <deal_token> <jwks_url> [--sku SKU] [--price 118.0] [--currency EUR]

Exit code 0 and the verified claims on success, 1 otherwise."""
from __future__ import annotations

import argparse
import json
import sys

import jwt  # PyJWT
from jwt import PyJWKClient

ISSUER = "https://api.bepleez.com"


def verify(token: str, jwks_url: str, sku: str | None = None, price: float | None = None, currency: str | None = None) -> dict:
    key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token).key
    claims = jwt.decode(token, key, algorithms=["RS256"], issuer=ISSUER, options={"require": ["exp", "iss"]})
    if sku is not None and str(claims.get("product_id")) != sku:
        raise ValueError(f"sku mismatch: token has {claims.get('product_id')}")
    if price is not None and abs(float(claims.get("price", -1)) - price) > 0.005:
        raise ValueError(f"price mismatch: token has {claims.get('price')}")
    if currency is not None and claims.get("currency") != currency:
        raise ValueError(f"currency mismatch: token has {claims.get('currency')}")
    return claims


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("token")
    ap.add_argument("jwks_url")
    ap.add_argument("--sku")
    ap.add_argument("--price", type=float)
    ap.add_argument("--currency")
    a = ap.parse_args()
    try:
        c = verify(a.token, a.jwks_url, a.sku, a.price, a.currency)
    except Exception as e:  # noqa: BLE001
        print(f"INVALID: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({k: c.get(k) for k in ("product_id", "price", "currency", "offer_id", "exp", "iss")}, indent=2))
