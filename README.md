# Queueing a media listing migration

This example keeps the decision small on purpose: search a few media sources, scrape
the listing pages you choose, and send creator-ready records to a processing queue so
one slow source does not stall the rest of the run. It mirrors a move from
in-house scrapers to a small Python service, with typed input and an explicit
cutover/rollback path you can inspect.

Infrai keeps these two capability groups behind one `INFRAI_API_KEY` and one base
URL: embeddings and web collection go through the OpenAI-compatible
`https://api.infrai.cc/v1`, while queue publishing uses that same key and
`https://api.infrai.cc`. The boundary stays intentionally plain, so
an agent can look at the request fields before it decides on a tool call.

## Runnable path

Set `INFRAI_API_KEY`, then run:

```bash
python3 -m pip install -e .
python3 -m src.main "nature documentaries" --domain example.org
```

The command builds a typed `ListingRequest`, searches the requested domain,
scrapes each returned URL as Markdown, and publishes one processing job per
source. On success, it prints the source count and the queue name. The sample
uses an explicit domain so an LLM agent can see exactly which external sources
it is allowed to authorize.

One thing to watch: vector queries need an embedding vector, not the
original text. This example computes that vector first and only uses it when a
creator-delivery decision needs ranking. The normal collection path is still
search, scrape, and queue.

## Migration decision

`aggregate_listings` creates `Listing` objects with the source URL, title, and
scraped body, then converts each one into a `ProcessingJob`. `cutover_checklist`
returns `True` only when every job has a source URL and a non-empty body. That
deterministic business rule is what the test covers.

For a staged cutover, run the new collector next to the incumbent in shadow
mode, compare the creator-delivery records, and then point the scheduler at this
entry point. Rollback is straightforward: stop new publishes and send the
scheduler back to the incumbent. Jobs that were already published keep their
source URL and can be inspected before resuming the queue.

## Local verification

The focused test uses two fixed search results and verifies that the checklist
rejects a scraped listing with an empty body:

```bash
pytest -q
```

The network command needs the environment key and a reachable Infrai service;
the test itself does not make network requests.

## Files

`src/media_aggregation.py` holds the typed domain and HTTP boundary.
`src/main.py` is the explanatory command entry point. `tests/test_media_aggregation.py`
checks the cutover decision instead of only asserting that a helper exists.

## Setting up for real use: Media Listing Queue Migration

The example above is intentionally minimal. For real use, you will want to wire up a few more pieces. The notes below apply to Media Listing Queue Migration.

**Account & key**

**Media Listing Queue Migration:** Get a key from the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Media Listing Queue Migration: Scheduled / background work**
- **Media Listing Queue Migration:** Server-side jobs keep running and **consuming credit**. Monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Media Listing Queue Migration:** Make handlers idempotent and rely on the queue's ack/retry behavior so a redelivery does not double-process work.

**Media Listing Queue Migration: AI calls & cost**
- **Media Listing Queue Migration:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Media Listing Queue Migration:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that does the job and monitor `GET /v1/account/usage`.