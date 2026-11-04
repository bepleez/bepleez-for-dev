#!/usr/bin/env python3
"""bepleez over MCP: a complete negotiation from your backend (Bearer key). Python 3, standard library only.

It plays the role of a developer's backend: it only knows the MCP address and the key, given by the environment.

    export BEPLEEZ_MCP_URL="https://<host>/agents/<seller-id>/mcp"
    export BEPLEEZ_API_KEY="bpz_test_..."          # shown once in dashboard > My shop > Integration

    python3 app.py --auto                # full negotiation in the terminal
    python3 app.py --auto --budget 100   # shopper's budget (default 105)
    python3 app.py                       # local mini-site http://127.0.0.1:8000 (chat + acceptance)

The product (record frozen when the negotiation opens) is defined at the top of the file: edit PRODUCT to try other cases.
The key is never printed or written."""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PRODUCT = {
    "sku": "DEMO-1",
    "title": "18V cordless drill",
    "price": 129.9,
    "currency": "EUR",
    "description": "New, 2-year warranty, 2 batteries and a charger.",
    "stock": 40,
}
UA = "Mozilla/5.0 (bepleez sandbox app)"


class McpError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code} {detail}".strip())
        self.code = code


class Mcp:
    def __init__(self, url: str, key: str):
        self.url, self.key, self.n = url, key, 0

    def tool(self, name: str, arguments: dict) -> dict:
        self.n += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self.n, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}}).encode()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "User-Agent": UA, "Content-Type": "application/json", "Authorization": f"Bearer {self.key}"})
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                out = json.loads(r.read() or b"null") or {}
        except urllib.error.HTTPError as e:
            code = {401: "invalid_api_key", 429: "quota_exceeded"}.get(e.code, f"http_{e.code}")
            raise McpError(code, e.read()[:200].decode(errors="replace"))
        except urllib.error.URLError as e:
            raise McpError("unreachable", str(e.reason))
        result = out.get("result") or {}
        data = result.get("structuredContent") or {}
        if result.get("isError") or "error" in out:
            msg = (data.get("messages") or [{}])[0]
            raise McpError(msg.get("code") or "error", msg.get("text") or json.dumps(out.get("error", ""))[:200])
        return data


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read() or b"null")


class Shop:
    """State of a negotiation: one thread, the latest offer, the messages exchanged."""

    def __init__(self, mcp: Mcp):
        self.mcp, self.thread, self.offer, self.agreement, self.log = mcp, "", {}, None, []

    def _absorb(self, state: dict):
        for m in state.get("seller_messages") or []:
            self.log.append({"from": "seller", "text": m})
        self.offer = state.get("current_offer") or self.offer
        self.agreement = state.get("agreement") or self.agreement

    def start(self, message: str):
        self.log.append({"from": "buyer", "text": message})
        d = self.mcp.tool("request_offer", {"product": PRODUCT, "message": message, "async": True,
                                            "idempotency_key": "app-open-" + uuid.uuid4().hex[:12]})
        self.thread = d["thread_id"]
        end = time.time() + 150
        while time.time() < end:
            state = self.mcp.tool("get_thread", {"thread_id": self.thread})
            if state.get("status") != "in_progress":
                self._absorb(state)
                return
            time.sleep(3)
        raise McpError("timeout", "the seller did not answer within 150 s")

    def say(self, message: str, price=None):
        self.log.append({"from": "buyer", "text": message})
        args = {"thread_id": self.thread, "message": message, "idempotency_key": "app-counter-" + uuid.uuid4().hex[:12]}
        if price is not None:
            args["price"] = price
        self._absorb(self.mcp.tool("counter_offer", args))

    def accept(self) -> dict:
        d = self.mcp.tool("accept_offer", {"thread_id": self.thread})
        self.agreement = d.get("agreement") or {}
        return self.verify()

    def verify(self) -> dict:
        a, out = self.agreement or {}, {}
        for label, field in (("verdict", "verify_url"), ("jwks", "jwks_url")):
            if a.get(field):
                try:
                    status, body = get_json(a[field])
                    out[label] = {"http": status, "valid": (body or {}).get("valid"), "status": (body or {}).get("status"),
                                  "keys": len((body or {}).get("keys") or [])}
                except Exception as e:  # noqa: BLE001 — l'essai continue
                    out[label] = {"error": str(e)}
        return out

    def view(self) -> dict:
        return {"thread": self.thread, "log": self.log, "offer": self.offer, "agreement": self.agreement}


def price_in(text: str):
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|eur|euros?)?", text, re.I)
    return float(m.group(1).replace(",", ".")) if m else None


# --- mode terminal -----------------------------------------------------------

def run_auto(mcp: Mcp, budget: float) -> int:
    shop = Shop(mcp)
    print(f"Product: {PRODUCT['title']} at {PRODUCT['price']} {PRODUCT['currency']} — shopper's budget: {budget:g}")
    shop.start(f"Hi, I'm looking for this product, my budget is {budget:g} EUR.")
    show(shop, "Ouverture")
    for turn in range(1, 7):
        total = float((shop.offer.get("total") or {}).get("amount", 0) or 0)
        if shop.offer.get("binding") == "firm" and 0 < total <= budget:
            break
        shop.say(f"I can go up to {budget:g} EUR, not more.", price=budget)
        show(shop, f"Tour {turn}")
    total = float((shop.offer.get("total") or {}).get("amount", 0) or 0)
    if shop.offer.get("binding") != "firm" or not 0 < total <= budget:
        print(f"\nNo agreement within the budget after 6 rounds (last offer: {shop.offer.get('total')}).")
        return 1
    print(f"\nFirm offer at {total:g}: I accept.")
    checks = shop.accept()
    a = shop.agreement or {}
    print("Agreement:", {k: a.get(k) for k in ("price", "currency", "sku", "expires_at")})
    print("Agreement token received:", bool(a.get("deal_token")))
    print("Checks:", json.dumps(checks))
    return 0 if a.get("deal_token") else 1


