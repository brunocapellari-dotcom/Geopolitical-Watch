from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def dispatch_pending(store, *, webhook_url: str | None = None, bearer_token: str | None = None, timeout: int = 30, limit: int = 100) -> dict[str, int]:
    url = webhook_url or os.environ.get("GEOWATCH_WEBHOOK_URL")
    if not url:
        return {"pending": len(store.pending_alerts(limit=limit)), "delivered": 0, "failed": 0, "skipped": 1}
    token = bearer_token or os.environ.get("GEOWATCH_WEBHOOK_TOKEN")
    delivered = 0
    failed = 0
    rows = store.pending_alerts(limit=limit)
    for row in rows:
        alert_id = str(row["alert_id"])
        payload = row.get("payload") or {}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "GeopoliticalWatch/0.7"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            request = Request(url, data=data, headers=headers, method="POST")
            with urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
                if status < 200 or status >= 300:
                    raise RuntimeError(f"webhook returned HTTP {status}")
            store.mark_alert(alert_id, status="delivered", delivered_at=datetime.now(timezone.utc).isoformat())
            delivered += 1
        except (HTTPError, URLError, RuntimeError, TimeoutError) as exc:
            store.mark_alert(alert_id, status="pending", error=f"{type(exc).__name__}: {exc}")
            failed += 1
    return {"pending": len(rows), "delivered": delivered, "failed": failed, "skipped": 0}
