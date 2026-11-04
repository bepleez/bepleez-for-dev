#!/usr/bin/env python3
"""App d'essai autonome du sandbox bepleez for dev (MCP, clé Bearer). Python 3, aucune dépendance.

Elle joue le rôle du backend d'un développeur : elle ne connaît que l'adresse MCP et la clé, données par l'environnement.

    export BEPLEEZ_MCP_URL="https://bepleez-staging.up.railway.app/agents/<id du vendeur>/mcp"
    export BEPLEEZ_API_KEY="bpz_test_..."          # affichée une fois dans Ma boutique → Intégration

    python3 app.py --auto                # négociation complète dans le terminal
    python3 app.py --auto --budget 100   # budget de l'acheteur (défaut 105)
    python3 app.py                       # mini-site local http://127.0.0.1:8000 (chat + acceptation)

Le produit (fiche gelée à l'ouverture) est défini en haut du fichier : modifiez PRODUCT pour essayer d'autres cas.
La clé n'est jamais affichée ni écrite."""
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
    "title": "Perceuse visseuse 18V",
    "price": 129.9,
    "currency": "EUR",
    "description": "Neuve, garantie 2 ans, livrée avec 2 batteries et un chargeur.",
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
    """État d'une négociation : un fil, la dernière offre, les messages échangés."""

    def __init__(self, mcp: Mcp):
        self.mcp, self.thread, self.offer, self.agreement, self.log = mcp, "", {}, None, []

    def _absorb(self, state: dict):
        for m in state.get("seller_messages") or []:
            self.log.append({"from": "vendeur", "text": m})
        self.offer = state.get("current_offer") or self.offer
        self.agreement = state.get("agreement") or self.agreement

    def start(self, message: str):
        self.log.append({"from": "acheteur", "text": message})
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
        raise McpError("timeout", "le vendeur n'a pas répondu en 150 s")

    def say(self, message: str, price=None):
        self.log.append({"from": "acheteur", "text": message})
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
    print(f"Produit : {PRODUCT['title']} à {PRODUCT['price']} {PRODUCT['currency']} — budget de l'acheteur : {budget:g}")
    shop.start(f"Bonjour, je cherche ce produit, mon budget est de {budget:g} €.")
    show(shop, "Ouverture")
    for turn in range(1, 7):
        total = float((shop.offer.get("total") or {}).get("amount", 0) or 0)
        if shop.offer.get("binding") == "firm" and 0 < total <= budget:
            break
        shop.say(f"Je peux aller jusqu'à {budget:g} €, pas plus.", price=budget)
        show(shop, f"Tour {turn}")
    total = float((shop.offer.get("total") or {}).get("amount", 0) or 0)
    if shop.offer.get("binding") != "firm" or not 0 < total <= budget:
        print(f"\nPas d'accord dans le budget après 6 tours (dernière offre : {shop.offer.get('total')}).")
        return 1
    print(f"\nOffre ferme à {total:g} : j'accepte.")
    checks = shop.accept()
    a = shop.agreement or {}
    print("Accord :", {k: a.get(k) for k in ("price", "currency", "sku", "expires_at")})
    print("Jeton d'accord reçu :", bool(a.get("deal_token")))
    print("Vérification :", json.dumps(checks))
    return 0 if a.get("deal_token") else 1


def show(shop: Shop, title: str = ""):
    """Affiche tout ce qui s'est dit depuis le dernier appel (acheteur et vendeur, textes complets) puis l'offre en cours."""
    import textwrap
    done = getattr(shop, "_shown", 0)
    if title:
        print(f"\n── {title} " + "─" * max(0, 60 - len(title)))
    for e in shop.log[done:]:
        who = "Acheteur" if e["from"] == "acheteur" else "Vendeur "
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
<form id=f><input id=i autocomplete=off placeholder="Votre message (un montant en € est lu comme contre-offre)"> <button>Envoyer</button></form>
<pre id=out></pre>
<script>
const $=id=>document.getElementById(id);let started=false;
async function post(p,b){const r=await fetch(p,{method:'POST',body:JSON.stringify(b||{})});return r.json()}
function render(s){$('t').textContent=s.product;$('log').innerHTML=s.log.map(e=>`<div class="m ${e.from=='vendeur'?'v':''}">${e.text}</div>`).join('');
 const o=s.offer||{};let h='';if(o.total){h=`<div class=offer>Offre ${o.binding||''} : <b>${o.total.amount} ${o.total.currency}</b>`;
 if(o.binding=='firm'&&!s.agreement)h+=` <button onclick="acc()">Accepter</button>`;h+='</div>'}$('offer').innerHTML=h;
 if(s.error)$('out').textContent='Erreur : '+s.error;else if(s.checks)$('out').textContent='Accord : '+JSON.stringify(s.agreement)+'\\nVérification : '+JSON.stringify(s.checks)}
$('f').onsubmit=async e=>{e.preventDefault();const m=$('i').value.trim();if(!m)return;$('i').value='';$('out').textContent='Le vendeur réfléchit…';
 render(await post(started?'/api/say':'/api/start',{message:m}));started=true;if(!$('out').textContent.startsWith('Erreur'))$('out').textContent=''};
async function acc(){$('out').textContent='Acceptation…';render(await post('/api/accept'))}
$('t').textContent='Écrivez votre premier message (ex : « Bonjour, je cherche une perceuse, budget 110 € »)';
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
    ap.add_argument("--auto", action="store_true", help="négociation complète dans le terminal")
    ap.add_argument("--budget", type=float, default=105.0, help="budget de l'acheteur en mode --auto")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    url, key = os.environ.get("BEPLEEZ_MCP_URL", "").strip(), os.environ.get("BEPLEEZ_API_KEY", "").strip()
    if not url or not key:
        print("Variables BEPLEEZ_MCP_URL et BEPLEEZ_API_KEY requises (voir l'en-tête du fichier).")
        return 2
    mcp = Mcp(url, key)
    try:
        if args.auto:
            return run_auto(mcp, args.budget)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(Shop(mcp)))
        print(f"Mini-site sur http://127.0.0.1:{args.port} (Ctrl+C pour arrêter)")
        server.serve_forever()
    except McpError as e:
        print(f"Erreur du serveur : {e}")
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
