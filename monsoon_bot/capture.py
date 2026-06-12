"""Network-capture harness for reverse-engineering MonsoonSim's command API.

This is an **exploratory tool**, not part of the automation flow. It attaches to
your already-running, logged-in Chrome (same CDP connection the bot uses) and
records the AJAX / command requests the game fires while *you* drive it by hand.
The goal is to learn the request shapes (URLs, methods, form payloads) behind
buttons like ``cmd=BUY_FG`` so we can later decide whether replaying them
directly is worthwhile (see the "Better way #2" discussion / README).

Usage:
    python -m monsoon_bot.capture            # capture xhr/fetch + cmd= requests
    python -m monsoon_bot.capture --all      # capture everything on the domain
    python -m monsoon_bot.capture --out my_capture.jsonl

Then perform ONE action in the game (e.g. place a retail order), watch the lines
appear, and press Ctrl+C to stop. A per-command summary is printed on exit.

Notes:
  * ``Cookie`` / ``Authorization`` headers are redacted so captures are safe to
    share. Captures may still contain game-state data — review before posting.
  * This only observes traffic; it never sends anything.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import config
from .driver import connect_to_game

_REDACT_HEADERS = {"cookie", "authorization", "x-csrf-token"}
_MAX_BODY_CHARS = 4000


def _extract_cmd(url: str, post_data: str | None) -> str | None:
    """Best-effort pull of the ``cmd`` parameter from the URL or POST body."""
    for source in (urlparse(url).query, post_data or ""):
        values = parse_qs(source).get("cmd")
        if values:
            return values[0]
    return None


def _is_interesting(request, fragments: list[str], capture_all: bool) -> bool:
    url = request.url or ""
    if not any(fragment in url for fragment in fragments):
        return False
    if capture_all:
        return True
    if "cmd=" in url:
        return True
    return request.resource_type in ("xhr", "fetch")


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        k: ("<redacted>" if k.lower() in _REDACT_HEADERS else v)
        for k, v in headers.items()
    }


async def run_capture(settings: dict, out_path: Path, capture_all: bool,
                      include_body: bool) -> None:
    fragments = settings["site_fragments"]
    connection = await connect_to_game(settings)
    page = connection.page

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_file = out_path.open("w", encoding="utf-8")
    cmd_counter: Counter[str] = Counter()
    total = 0
    pending: set[asyncio.Task] = set()

    async def handle_finished(request) -> None:
        nonlocal total
        try:
            if not _is_interesting(request, fragments, capture_all):
                return
            cmd = _extract_cmd(request.url, request.post_data)

            entry: dict = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "cmd": cmd,
                "method": request.method,
                "url": request.url,
                "resource_type": request.resource_type,
                "post_data": request.post_data,
                "headers": _safe_headers(request.headers),
            }

            try:
                response = await request.response()
                if response is not None:
                    entry["status"] = response.status
                    if include_body and request.resource_type in ("xhr", "fetch"):
                        body = await response.text()
                        entry["response_body"] = body[:_MAX_BODY_CHARS]
            except Exception:
                pass  # response may be unavailable (cached, redirect, etc.)

            out_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            out_file.flush()
            total += 1
            cmd_counter[cmd or "(no cmd)"] += 1
            label = cmd or request.resource_type
            print(f"  [{total:>3}] {request.method:<4} {label:<18} {request.url[:90]}")
        except Exception as exc:  # never let a handler crash the capture
            print(f"  (capture error: {exc})")

    def on_finished(request) -> None:
        task = asyncio.create_task(handle_finished(request))
        pending.add(task)
        task.add_done_callback(pending.discard)

    page.on("requestfinished", on_finished)

    print("=" * 72)
    print("Capturing MonsoonSim traffic. Perform an action in the game now.")
    print(f"Writing to: {out_path}")
    print("Press Ctrl+C to stop.")
    print("=" * 72)

    try:
        await asyncio.Event().wait()  # run until interrupted
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        page.remove_listener("requestfinished", on_finished)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        out_file.close()
        await connection.close()

        print("\n" + "=" * 72)
        print(f"Captured {total} request(s) -> {out_path}")
        if cmd_counter:
            print("Commands seen:")
            for cmd, count in cmd_counter.most_common():
                print(f"  {count:>3}x  {cmd}")
        print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture MonsoonSim command traffic.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output .jsonl file (default: captures/<timestamp>.jsonl)")
    parser.add_argument("--all", action="store_true", dest="capture_all",
                        help="Capture all requests to the domain, not just xhr/fetch/cmd")
    parser.add_argument("--no-body", action="store_true",
                        help="Do not record response bodies")
    args = parser.parse_args()

    out_path = args.out or (
        Path("captures") / f"monsoon_capture_{datetime.now():%Y%m%d_%H%M%S}.jsonl")

    settings = config.load_settings()
    try:
        asyncio.run(run_capture(settings, out_path, args.capture_all, not args.no_body))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
