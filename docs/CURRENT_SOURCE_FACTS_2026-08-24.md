# Current source facts — 2026-08-24

These implementation assumptions were revalidated on 2026-08-24 and should be rechecked before production deployment.

## GDELT DOC 2.0

- Supports explicit `STARTDATETIME` and `ENDDATETIME` query controls in `YYYYMMDDHHMMSS` format.
- Geopolitical Watch uses explicit bounded windows for historical replay instead of relying only on a rolling `timespan`.
- DOC API result limits mean a dense time window can still truncate coverage; backfill therefore must use bounded windows and, when needed, narrower time/query partitions.

References:
- https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- https://blog.gdeltproject.org/gdelt-doc-2-0-api-expanded-searching-of-the-internet-archive/

## UCDP API

- Free of charge.
- Authenticated access uses `x-ucdp-access-token`.
- Version must be specified for reproducible calls.
- Latest annual GED version observed during validation: 26.1.
- Candidate releases exist separately from the annual release.
- Pagination is required for larger queries.
- GED `StartDate`/`EndDate` filters follow the API's documented date-filter semantics; current documentation ties these filters to `date_end`, so consumers must not reinterpret them as a generic event-start window.

Reference: https://ucdp.uu.se/apidocs/

## ReliefWeb API

- Current API version: V2.
- `appname` is mandatory and, from 2025-11-01, must be pre-approved.
- Maximum entries per call: 1000.
- Maximum calls per day: 1000, subject to provider review.
- Content may include copyrighted material from information partners; respect original rights.
- v0.4 does not automate ReliefWeb historical backfill.

Reference: https://apidoc.reliefweb.int/

## NASA FIRMS

- API/map services require a free MAP_KEY.
- Area API supports an optional historical date and a day range from 1 to 5 days.
- Published transaction limit observed during validation: 5000 transactions per 10-minute interval.
- Thermal anomalies are contextual sensor detections, not standalone evidence of military attacks.
- World-scale historical pulls can be large; operational use should prefer bounded regions where possible.

References:
- https://firms.modaps.eosdis.nasa.gov/api/area/
- https://firms.modaps.eosdis.nasa.gov/api/map_key/
