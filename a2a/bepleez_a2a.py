"""bepleez over A2A: a small library. Python 3.9+, standard library only.
Install `cryptography` to have the seller's signatures verified (without it they are reported as unchecked).

    import sys; sys.path.insert(0, "bepleez-for-dev/a2a")      # or copy this file next to your code
    from bepleez_a2a import Thread, negotiate, A2AError

    result = negotiate(Thread(a2a_url, key), product, budget=118)   # dict: status, price, code, ...

`negotiate()` is the whole loop (request, counter-offers, optional answer to the seller's question, accept, commit).
Errors raise `A2AError`; nothing here ever prints the key."""
import base64
import json
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

CAPABILITY = "com.bepleez.shopping.intent"
PRODUCT_KEY = "com.bepleez.shopping.product"
VERSION = "2026-10-25"
UA = "Mozilla/5.0 (bepleez a2a example)"


class A2AError(Exception):
    """The call failed (HTTP/JSON-RPC error, or an invalid signature on a seller's act)."""


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
    def __init__(self, a2a_url, key, log=print):
        self.url, self.key, self.log = a2a_url, key, log
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
            raise A2AError(f"A2A error HTTP {status}: {json.dumps((out or {}).get('error') or out)[:300]}")
        acts = [p["data"][CAPABILITY] for p in out["result"].get("parts", []) if isinstance(p.get("data"), dict) and CAPABILITY in p["data"]]
        for a in acts:
            ok = verify_act(a, self.jwks) if a.get("signature") else None
            mark = {True: "signature OK", False: "SIGNATURE INVALID", None: "unsigned/unchecked"}[ok]
            offer = (a.get("body") or {}).get("offer")
            price = f" {offer['pricing']['total']['amount'] / 100:.2f} {offer['pricing']['total']['currency']} ({offer['binding']})" if offer else ""
            self.log(f"  seller {a['act']}{price} [{mark}]\n    {a.get('text') or ''}")
            if ok is False:
                raise A2AError("refusing to continue: invalid signature")
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



# --- the whole negotiation ----------------------------------------------------------------------------------------

def negotiate(thread, product, budget, steps=(1.0,), answer_question=None, max_rounds=6, opening_text=None, counter_text=None):
    """Negotiate `product` (dict: sku, title, price > 0, currency, description, stock) for a shopper who pays `budget` at most.

    steps: share of the budget offered at each counter, e.g. (0.8, 0.9, 1.0) to climb gradually; the last one is repeated.
    answer_question: optional function(question_act) -> text. Called when the seller sends a `question` act; the text is
        sent as an `answer`. A question that exists only in the offer's text needs no answer: the next counter is enough.
    opening_text / counter_text: the words sent with the request and with each counter-offer: a string, or for counter_text a
        function(price) -> str. Put the shopper's SITUATION there (use, deadline, alternative seen), never "my maximum is X".
        The defaults are neutral. Note that the price of a counter-offer is in the act itself: offering your full budget as a
        counter shows it, so keep the last step below 1.0 if the ceiling matters to you.
    Returns a dict: status ("agreed" | "walked_away" | "no_offer" | "no_commit"), and for an agreement price, currency,
    code, expires_at, list_price. A firm offer above the budget is countered while steps remain, then the shopper leaves.
    """
    acts = thread.send(thread.act("request", {"need": {"items": [{"sku": product["sku"], "quantity": 1}]}},
                                  opening_text or f"Hi, I'm interested in the {product['title']}. Is there a better price?"), product=product)
    n = 0
    for _ in range(max_rounds):
        question = next((a for a in acts if a["act"] == "question"), None)
        if question and answer_question:
            acts = thread.send(thread.act("answer", {"data": {}}, answer_question(question), question["message_id"])) or acts
        offer = next((a for a in reversed(acts) if a["act"] in ("offer", "counter") and (a.get("body") or {}).get("offer")), None)
        if offer is None:
            return {"status": "no_offer"}
        o = offer["body"]["offer"]
        price = o["pricing"]["total"]["amount"] / 100
        if o["binding"] == "firm" and price <= budget:
            done = thread.send(thread.act("accept", {"offer_id": o["offer_id"]}, None, offer["message_id"]))
            commit = next((a for a in done if a["act"] == "commit"), None)
            if not commit:
                return {"status": "no_commit"}
            c = commit["body"]["commitment"]
            return {"status": "agreed", "price": c["total"]["amount"] / 100, "currency": c["total"]["currency"],
                    "code": c.get("code"), "expires_at": c.get("expires_at"), "list_price": product["price"]}
        if o["binding"] == "firm" and n >= len(steps):
            return {"status": "walked_away", "last_firm_offer": price}
        mine = round(budget * steps[min(n, len(steps) - 1)], 2)
        n += 1
        text = counter_text(mine) if callable(counter_text) else (counter_text or "Here is my counter-offer.")
        acts = thread.send(thread.counter(offer, mine, text))
    return {"status": "walked_away"}
