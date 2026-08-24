# Current source facts — 2026-08-24

These implementation assumptions were revalidated on 2026-08-24 and should be rechecked before production deployment.

## GDELT DOC 2.0

- Supports explicit `STARTDATETIME` and `ENDDATETIME` query controls in `YYYYMMDDHHMMSS` format.
- Historical replay uses bounded windows rather than only a rolling timespan.
- Dense windows can hit result limits and require narrower/query-partitioned requests.

References:
- https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- https://blog.gdeltproject.org/gdelt-doc-2-0-api-expanded-searching-of-the-internet-archive/

## UCDP API

- Free of charge.
- Authenticated access uses `x-ucdp-access-token`.
- Version is explicit for reproducible calls.
- Annual GED version observed during validation: 26.1.
- Pagination is required for larger queries.
- Date-filter semantics must be preserved as documented rather than reinterpreted generically.

Reference: https://ucdp.uu.se/apidocs/

## ReliefWeb API

- Current API version: V2.
- `appname` is mandatory and, from 2025-11-01, must be pre-approved.
- Maximum entries per call: 1000.
- Standard quota observed: 1000 calls/day, subject to provider review.
- Information-partner rights must be preserved; full copyrighted bodies are not copied into Geopolitical Watch reports.

Reference: https://apidoc.reliefweb.int/

## NASA FIRMS

- API/map services require a free MAP_KEY.
- Area API supports historical date and 1-5 day windows.
- Published transaction limit observed during validation: 5000 transactions per 10-minute interval.
- Thermal anomalies are contextual sensor detections, not attack attribution.
- Operational pulls should prefer bounded geographic regions instead of repeated global history pulls.

References:
- https://firms.modaps.eosdis.nasa.gov/api/area/
- https://firms.modaps.eosdis.nasa.gov/api/map_key/

## GDACS

- GDACS exposes an official API/Swagger surface with event-list and event-detail endpoints, including latest/current event-list access and geographic/event metadata.
- Geopolitical Watch uses GDACS as an institutional disaster/context signal.
- A GDACS alert is not interpreted as evidence that a military attack occurred.

References:
- https://www.gdacs.org/gdacsapi/
- https://www.gdacs.org/Documents/2025/GDACS_API_quickstart_v1.pdf

## ACLED

- Programmatic API access requires a myACLED account and OAuth authentication.
- The access token is sent using `Authorization: Bearer ...`.
- The data API supports event queries and date filters.
- Cursor pagination is supported and is the durable automation choice; `next_cursor = null` ends traversal.
- Page-based pagination is scheduled for deprecation for most endpoints from 2026-10-01, making cursor pagination the forward-compatible implementation.
- ACLED remains disabled in default configuration until credentials and applicable usage/licensing terms are reviewed.

References:
- https://acleddata.com/api-documentation/getting-started
- https://acleddata.com/api-documentation/api-reference
- https://acleddata.com/api-documentation/pagination
