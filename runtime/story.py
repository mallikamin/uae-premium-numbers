#!/usr/bin/env python3
"""FB + IG Story posting for the uae-premium-numbers poster.

Mirrors the proven postpaidplans/goldennummbers story flow:
  - FB Page Story: upload the vertical card with published=false, then
    promote it via {page_id}/photo_stories (direct file upload).
  - IG Story: create a STORIES container from a CDN image_url, poll until
    FINISHED, then media_publish.

Both are best-effort: they return (ok, info) and never raise, so a story
failure can be logged/alerted without rolling back the feed post.
"""
from __future__ import annotations
import time
import requests


def _graph(cfg) -> str:
    return f"https://graph.facebook.com/{cfg.get('graph_version', 'v21.0')}"


def post_fb_story(cfg, image_path: str) -> tuple[bool, str]:
    """Publish a vertical card as a FB Page Story (2-step photo_stories API)."""
    GRAPH = _graph(cfg)
    try:
        with open(image_path, "rb") as fh:
            up = requests.post(
                f"{GRAPH}/{cfg['fb_page_id']}/photos",
                data={"published": "false", "access_token": cfg["fb_page_token"]},
                files={"source": fh}, timeout=90,
            )
        if up.status_code not in (200, 201):
            return False, f"photo upload HTTP {up.status_code}: {up.text[:160]}"
        photo_id = up.json().get("id")
        if not photo_id:
            return False, "photo upload returned no id"
        pub = requests.post(
            f"{GRAPH}/{cfg['fb_page_id']}/photo_stories",
            data={"photo_id": photo_id, "access_token": cfg["fb_page_token"]},
            timeout=60,
        )
        if pub.status_code in (200, 201) and pub.json().get("success", True):
            return True, str(pub.json().get("post_id") or pub.json().get("id") or "ok")
        return False, f"photo_stories HTTP {pub.status_code}: {pub.text[:200]}"
    except requests.RequestException as e:
        return False, f"fb story error: {e}"


def post_ig_story(cfg, image_url: str, max_wait_polls: int = 12) -> tuple[bool, str]:
    """Publish a vertical card as an IG Story (media_type=STORIES, by URL)."""
    ig = cfg.get("ig_user_id")
    if not ig:
        return False, "no ig_user_id"
    GRAPH = _graph(cfg)
    try:
        c = requests.post(
            f"{GRAPH}/{ig}/media",
            data={"media_type": "STORIES", "image_url": image_url,
                  "access_token": cfg["fb_page_token"]},
            timeout=30,
        )
        if c.status_code not in (200, 201):
            return False, f"container HTTP {c.status_code}: {c.text[:160]}"
        cid = c.json().get("id")
        if not cid:
            return False, "container returned no id"
        for _ in range(max_wait_polls):
            time.sleep(5)
            s = requests.get(
                f"{GRAPH}/{cid}",
                params={"fields": "status_code", "access_token": cfg["fb_page_token"]},
                timeout=15,
            )
            sc = s.json().get("status_code")
            if sc == "FINISHED":
                break
            if sc == "ERROR":
                return False, f"processing ERROR: {s.text[:160]}"
        pub = requests.post(
            f"{GRAPH}/{ig}/media_publish",
            data={"creation_id": cid, "access_token": cfg["fb_page_token"]},
            timeout=30,
        )
        if pub.status_code in (200, 201):
            return True, str(pub.json().get("id"))
        return False, f"publish HTTP {pub.status_code}: {pub.text[:200]}"
    except requests.RequestException as e:
        return False, f"ig story error: {e}"
