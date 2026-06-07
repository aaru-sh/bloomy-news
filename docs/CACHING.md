# Dashboard Caching Strategy

## Overview

The dashboard server (`dashboard/serve.py`) uses HTTP caching and compression to
reduce bandwidth and latency for API responses that only change between pipeline runs.

## What's Cached and Why

| Endpoint | Cache-Control | ETag | Why |
|---|---|---|---|
| `/api/articles` | `public, max-age=10` | Yes | Content changes only on pipeline run (~4.66 MB JSON) |
| `/api/stats` | `public, max-age=10` | Yes | Derived from articles data, changes on pipeline run |
| `/api/bookmarks` | `public, max-age=0` | Yes | Changes via user POST requests (toggle), needs fresh data |
| `/api/bookmarks/toggle` | `public, max-age=0` | Yes | POST response with updated state |
| Static files (HTML/JS/CSS) | `no-store, must-revalidate` | No | Must always reflect latest pipeline output |

**Key design decision:** `/api/bookmarks` uses `max-age=0` because bookmark
state changes immediately when users toggle via POST. A stale cache would show
incorrect starred state.

## ETag Mechanism

Every JSON API response includes an `ETag` header computed from the response body:

```
ETag: "a1b2c3d4e5f67890"
```

The ETag is a SHA-256 hash (truncated to 16 hex chars) of the serialized JSON.
This means:
- Same content always produces the same ETag regardless of server restart
- Different content (even by one character) produces a different ETag
- The ETag is derived from the data, not timestamps

### Conditional Requests

When the browser has a cached response with an ETag, it sends:

```
If-None-Match: "a1b2c3d4e5f67890"
```

If the ETag matches the current response, the server returns **304 Not Modified**
with no body. This saves:
- ~4.66 MB of transfer for `/api/articles` on each unchanged request
- Server CPU for JSON serialization of the response body (though the file is
  still read and serialized — the savings are in network transfer)

The 304 response still includes `Cache-Control` and `ETag` headers so the browser
can continue using its cached copy and revalidate on the next request.

## Gzip Compression

Responses larger than 1 KB are gzip-compressed when the client sends
`Accept-Encoding: gzip` (all modern browsers do by default).

### Compression ratios

| Endpoint | Uncompressed | Compressed | Savings |
|---|---|---|---|
| `/api/articles` | ~4.66 MB | ~500 KB | ~89% |
| `/api/stats` | ~1 KB | ~0.3 KB | ~70% |
| `/api/bookmarks` | variable | variable | ~85% typical |

Compression is applied server-side on each request. The compressed response
includes `Content-Encoding: gzip` so browsers decompress transparently.

## Browser Behavior

### First load (cold cache)

1. Browser requests `/api/articles` — no `If-None-Match` header
2. Server returns **200 OK** with ETag, gzip body, and `Cache-Control: public, max-age=10`
3. Browser caches the response for 10 seconds

### Subsequent load (within max-age)

1. Browser uses cached copy directly — no network request
2. Dashboard loads instantly from local cache

### Revalidation (after max-age expires)

1. Browser sends request with `If-None-Match: "<etag>"`
2. If content unchanged: **304 Not Modified** (no body transfer)
3. If content changed (pipeline ran): **200 OK** with new ETag and body

### Pipeline run (content changes)

1. Pipeline generates new `dashboard_data.json`
2. ETags for `/api/articles` and `/api/stats` change automatically (computed from body)
3. Browser's `If-None-Match` won't match → full 200 response with new data
4. Next 10-second window uses new ETag for 304 responses

## Cache Invalidation

Cache invalidation is automatic — no manual steps needed:

1. **Pipeline runs** → writes new `dashboard_data.json` → ETags change → browser gets fresh data
2. **Bookmark toggle** → writes new `bookmarks.json` → ETag changes → response reflects new state
3. **Static files** → `no-store` header forces browser to re-fetch HTML/JS/CSS every time

The `max-age=10` on articles/stats means the browser checks at most once every
10 seconds. Between pipeline runs (typically hours), this means:
- First 10 seconds after page load: uses cache (no network)
- After 10 seconds: sends conditional request, gets 304 if no pipeline ran
- After pipeline runs: gets 200 with new data on next revalidation

## Configuration

To adjust the cache duration, change the `cache_max_age` parameter in `do_GET`:

```python
# Increase to 60 seconds for less frequent revalidation
self._send_json(load_data(), cache_max_age=60)

# Set to 0 to disable caching entirely
self._send_json(load_data(), cache_max_age=0)
```

To disable compression for specific endpoints, add a size check or remove the
gzip logic from `_send_json`.

## Files Modified

- `dashboard/serve.py` — Added ETag headers and gzip compression to `_send_json`
- `docs/CACHING.md` — This documentation
