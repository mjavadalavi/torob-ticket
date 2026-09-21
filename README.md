# Torob Ticket

Torob Ticket is a provider-neutral travel comparison product for flights, trains,
and buses. It keeps the Torob search experience, queries verified OTA adapters,
groups identical journeys, explains the ranking, and sends the user to the
selected seller. Passenger forms and payment do not live in this product.

The active implementation is split into a FastAPI service and an RTL-first
Next.js web client. Runtime code lives in `backend/` and `frontend/`. The
original Laravel application is preserved under `legacy/laravel/` for historical
reference only.

## Highlights

- Live city autocomplete and provider-backed searches for flight, train, and bus.
- Background search jobs with visible queued, running, completed, and failed states.
- One grouped journey card with ranked seller offers and official provider logos.
- Nearby-date availability, filtering, sorting, seller comparison, refund rules,
  and provider-aware seat maps where the upstream contract supports them.
- Same-origin logo and travel API proxies with strict host allowlists.
- Responsive desktop and mobile result layouts with RTL support.

## Run locally (without Docker)

The backend requires Python 3.12+ and the frontend requires Node.js 20+.

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[test]'
backend/.venv/bin/uvicorn app.main:app --app-dir backend \
  --host 127.0.0.1 --reload --port 8100
```

In a second terminal:

```sh
cd frontend
npm install
API_URL=http://127.0.0.1:8100/api/v1 \
  npm run dev -- --hostname 127.0.0.1 --port 3100
```

- Web app: <http://127.0.0.1:3100>
- API: <http://127.0.0.1:8100>
- API health: <http://127.0.0.1:8100/health>
- Interactive API docs: <http://127.0.0.1:8100/docs>

## Run with Docker (optional)

Docker is not required for local development. If you prefer the containerized
setup, run:

```sh
cp .env.torob.example .env
docker compose up --build
```

The default container ports are 3000 for the web client and 8000 for the API.

## Verify

```sh
backend/.venv/bin/pytest -q
cd frontend
npm run typecheck
npm run build
npm run test:e2e
```

The Playwright suite starts isolated servers on ports 8100 and 3100. It covers
live provider-backed city search, all three loading flows, result editing,
official operator and seller logos, nearby dates, seller comparison, mobile
layouts, and expired-result recovery. It does not follow an external OTA link.

## Demo video

The complete live-flow recording is included in [`demo.mp4`](./demo.mp4).
It is a 134.68-second, 1440×900 H.264 MP4 weighing about 9 MB, well below the
five-minute and 200 MB delivery limits.

<video controls preload="metadata" width="960" src="./demo.mp4">
  Your browser does not support inline video. [Download the demo](./demo.mp4).
</video>

The recording covers the home search flow, flight/train/bus tabs, mode-specific
loading states, nearby-date prices, ranked results, official source-site logos,
seller comparison, real OTA pages, and responsive mobile controls. It uses live
provider responses rather than response fixtures.

With the local API and web app already running on ports 8100 and 3100, reproduce
the recording with:

```sh
cd frontend
DEMO_BASE_URL=http://127.0.0.1:3100 \
DEMO_MAX_DURATION_SECONDS=300 \
DEMO_MAX_FILE_SIZE_MB=200 \
npm run demo:record
```

The recorder probes current provider inventory first and selects live dates for
flight, train, and bus automatically. It encodes the final file as H.264 with
`yuv420p` and fast-start metadata for broad playback compatibility.

## API contract

The authoritative wire contract is [`contracts/openapi.yaml`](contracts/openapi.yaml).
TypeScript consumers can import [`contracts/travel.ts`](contracts/travel.ts).
Request examples for all three modes live in [`contracts/fixtures`](contracts/fixtures).
No fabricated response fixture or runtime fallback is used. The primary flow is:

```text
Search request → adapter factory → normalize → group journeys → rank by intent
             → compare seller offers → preview external OTA redirect
