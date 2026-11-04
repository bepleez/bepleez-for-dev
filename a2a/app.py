#!/usr/bin/env python3
"""bepleez over A2A: a complete negotiation from your backend. Python 3.9+, standard library only.
Signature checks of the seller's acts need `pip install cryptography` (without it the example runs and tells you they are skipped).

    export BEPLEEZ_A2A_URL="https://<host>/agents/<seller-id>/a2a"
    export BEPLEEZ_API_KEY="bpz_test_..."          # dashboard > My shop > Integration (shown once, server-side only)
    python3 app.py --budget 105

You send acts (JSON) in A2A `message/send`; the product comes from YOUR backend in `message.metadata`. The key is never printed."""
import argparse
import base64
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

CAPABILITY = "com.bepleez.shopping.intent"
PRODUCT_KEY = "com.bepleez.shopping.product"
VERSION = "2026-10-25"
UA = "Mozilla/5.0 (bepleez a2a example)"

PRODUCT = {  # read by YOUR backend from YOUR catalogue; frozen when the negotiation opens
    "sku": "DEMO-1", "title": "18V cordless drill", "price": 129.9, "currency": "EUR",
    "description": "New, 2-year warranty, 2 batteries and a charger.", "stock": 40,
}


def http(method, url, body=None, key=None):
    headers = {"User-Agent": UA, "Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw[:200].decode(errors="replace")}


# --- signature check (ES256 detached JWS over the JCS form of the act, RFC 7515 App. F + RFC 8785) -------------------

def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _num(v):
    if isinstance(v, int):
        return str(v)
    if v == int(v) and abs(v) < 1e21:
        return str(int(v))
    return repr(v)


def canonical(v):
    if v is None: return "null"
    if v is True: return "true"
    if v is False: return "false"
    if isinstance(v, (int, float)): return _num(v)
    if isinstance(v, str): return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list): return "[" + ",".join(canonical(x) for x in v) + "]"
    keys = sorted(v, key=lambda k: k.encode("utf-16-be"))
    return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical(v[k]) for k in keys) + "}"


