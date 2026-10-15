"""Send a human-approved advisory to a farmer's phone by SMS.

Only an advisory an officer has APPROVED (challenge_agent review step) can be
sent. The message is either the approved text itself, if it is short enough,
or a short text the officer types; either way the exact words sent are recorded
in the tamper-evident audit log with the advisory's digest. The farmer's number
is not stored in full: the audit keeps a salted hash and the last 3 digits.

Gateway: the open-source "SMS Gateway for Android" app (capcom6/android-sms-gateway,
Apache-2.0) running on an ordinary Android phone with a local SIM, in its
"Local Server" mode, on the same Wi-Fi as this computer. Its documented call is

    POST http://<phone-ip>:8080/message   (HTTP basic auth from the app)
    {"textMessage": {"text": "..."}, "phoneNumbers": ["+263..."]}

Set MURIMIFARA_SMS_URL (e.g. http://192.168.1.20:8080), MURIMIFARA_SMS_USER and
MURIMIFARA_SMS_PASS. Without them the command does a dry run and sends nothing.

Usage:
    python -m murimi_plus.sms send <advisory-id> --to +2637XXXXXXXX [--text "..."] [--db ...]

Receiving farmers' questions by SMS is NOT automated here: the officer types or
pastes the question into the review page, so a person sees every message.
"""
import argparse
import getpass
import hashlib
import json
import os
import re
import sys

import httpx

try:
    from challenge_agent.store import Store
except ImportError as exc:  # pragma: no cover
    raise ImportError("SMS sending needs the challenge_agent folder (the officer approval step) "
                      "in the same folder as app.py") from exc

MAX_CHARS = 459              # 3 GSM-7 SMS parts of 153 characters
PHONE = re.compile(r"^\+263\d{9}$")
SIGN_OFF = "Murimi Fara - checked by {who}."


def plain(text):
    """Markdown answer -> plain SMS text."""
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^\s*[-*]\s+", "- ", text, flags=re.M)
    return re.sub(r"\n{2,}", "\n", text).strip()


def normalise_phone(number):
    digits = re.sub(r"[\s\-()]", "", number or "")
    if digits.startswith("0") and len(digits) == 10:
        digits = "+263" + digits[1:]
    if not PHONE.match(digits):
        raise ValueError("Phone must be a Zimbabwe number, e.g. +263771234567 or 0771234567")
    return digits


def phone_ref(number, salt):
    return {"phone_hash": hashlib.sha256((salt + number).encode()).hexdigest()[:16],
            "phone_last3": number[-3:]}


def build_message(advisory, officer_text=""):
    """The exact SMS body for an approved advisory, or ValueError."""
    if advisory["state"] != "approved":
        raise ValueError("Only an officer-approved advisory can be sent")
    who = (advisory.get("reviewer") or "officer").split(" (")[0]
    doc = advisory["document"]
    body = plain(officer_text) if officer_text.strip() else plain(doc.get("text", ""))
    if doc.get("urgent") and not body.upper().startswith("URGENT"):
        body = "URGENT: " + body
    message = f"{body}\n{SIGN_OFF.format(who=who)}"
    if len(message) > MAX_CHARS:
        raise ValueError(f"Message is {len(message)} characters; the limit is {MAX_CHARS} (3 SMS). "
                         "Write a short version with --text; it will be sent and recorded exactly as typed.")
    return message


def gateway_from_env():
    url = os.environ.get("MURIMIFARA_SMS_URL", "").rstrip("/")
    if not url:
        return None
    return {"url": url, "user": os.environ.get("MURIMIFARA_SMS_USER", ""),
            "password": os.environ.get("MURIMIFARA_SMS_PASS", "")}


def send(store, advisory_id, to, officer_text="", gateway=None, actor=None, client=None):
    """Export (idempotent), then send once per advisory+number. Returns a result dict."""
    advisory = store.get(advisory_id)
    number = normalise_phone(to)
    message = build_message(advisory, officer_text)
    actor = actor or getpass.getuser()
    ref = phone_ref(number, advisory["digest"])
    already = [e for e in store.audit() if e["event"] == "sms_sent"
               and e["payload"].get("id") == advisory_id and e["payload"].get("phone_hash") == ref["phone_hash"]]
    if already:
        raise ValueError("This advisory was already sent to this number")
    store.export(advisory_id, actor)
    if gateway is None:
        return {"dry_run": True, "to": number, "message": message,
                "note": "Set MURIMIFARA_SMS_URL / _USER / _PASS to send for real."}
    client = client or httpx.Client(timeout=30)
    response = client.post(f"{gateway['url']}/message", auth=(gateway["user"], gateway["password"]),
                           json={"textMessage": {"text": message}, "phoneNumbers": [number]})
    if response.status_code >= 300:
        store.log("sms_failed", actor, {"id": advisory_id, "digest": advisory["digest"], **ref,
                                        "status": response.status_code})
        raise ValueError(f"SMS gateway refused the message (HTTP {response.status_code})")
    try:
        gateway_id = str(response.json().get("id", ""))
    except ValueError:
        gateway_id = ""
    store.log("sms_sent", actor, {"id": advisory_id, "digest": advisory["digest"], **ref,
                                  "text_sha256": hashlib.sha256(message.encode()).hexdigest(),
                                  "text": message, "gateway_id": gateway_id})
    return {"dry_run": False, "to": number, "message": message, "gateway_id": gateway_id}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Send an approved advisory by SMS")
    parser.add_argument("--db", default=os.path.join(".challenge-data", "agent.sqlite3"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("send")
    p.add_argument("id")
    p.add_argument("--to", required=True)
    p.add_argument("--text", default="", help="Short officer-written SMS (sent exactly as typed)")
    args = parser.parse_args(argv)
    store = Store(args.db)
    try:
        advisory = store.get(args.id)
        message = build_message(advisory, args.text)
        number = normalise_phone(args.to)
        print(f"To: {number}\n---\n{message}\n---")
        gateway = gateway_from_env()
        if gateway and sys.stdin.isatty():
            if input("Type SEND to send this SMS: ") != "SEND":
                print("Not sent.")
                return 1
        elif gateway:
            raise ValueError("Sending needs an interactive terminal (a person confirms each SMS)")
        result = send(store, args.id, number, args.text, gateway)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())