# Torob Ticket

Torob Ticket is a provider-neutral travel comparison product. It keeps the Torob
search experience, compares offers from flight/train/bus OTA adapters, explains
the ranking, and sends checkout to the selected OTA. Passenger forms and payment
do not live in this product.

The new implementation is split into a FastAPI service and a RTL Next.js web
client. The original Laravel code in this repository is retained as historical
reference only; it is not part of the new runtime.

## Run with Docker

```sh
cp .env.torob.example .env
docker compose up --build
```

- Web: <http://localhost:3000>
- API: <http://localhost:8000>
- API health: <http://localhost:8000/health>
- Interactive API docs: <http://localhost:8000/docs>

## Run without Docker

The backend requires Python 3.12+ and the frontend requires Node.js 20+.

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[test]'
backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000

cd frontend
npm install
API_URL=http://localhost:8000/api/v1 npm run dev
```

## Verify

```sh
backend/.venv/bin/pytest -q
cd frontend
npm run typecheck
npm run build
npm run test:e2e
```

The browser suite starts isolated servers on ports 8100 and 3100 and exercises
live provider-backed city search, a bus result flow, inline result editing,
seller comparison, and expired-result recovery. It never follows the external
OTA link.

## Demo video

[`demo.mp4`](demo.mp4) is an 81-second, 1440×900 recording of the live product.
It shows searchable cities, the shared and mode-specific loading states,
five-day nearby prices, ranked flight results, seller details and refund rules,
real train results, responsive mobile views, and the bus seat-map entry plus
provider-aware seat availability state. No
response fixture is used while recording. With production servers running on
ports 8100 and 3100, the reproducible recorder can be run with:

```sh
cd frontend
DEMO_BASE_URL=http://127.0.0.1:3100 \
npm run demo:record
```

The recorder probes current provider inventory first and chooses live dates for
flight, train, and bus automatically. It then completes every journey from the
home search form, including each mode-specific loading state. Convert the
resulting WebM to H.264 MP4 with `ffmpeg`; the delivered file uses `yuv420p` and
`faststart` for broad playback compatibility.

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
