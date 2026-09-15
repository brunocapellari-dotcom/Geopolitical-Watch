# Security CI exceptions

The production CI intentionally keeps Bandit at medium/high severity and fails on new findings. Two rule families are excluded after manual review:

- **B104 (bind all interfaces):** the published service must listen on the platform-facing interface. The private production entry point defaults to loopback in code and only the deployment manifest supplies `HOST=0.0.0.0`. The remaining hard-coded bind is in the legacy direct API entry point, which is not the `geowatch serve` production path.
- **B608 (SQL expression construction):** the flagged statements compose only fixed SQL fragments and placeholder counts selected by application code. All user/data values continue to be passed through database parameter binding. No table name, column name, operator, ordering expression, or raw value is taken from a request and interpolated into SQL.

These are narrow reviewed exceptions, not a blanket approval for dynamic SQL or unrestricted network binding. New Bandit findings outside B104/B608 fail CI. Outbound URL calls are separately restricted to HTTP(S), published webhook delivery is HTTPS-only, untrusted sanctions XML uses `defusedxml`, and production startup is fail-closed when authentication or persistent storage is absent.
