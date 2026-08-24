# Current source facts — 2026-08-24

These implementation assumptions were revalidated on 2026-08-24 and should be rechecked before production deployment.

## UCDP API

- Free of charge.
- Authenticated access uses `x-ucdp-access-token`.
- Version must be specified for reproducible calls.
- Latest annual GED version observed during validation: 26.1.
- Candidate releases exist separately from the annual release.

Reference: https://ucdp.uu.se/apidocs/

## ReliefWeb API

- Current API version: V2.
- `appname` is mandatory and, from 2025-11-01, must be pre-approved.
- Maximum entries per call: 1000.
- Maximum calls per day: 1000, subject to provider review.
- Content may include copyrighted material from information partners; respect original rights.

Reference: https://apidoc.reliefweb.int/

## NASA FIRMS

- API/map services require a free MAP_KEY.
- Published transaction limit observed during validation: 5000 transactions per 10-minute interval.
- Thermal anomalies are contextual sensor detections, not standalone evidence of military attacks.

Reference: https://firms.modaps.eosdis.nasa.gov/api/map_key/
