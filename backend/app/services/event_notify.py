"""Best-effort HTTP bridge so CLI tasks can notify the running API SSE bus."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def notify_api(event: str, **data: Any) -> bool:
    """
    POST to ``/api/events/notify`` on the local API if configured.

    Env:
      EVENTS_NOTIFY_URL — default http://127.0.0.1:8000/api/events/notify
      EVENTS_NOTIFY — set to 0 to disable
    """
    if os.environ.get("EVENTS_NOTIFY", "1").strip() == "0":
        return False

    url = (
        os.environ.get("EVENTS_NOTIFY_URL", "").strip()
        or "http://127.0.0.1:8000/api/events/notify"
    )
    payload = json.dumps({"event": event, "data": data}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
