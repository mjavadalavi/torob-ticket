# Torob Ticket shared contract

`openapi.yaml` is the source of truth for the FastAPI wire contract. The same
models are available as TypeScript types in [`travel.ts`](./travel.ts) for the
Next.js client. Keep both files aligned with
`backend/app/domain/` and FastAPI's generated OpenAPI when adding a transport
mode, capability, or OTA adapter.

## Search flow

1. `POST /api/v1/search-jobs` with one `mode` (`flight`, `train`, or `bus`),
   route, date, passenger counts, and ranking `intent`. The API responds with
   HTTP 202, `{ "search_id": "...", "status": "queued" }`, an absolute
   `Location` URL, and `Retry-After: 1`.
   Omit `return_date` (or send `null`) for a one-way search. For a round trip,
   send a return date later than `departure_date`. The orchestrator keeps OTA
   adapters one-way and executes the reversed return leg under the same job.
   `preferences.mode` must equal the top-level `mode`. Train and bus requests
   currently accept adults only because minor pricing has not been verified
   with those providers.
2. Poll `GET /api/v1/search-jobs/{search_id}` after the suggested delay. A
   `queued` or `running` job has `result: null` and `error: null`; a `completed`
   job has a normalized `SearchResponse` in `result`; a `failed` job has only a
   sanitized `{ code, message, retryable }` error. All four persisted states use
   HTTP 200. Missing or expired jobs return 404. Job admission returns 503 when
   the bounded queue is full or the service is closing.
3. Render each `result.offers[]` item as one outbound journey.
   `seller_offers[]` contains the comparable OTA prices for that journey; the
   API has already normalized and grouped provider responses. When
   `result.return_leg` is present, render its independently ranked `offers[]` as
   the reversed return journey. Provider counts and failures are reported per
   leg; offer and seller-offer IDs are unique across both legs.
4. Use `recommended_price`, `recommended_capabilities`, and
   `recommended_seller_offer_id` together when rendering the ranked card. Use
   the group-level `lowest_price` and `available_capabilities` only as aggregate
   comparison/filter data; never attach one seller's capability to another
   seller's price. Map `torob_guarantee` to «تضمین ترب» and `torob_pay` to
   «ترب‌پی».
5. Call `GET /api/v1/offers/{offer_id}/redirect?seller_offer_id=...` before
   leaving the comparison page. Check `target_kind` and
   `price_recheck_required`, show the external-checkout notice, and then open
   the returned URL. Current adapters return a seller search page rather than
   an exact proposal deep link. Passenger information and payment stay on the
   OTA. The endpoint returns `503 adapter_unavailable` when the adapter is not
   active or its redirect fails the verified HTTPS/provider-host checks.

`POST /api/v1/search` remains available for compatibility with synchronous
clients. It accepts the identical `SearchRequest` and returns `SearchResponse`
directly, but interactive clients should use search jobs so the UI can show
mode-aware progress while OTA adapters run.

Optional provider-backed data is resolved per seller offer. `/details` and
`/refund-rules` describe the short-lived live-search snapshot stored for that
seller; they do not promise a fresh repricing request. Use `/refund-rules` only
when `refund_rules` is advertised and `/seat-map` only when `seat_selection` is
advertised. Unsupported capabilities
return the structured `503 adapter_unavailable` error instead of guessed data.
Provider source tokens remain internal adapter state and are never part of the
public response contract; clients identify a seller result only by its public
`seller_offers[].id` value.

Provider failures are non-fatal when at least one adapter succeeds. Display a
small completeness notice from `provider_failures`; do not discard successful
offers.

`GET /api/v1/providers?mode=flight|train|bus` lists every OTA/mode pair from
the audited product scope. `registered` means a live adapter exists; the other
statuses explain why a provider is not queried. This endpoint describes
integration eligibility, not real-time uptime. Continue to use each search
response's `provider_failures` for current provider availability.

## Mode-specific details

`mode_details` is a discriminated union. Use its `mode` field to select the
correct view without branching the core result card:

- `flight`: airports, airline/flight number, fare type, cabin, and baggage.
- `train`: railway company, compartment type/capacity, women-only/private
  compartment, and vehicle transport.
- `bus`: city terminals, company/service, bus class/capacity, seat selection,
  and cancellation policy.

Shared fields (`attributes`, `price`, `seller`, `capabilities`, timestamps) are
intentionally identical across modes. A future adapter should implement the
`TravelAdapter` port and return provider-neutral offers; orchestration, grouping,
ranking, and the UI card do not need to change.

## Local development

From the repository root:

```sh
cp .env.example .env
docker compose up --build
```

The API is available at `http://localhost:8000` and the RTL web app at
`http://localhost:3000`. The server-only `API_URL` should include `/api/v1`;
browser calls stay same-origin through the allowlisted Next.js proxy.

Request examples remain in `fixtures/`. Response fixtures are intentionally not
shipped: product code and contract tests must never fall back to fabricated fares.

Validate the static API description, runtime parity gates, and standalone
TypeScript contract with:

```sh
npx @redocly/cli lint contracts/openapi.yaml --config contracts/redocly.yaml
backend/.venv/bin/pytest -q tests/backend/test_architecture.py tests/backend/test_search_api.py
frontend/node_modules/.bin/tsc --noEmit --target ES2022 --module ESNext --moduleResolution Bundler --skipLibCheck contracts/travel.ts
```
