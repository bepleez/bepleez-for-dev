# The calls with curl

```bash
H=(-H "Authorization: Bearer $BEPLEEZ_API_KEY" -H "Content-Type: application/json")
```

Open (asynchronous):

```bash
curl -s "$BEPLEEZ_MCP_URL" "${H[@]}" -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"request_offer","arguments":{
  "product":{"sku":"DEMO-1","title":"18V cordless drill","price":129.9,"currency":"EUR",
             "description":"New, 2-year warranty, 2 batteries and a charger.","stock":40},
  "message":"Hi, I need a drill for this weekend, my budget is 110 EUR.",
  "idempotency_key":"open-0001-demo","async":true}}}'
```

Poll until `structuredContent.status` is `ready`:

```bash
curl -s "$BEPLEEZ_MCP_URL" "${H[@]}" -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_thread","arguments":{"thread_id":"<thread_id>"}}}'
```

Counter-offer (the same `idempotency_key` replays, never repeats):

```bash
curl -s "$BEPLEEZ_MCP_URL" "${H[@]}" -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"counter_offer","arguments":{
  "thread_id":"<thread_id>","message":"Could you do 118 EUR?","price":118,"idempotency_key":"counter-0001-demo","async":true}}}'
```

Accept (only after the shopper agrees; add `option_id` for a menu):

```bash
curl -s "$BEPLEEZ_MCP_URL" "${H[@]}" -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"accept_offer","arguments":{"thread_id":"<thread_id>","offer_id":"<offer_id>"}}}'
```

List the tools with their exact input and output schemas: `{"jsonrpc":"2.0","id":5,"method":"tools/list"}`.
