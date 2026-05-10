#!/usr/bin/env python3
"""Notification helper for the Meta poster (uae-premium-numbers brand).

Uses msmtp (already configured on loom-edge at ~/.msmtprc) to send email
to the uae-premium-numbers ops list. Mirrors goldennummbers/runtime/notify.py
so the operational pattern stays identical across both brands.
"""
from __future__ import annotations
import subprocess

RECIPIENTS = [
    "mallikamiin@gmail.com",
    "amin@sitaratech.info",
    "bilalkhaliddxb@gmail.com",
]
FROM_HEADER = "uae-premium-numbers Poster <mallikamiin@gmail.com>"


def send_email(subject: str, body: str, recipients: list[str] | None = None) -> tuple[bool, str]:
    to = recipients or RECIPIENTS
    msg = "\n".join([
        f"From: {FROM_HEADER}",
        f"To: {', '.join(to)}",
        f"Subject: {subject}",
        "Content-Type: text/plain; charset=UTF-8",
        "",
        body,
    ])
    try:
        p = subprocess.run(
            ["/usr/bin/msmtp", "-t"],
            input=msg, text=True, timeout=30, capture_output=True
        )
        if p.returncode == 0:
            return True, ""
        return False, (p.stderr or "").strip()
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    import sys
    subj = sys.argv[1] if len(sys.argv) > 1 else "[uaepremiumnumbers] test email"
    body = sys.argv[2] if len(sys.argv) > 2 else "This is a test from notify.py."
    ok, err = send_email(subj, body)
    print(f"sent={ok} err={err}")
