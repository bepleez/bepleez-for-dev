#!/usr/bin/env python3
"""bepleez over A2A: a complete negotiation from your backend. Python 3.9+, standard library only.
Signature checks of the seller's acts need `pip install cryptography` (without it the example runs and tells you they are skipped).

    export BEPLEEZ_A2A_URL="https://<host>/agents/<seller-id>/a2a"
    export BEPLEEZ_API_KEY="bpz_test_..."          # dashboard > My shop > Integration (shown once, server-side only)
    python3 app.py --budget 105

The logic lives in `bepleez_a2a.py` (importable, see its header); this file only wires the environment and a product.
The product comes from YOUR backend and is frozen when the negotiation opens."""
import argparse
import os
import sys

from bepleez_a2a import A2AError, Thread, negotiate

PRODUCT = {  # read by YOUR backend from YOUR catalogue; frozen when the negotiation opens
    "sku": "DEMO-1", "title": "18V cordless drill", "price": 129.9, "currency": "EUR",
    "description": "New, 2-year warranty, 2 batteries and a charger.", "stock": 40,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=105.0, help="what the simulated shopper will pay at most")
    ap.add_argument("--gradual", action="store_true", help="climb to the budget in three steps (80, 90, 100 %%) instead of offering it at once")
    args = ap.parse_args()
    url, key = os.environ.get("BEPLEEZ_A2A_URL", ""), os.environ.get("BEPLEEZ_API_KEY", "")
    if not url or not key:
        sys.exit("Set BEPLEEZ_A2A_URL and BEPLEEZ_API_KEY (see the header of this file).")
    try:
        t = Thread(url, key)
        print(f"Seller keys published in its UCP profile: {len(t.jwks)}")
        result = negotiate(t, PRODUCT, args.budget, steps=(0.8, 0.9, 1.0) if args.gradual else (1.0,),
                           answer_question=lambda q: "It is for a weekend project, I need it this week.")
    except A2AError as e:
        sys.exit(str(e))
    if result["status"] == "agreed":
        print(f"\nAgreement: {result['price']:.2f} {result['currency']}, reference {result['code']}, expires {result['expires_at']}")
        return 0
    print(f"\nNo agreement: {result}")
    return 0 if result["status"] == "walked_away" else 1


if __name__ == "__main__":
    sys.exit(main())
