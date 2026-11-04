#!/usr/bin/env node
// Verify a bepleez agreement token. Node 18+, no dependency.
//   node verify.mjs <deal_token> <jwks_url> [--sku SKU] [--price 118] [--currency EUR]
import { createPublicKey, verify } from "node:crypto";

const ISSUER = "https://api.bepleez.com";
const b64 = (s) => Buffer.from(s, "base64url");

export async function verifyToken(token, jwksUrl, { sku, price, currency } = {}) {
  const [h, p, s] = token.split(".");
  if (!h || !p || !s) throw new Error("malformed token");
  const header = JSON.parse(b64(h).toString());
  if (header.alg !== "RS256") throw new Error("unexpected alg " + header.alg);
  const jwks = await (await fetch(jwksUrl)).json();
  const jwk = jwks.keys.find((k) => k.kid === header.kid);
  if (!jwk) throw new Error("no key with this kid in the JWKS");
  const ok = verify("RSA-SHA256", Buffer.from(`${h}.${p}`), createPublicKey({ key: jwk, format: "jwk" }), b64(s));
  if (!ok) throw new Error("bad signature");
  const claims = JSON.parse(b64(p).toString());
  if (claims.iss !== ISSUER) throw new Error("unexpected issuer " + claims.iss);
  if (!claims.exp || claims.exp * 1000 < Date.now()) throw new Error("token expired");
  if (sku !== undefined && String(claims.product_id) !== sku) throw new Error("sku mismatch: " + claims.product_id);
  if (price !== undefined && Math.abs(Number(claims.price) - price) > 0.005) throw new Error("price mismatch: " + claims.price);
  if (currency !== undefined && claims.currency !== currency) throw new Error("currency mismatch: " + claims.currency);
  return claims;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [token, jwksUrl, ...rest] = process.argv.slice(2);
  const opt = (n) => { const i = rest.indexOf(n); return i >= 0 ? rest[i + 1] : undefined; };
  try {
    const c = await verifyToken(token, jwksUrl, {
      sku: opt("--sku"), price: opt("--price") && Number(opt("--price")), currency: opt("--currency"),
    });
    const { product_id, price, currency, offer_id, exp, iss } = c;
    console.log(JSON.stringify({ product_id, price, currency, offer_id, exp, iss }, null, 2));
  } catch (e) {
    console.error("INVALID:", e.message);
    process.exit(1);
  }
}