def verify_act(act, jwks):
    """True/False, or None when the `cryptography` package is missing."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    except ImportError:
        return None
    token = act.get("signature", "")
    if token.count(".") != 2:
        return False
    header_b64, payload, sig_b64 = token.split(".")
    header = json.loads(_unb64(header_b64))
    jwk = next((k for k in jwks if k.get("kid") == header.get("kid")), None)
    raw = _unb64(sig_b64)
    if payload or header.get("alg") != "ES256" or not jwk or len(raw) != 64:
        return False
    pub = ec.EllipticCurvePublicNumbers(int.from_bytes(_unb64(jwk["x"]), "big"), int.from_bytes(_unb64(jwk["y"]), "big"), ec.SECP256R1()).public_key()
    signing_input = (header_b64 + "." + base64.urlsafe_b64encode(canonical({k: v for k, v in act.items() if k != "signature"}).encode()).rstrip(b"=").decode()).encode()
    try:
        pub.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")), signing_input, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


# --- the conversation ---------------------------------------------------------------------------------------------

class Thread:
    def __init__(self, a2a_url, key):
        self.url, self.key = a2a_url, key
        self.session = str(uuid.uuid4())
        self.seq = 0
        self.me = f"urn:example:buyer:{self.session}"
        self.profile_url = a2a_url[: -len("/a2a")] + "/.well-known/ucp"
        status, profile = http("GET", self.profile_url)
        self.jwks = (profile or {}).get("keys", []) if status == 200 else []

    def act(self, kind, body=None, text=None, in_reply_to=None):
        self.seq += 1
        a = {"protocol": CAPABILITY, "version": VERSION, "message_id": str(uuid.uuid4()), "session_id": self.session,
             "thread_id": self.session, "seq": self.seq, "sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "from": self.me, "to": self.profile_url, "act": kind, "ai_disclosure": True}
        if in_reply_to: a["in_reply_to"] = in_reply_to
        if body is not None: a["body"] = body
        if text: a["text"], a["lang"] = text, "en"
        return a

    def send(self, act, product=None):
        """Send one act. `product` (a dict like PRODUCT) goes with the opening `request` only."""
        message = {"kind": "message", "role": "user", "messageId": act["message_id"], "contextId": self.session,
                   "parts": [{"kind": "data", "data": {CAPABILITY: act}}] + ([{"kind": "text", "text": act["text"]}] if act.get("text") else [])}
        if product:
            message["metadata"] = {PRODUCT_KEY: product}
        status, out = http("POST", self.url, {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "message/send", "params": {"message": message}}, self.key)
        if status != 200 or "error" in (out or {}):
            raise SystemExit(f"A2A error HTTP {status}: {json.dumps((out or {}).get('error') or out)[:300]}")
        acts = [p["data"][CAPABILITY] for p in out["result"].get("parts", []) if isinstance(p.get("data"), dict) and CAPABILITY in p["data"]]
        for a in acts:
            ok = verify_act(a, self.jwks) if a.get("signature") else None
            mark = {True: "signature OK", False: "SIGNATURE INVALID", None: "unsigned/unchecked"}[ok]
            offer = (a.get("body") or {}).get("offer")
            price = f" {offer['pricing']['total']['amount'] / 100:.2f} {offer['pricing']['total']['currency']} ({offer['binding']})" if offer else ""
            print(f"  seller {a['act']}{price} [{mark}]\n    {a.get('text') or ''}")
            if ok is False:
                raise SystemExit("refusing to continue: invalid signature")
        return acts

    def counter(self, offer_in, price, text):
        o = offer_in["body"]["offer"]
        line = o["lines"][0]
        cents = round(price * 100)
        cur = o["pricing"]["total"]["currency"]
        mine = {"offer_id": f"{self.session}-b{self.seq + 1}", "binding": "indicative", "personalized": True, "responds_to": o["offer_id"],
                "accept_signature": "agent",
                "lines": [{"item": line["item"], "unit_price": {"amount": cents, "currency": cur}, "quantity": 1, "line_total": {"amount": cents, "currency": cur}}],
                "pricing": {"total": {"amount": cents, "currency": cur}, "tax_included": True}}
        return self.act("counter", {"offer": mine}, text, offer_in["message_id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=105.0, help="what the simulated shopper will pay at most")
    args = ap.parse_args()
    url, key = os.environ.get("BEPLEEZ_A2A_URL", ""), os.environ.get("BEPLEEZ_API_KEY", "")
    if not url or not key:
        sys.exit("Set BEPLEEZ_A2A_URL and BEPLEEZ_API_KEY (see the header of this file).")
    t = Thread(url, key)
    print(f"Seller keys published in its UCP profile: {len(t.jwks)}")
    print(f"1. request ({PRODUCT['title']}, list price {PRODUCT['price']})")
    acts = t.send(t.act("request", {"need": {"items": [{"sku": PRODUCT["sku"], "quantity": 1}]}}, f"Hi, I need a drill this weekend, my budget is {args.budget:.0f} EUR."), product=PRODUCT)
    for i in range(5):
        offer = next((a for a in reversed(acts) if a["act"] in ("offer", "counter") and (a.get("body") or {}).get("offer")), None)
        if offer is None:
            print("The seller made no offer; stopping.")
            return 1
        o = offer["body"]["offer"]
        price = o["pricing"]["total"]["amount"] / 100
        if o["binding"] == "firm":
            if price <= args.budget:
                print(f"3. accept the firm offer at {price:.2f}")
                done = t.send(t.act("accept", {"offer_id": o["offer_id"]}, None, offer["message_id"]))
                commit = next((a for a in done if a["act"] == "commit"), None)
                if commit:
                    c = commit["body"]["commitment"]
                    print(f"\nAgreement: {c['total']['amount'] / 100:.2f} {c['total']['currency']}, reference {c.get('code')}, expires {c.get('expires_at')}")
                    return 0
                print("No commit received.")
                return 1
            print(f"Firm offer {price:.2f} is above the budget {args.budget:.2f}: the shopper walks away.")
            return 0
        print(f"2.{i + 1} counter at {args.budget:.2f}")
        acts = t.send(t.counter(offer, args.budget, f"I can go up to {args.budget:.0f} EUR, not more."))
    print("No firm offer after 5 rounds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
