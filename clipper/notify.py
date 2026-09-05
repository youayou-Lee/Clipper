"""Webhook notification: POST findings as JSON. Standard library only."""

import datetime
import json
import urllib.request


def build_payload(findings, original_text) -> dict:
    return {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "findings": [
            {
                "chain": f.chain,
                "kind": f.kind,
                "confidence": f.confidence,
                "address": f.address,
            }
            for f in findings
        ],
        "original_text": original_text,
    }


def send_webhook(url, payload, timeout=3) -> bool:
    """POST payload as JSON. True on 2xx; any failure returns False (never raises)."""
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False
