# Torob Ticket frontend

RTL travel comparison UI for flight, train, and bus offers. The app follows the
Torob visual language and keeps checkout on the selected OTA.

## Run locally

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. Browser requests use the same-origin Next.js API
routes, while server rendering reads the server-only `API_URL`. When the API is unavailable, the UI shows an
explicit live-data error. It never substitutes fabricated fares or seller offers
for a failed provider response.

## Main routes

- `/?mode=flight|train|bus` — mode-aware ticket search
- `/results?mode=flight|train|bus` — ranked offer groups
- `/offers/:id?return_to=...` — seller comparison and confirmed OTA redirect

## Checks

```bash
npm run typecheck
npm run build
npm run test:e2e
```

The Playwright suite starts isolated backend/frontend servers by default and
uses the live provider adapters. Set `E2E_BASE_URL=http://127.0.0.1:3000` to
exercise an already-running local instance instead.
