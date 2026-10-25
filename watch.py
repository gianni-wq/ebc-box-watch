#!/usr/bin/env python3
"""Check the box from outside, and tell Gianni on Telegram when it stops answering.

GitHub runs this every 5 minutes (.github/workflows/watch.yml). Each address below is a public
health page served by the box through one of its two Cloudflare tunnels. An address that fails
on two runs in a row is down; the first time any address is down, one message goes out, and one
more when every address answers again. What it has seen is kept in state.json, which the workflow
commits back only when it changes.

This repo is public, so its logs are too: it prints names and status codes, never the bot key,
the chat id or anything Telegram answers.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
ET = ZoneInfo("America/New_York")

#: name -> (address, what its body starts with when it is well). All three are pages the box
#: serves to anyone; ops and order-files ride its main tunnel, preferences its second one.
CHECKS = {
    "ops": ("https://ops.educationalnote.com/healthz", "ok"),
    "order-files": ("https://order-files.educationalnote.com/healthz", "ok"),
    "preferences": ("https://preferences.educationalnote.com/healthz", "ok"),
}
#: The words a message uses for each name.
LABELS = {"ops": "EBC Ops", "order-files": "order files", "preferences": "email preferences"}
DOWN_AFTER = 2          # failed runs in a row before an address counts as down
KEEPALIVE_DAYS = 25     # GitHub turns a public repo's schedule off after 60 days with no commit
TIMEOUT = 20
#: Cloudflare's Browser Integrity Check refuses Python's own user agent (error 1010).
UA = "ebc-box-watch/1 (+https://github.com/gianni-wq/ebc-box-watch)"


def check(url: str, expect: str) -> str:
    """'ok', or a short reason it is not: an HTTP code or the kind of network failure."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(200).decode("utf-8", "replace")
            return "ok" if r.status == 200 and body.startswith(expect) else f"{r.status} unexpected body"
    except urllib.error.HTTPError as e:
        return str(e.code)
    except Exception as e:  # timeouts, DNS, refused: all mean the page did not answer
        return type(e).__name__


def send(text: str) -> bool:
    token, chat = os.environ.get("ALERT_BOT_TOKEN", ""), os.environ.get("ALERT_CHAT_ID", "")
    if not token or not chat:
        print("alert NOT sent: the bot key or chat id is missing")
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data,
                                    timeout=TIMEOUT) as r:
            ok = r.status == 200
    except urllib.error.HTTPError as e:
        print(f"alert NOT sent: Telegram answered {e.code}")
        return False
    except Exception as e:
        print(f"alert NOT sent: {type(e).__name__}")
        return False
    print("alert sent" if ok else "alert NOT sent")
    return ok


def _et(iso: str) -> str:
    t = dt.datetime.fromisoformat(iso).astimezone(ET)
    return t.strftime("%-I:%M %p ET, %a %b %-d")


def _names(names: list[str]) -> str:
    words = [LABELS.get(n, n) for n in names]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def step(state: dict, results: dict, now: dt.datetime) -> tuple[dict, str | None]:
    """The new state and the message to send (or None), from the last state and this run."""
    fails = dict(state.get("fails") or {})
    for name, result in results.items():
        fails[name] = 0 if result == "ok" else int(fails.get(name, 0)) + 1
    down = sorted(n for n, f in fails.items() if n in results and f >= DOWN_AFTER)
    new = dict(state, fails=fails)
    msg = None
    if down and not state.get("alerted"):
        new["alerted"], new["down_since"] = True, now.isoformat(timespec="seconds")
        if len(down) == len(results):
            what = "Nothing on the box answers from outside: the box, its tunnels or the shop's internet is down."
        else:
            what = f"Not answering from outside: {_names(down)}. The rest of the box answers."
        msg = f"EBC box: {what} Seen at {_et(new['down_since'])}, checked by GitHub."
    elif not down and state.get("alerted"):
        since = dt.datetime.fromisoformat(state["down_since"])
        mins = max(1, round((now - since).total_seconds() / 60))
        new["alerted"], new["down_since"] = False, None
        msg = f"EBC box: answering again at {_et(now.isoformat())}. It was out about {mins} minutes."
    last = state.get("keepalive") or "2000-01-01"
    if (now.date() - dt.date.fromisoformat(last)).days >= KEEPALIVE_DAYS:
        new["keepalive"] = now.date().isoformat()
    return new, msg


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    if os.environ.get("TEST_MESSAGE") == "true":
        ok = send(f"EBC box watcher: test message at {_et(now.isoformat())}. "
                  "If you can read this, GitHub can reach you when the box stops answering.")
        return 0 if ok else 1
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    results = {name: check(url, expect) for name, (url, expect) in CHECKS.items()}
    for name, result in results.items():
        print(f"{name}: {result}")
    new, msg = step(state, results, now)
    if msg:
        if not send(msg):
            return 1  # the state is not saved, so the next run tries the message again
    if new != state:
        STATE.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
