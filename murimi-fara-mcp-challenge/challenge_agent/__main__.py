"""Trusted local operator interface. Review/export are never offered to agents."""
import argparse
import asyncio
import getpass
import json
from pathlib import Path
import sys

from .orchestrator import draft
from .store import Store


def error_messages(exc):
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(error_messages(child) for child in exc.exceptions)
    return str(exc)


def main():
    parser = argparse.ArgumentParser(description="New challenge agent; existing Murimi Fara is unchanged")
    parser.add_argument("--db", default=str(Path(".challenge-data") / "agent.sqlite3"))
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("draft")
    build.add_argument("--query", required=True)
    build.add_argument("--region", default="")
    build.add_argument("--model-url", help="Existing local llama-server /completion endpoint")
    build.add_argument("--online", action="store_true", help="Consult third-party Fetch MCP")
    build.add_argument("--require-external", action="store_true", help="Fail if third-party MCP is unavailable")
    for command in ("show", "review", "export"):
        p = sub.add_parser(command)
        p.add_argument("id")
        if command == "review":
            p.add_argument("--digest", required=True, help="Exact digest from the displayed draft")
            p.add_argument("--decision", required=True, choices=("approve", "reject"))
            p.add_argument("--reason", required=True)
    sub.add_parser("audit")
    web = sub.add_parser("web", help="Officer review page in the browser (this computer only)")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--model-url", help="Existing local llama-server /completion endpoint")
    web.add_argument("--online", action="store_true", help="Offer the third-party Fetch MCP reference")
    args = parser.parse_args()
    store = Store(args.db)
    if args.command == "web":
        import uvicorn
        from .review_app import create_app
        print(f"Officer review page: http://127.0.0.1:{args.port}/  (Ctrl+C to stop)")
        uvicorn.run(create_app(args.db, args.model_url, args.online), host="127.0.0.1",
                    port=args.port, log_level="warning")
        return 0
    try:
        if args.command == "draft":
            result = asyncio.run(draft(args.query, args.db, args.region, args.model_url,
                                      args.online, args.require_external))
        elif args.command == "show":
            result = store.get(args.id)
        elif args.command == "review":
            # Real terminal and typed confirmation required; no --yes bypass.
            if not sys.stdin.isatty():
                raise ValueError("Human review requires an interactive terminal")
            advisory = store.get(args.id)
            print(json.dumps(advisory, ensure_ascii=False, indent=2))
            expected = args.decision.upper() + " " + args.digest
            entered = input("After reviewing all evidence, type " + expected + ": ")
            if entered != expected:
                raise ValueError("Human confirmation did not match; no decision saved")
            result = store.review(args.id, args.digest, getpass.getuser(),
                                  args.decision == "approve", args.reason)
        elif args.command == "export":
            result = store.export(args.id, getpass.getuser())
        else:
            result = {"verified": True, "events": store.audit()}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(error_messages(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