def show(shop: Shop, title: str = ""):
    """Print everything said since the last call (shopper and seller, full texts) then the current offer."""
    import textwrap
    done = getattr(shop, "_shown", 0)
    if title:
        print(f"\n── {title} " + "─" * max(0, 60 - len(title)))
    for e in shop.log[done:]:
        who = "Shopper" if e["from"] == "buyer" else "Seller  "
        body = textwrap.fill(e["text"], width=96, initial_indent="", subsequent_indent=" " * 13)
        print(f"  {who} : {body}")
    shop._shown = len(shop.log)
    o = shop.offer or {}
    amount = (o.get("total") or {}).get("amount")
    cur = (o.get("total") or {}).get("currency", "")
    extra = {k: v for k, v in o.items() if k not in ("total", "binding", "lines") and v not in (None, "", [], {})}
    kind = {"firm": "ferme (engageante)", "indicative": "indicative (non engageante)"}.get(o.get("binding"), o.get("binding"))
    print(f"  → Offre {kind} : {amount} {cur}" + (f"   {extra}" if extra else ""))


# --- mode mini-site ----------------------------------------------------------

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>App d'essai bepleez</title>
<style>body{font:16px system-ui;max-width:640px;margin:2rem auto;padding:0 16px}h1{font-size:1.2rem}
.m{padding:.5rem .8rem;margin:.4rem 0;border-radius:10px;background:#eee}.m.v{background:#0b1b3d;color:#fff}
.offer{border:1px solid #888;padding:.6rem;border-radius:10px;margin:.6rem 0}input{width:70%;padding:.5rem}button{padding:.5rem 1rem}
pre{background:#f4f4f4;padding:.6rem;overflow:auto}</style>
<h1 id=t></h1><div id=log></div><div id=offer></div>
<form id=f><input id=i autocomplete=off placeholder="Your message (an amount in EUR is read as a counter-offer)"> <button>Send</button></form>
<pre id=out></pre>
<script>
const $=id=>document.getElementById(id);let started=false;
async function post(p,b){const r=await fetch(p,{method:'POST',body:JSON.stringify(b||{})});return r.json()}
function render(s){$('t').textContent=s.product;$('log').innerHTML=s.log.map(e=>`<div class="m ${e.from=='seller'?'v':''}">${e.text}</div>`).join('');
 const o=s.offer||{};let h='';if(o.total){h=`<div class=offer>Offre ${o.binding||''} : <b>${o.total.amount} ${o.total.currency}</b>`;
 if(o.binding=='firm'&&!s.agreement)h+=` <button onclick="acc()">Accepter</button>`;h+='</div>'}$('offer').innerHTML=h;
 if(s.error)$('out').textContent='Error: '+s.error;else if(s.checks)$('out').textContent='Agreement: '+JSON.stringify(s.agreement)+'\\nChecks: '+JSON.stringify(s.checks)}
$('f').onsubmit=async e=>{e.preventDefault();const m=$('i').value.trim();if(!m)return;$('i').value='';$('out').textContent='The seller is thinking…';
 render(await post(started?'/api/say':'/api/start',{message:m}));started=true;if(!$('out').textContent.startsWith('Erreur'))$('out').textContent=''};
async function acc(){$('out').textContent='Acceptation…';render(await post('/api/accept'))}
$('t').textContent='Write your first message (e.g. “Hi, I need a drill, budget 110 EUR”)';
</script>"""


def make_handler(shop: Shop):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            raw = body if isinstance(body, bytes) else body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self._send(200, PAGE, "text/html") if self.path == "/" else self._send(404, "{}")

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0) or 2) or b"{}")
            extra = {}
            try:
                if self.path == "/api/start":
                    shop.__init__(shop.mcp)
                    shop.start(body.get("message", ""))
                elif self.path == "/api/say":
                    shop.say(body.get("message", ""), price_in(body.get("message", "")))
                elif self.path == "/api/accept":
                    extra["checks"] = shop.accept()
                else:
                    return self._send(404, "{}")
            except McpError as e:
                extra["error"] = str(e)
            self._send(200, json.dumps({**shop.view(), "product": PRODUCT["title"], **extra}))

        def log_message(self, *a):  # silence
            pass

    return H


def main() -> int:
    ap = argparse.ArgumentParser(description="App d'essai du sandbox bepleez for dev")
    ap.add_argument("--auto", action="store_true", help="full negotiation in the terminal")
    ap.add_argument("--budget", type=float, default=105.0, help="shopper's budget in --auto mode")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    url, key = os.environ.get("BEPLEEZ_MCP_URL", "").strip(), os.environ.get("BEPLEEZ_API_KEY", "").strip()
    if not url or not key:
        print("BEPLEEZ_MCP_URL and BEPLEEZ_API_KEY are required (see the header of this file).")
        return 2
    mcp = Mcp(url, key)
    try:
        if args.auto:
            return run_auto(mcp, args.budget)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(Shop(mcp)))
        print(f"Mini-site on http://127.0.0.1:{args.port} (Ctrl+C to stop)")
        server.serve_forever()
    except McpError as e:
        print(f"Erreur du serveur : {e}")
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