```

When adding a provider, implement the `TravelAdapter` port and return the shared
provider-neutral models. Core orchestration and UI cards should remain unchanged.
New transport modes should add a `TravelDetails` variant and register adapters;
they must not introduce mode-specific endpoints.

The registered live provider/mode pairs are:

- flight: Alibaba, SnappTrip, MrBilit, FlyToday, and Booking.ir
- train: Alibaba, SnappTrip, and MrBilit
- bus: Alibaba, SnappTrip, MrBilit, FlyToday, Safar724, and Payaneha

`GET /api/v1/providers?mode=flight|train|bus` exposes the complete audited
provider list for one mode. It distinguishes registered adapters from sources
that are unavailable, access-restricted, protected by human verification,
referral-only, or still unverified. This is integration scope, not live uptime;
per-search outages continue to appear in `provider_failures`.

The other supplied OTA/mode pairs remain research candidates, not registered
adapters. FlyToday train returned an explicit upstream rail-unavailable response;
Booking.ir rail returned HTTP 500, Ghasedak24 reported its rail data center was
disconnected, and Raja rejected corrected encrypted inventory requests with HTTP
403 during verification. SafarMarket flight inventory was live-verified, but its
generated reCAPTCHA challenge requires a separate sandbox and security decision
before production registration. SafarMarket bus is only an outbound Ghasedak24
referral, not an independent inventory source. Fadak Trains, Eligasht, Snapp
Flights, Trip.ir, Payaneh.ir, and Bazargah remain unverified. None of these pairs
may be advertised or queried until their live contracts and redirect paths are
both reproducible and covered by adapter tests.

All adapters use provider web contracts that were verified against live responses.
Provider failures remain visible in the API instead of being replaced with sample
offers. A successful search may still contain zero offers when an OTA has no
inventory for that route and date; this is a real empty state, not a fallback.
Read-only provider calls retry one transient connection failure or HTTP
429/502/503/504 response inside the original total deadline. `Retry-After` is
honored when present; authentication/access errors such as HTTP 403 are never
retried.
Concurrent public searches are admission-limited before they reach the bounded
provider connection pools. Tune `TOROB_TRAVEL_SEARCH_MAX_CONCURRENCY` and
`TOROB_TRAVEL_SEARCH_ADMISSION_TIMEOUT_SECONDS` for the deployment capacity.
Raw provider responses are cached in-process for 30 seconds by default, so changing
the ranking between best, cheapest, and fastest does not immediately recrawl the
same OTA. Tune `TOROB_TRAVEL_ADAPTER_SEARCH_CACHE_TTL_SECONDS` and
`TOROB_TRAVEL_ADAPTER_SEARCH_CACHE_MAX_ENTRIES` to match expected traffic; the TTL
is always capped by the offer lifetime.
Location autocomplete has its own shorter
`TOROB_TRAVEL_LOCATION_TIMEOUT_SECONDS` deadline, so a slow secondary source
cannot hide verified suggestions returned by a responsive adapter.

Offer and protected provider context currently live in one bounded, expiring
in-memory store. Run the API with exactly one worker (`TOROB_TRAVEL_API_WORKERS=1`),
as the application enforces at startup. A shared store such as Redis is required
before scaling the API to multiple workers or replicas.

Seller links open the OTA search for the same route and date. They are not exact
proposal deep links unless a provider contract explicitly supplies one, so the UI
asks the user to recheck price and availability on the seller website. Redirect
hosts are allowlisted per provider rather than in a shared global list.

`price.amount` and `lowest_price.amount` are whole tomans for the complete requested
passenger party. Every grouped offer also returns `passenger_count`, and the UI labels
the amount explicitly as the total for that many passengers. Seller rating and review
count stay `null` unless a verified source supplies them, so unknown reputation never
appears as a fabricated zero or five-star score.

## Design references

The reviewed Torob and OTA flows, plus approved image mockups, are in
[`design/mockups`](design/mockups). The product language is «بلیت ترب» with
internal tabs for «پرواز»، «قطار»، and «اتوبوس». Use «تضمین ترب» and «ترب‌پی» for
the corresponding capability badges.
