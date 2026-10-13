"""Officer review page: the human side of the workflow, in a browser.

Runs only on this computer (127.0.0.1). An extension officer can
  1. enter a farmer's question -> the LangGraph agent drafts an advisory via MCP,
  2. read the draft with all its evidence,
  3. approve or reject it (typed confirmation + name + reason), and
  4. export approved advice and check the audit log.

The agent itself has no access to any of this: approval and export are not MCP
tools, and this page is a separate, human-only interface on top of the same
store the CLI uses.
"""
import getpass
from html import escape
import json
from pathlib import Path
import re

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from .orchestrator import ROOT, draft
from .store import Store

LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
REGIONS = ["", "I", "II", "III", "IV", "V"]

CSS = """
:root{--green:#2f6b2f;--green-dark:#1f4d1f;--bg:#f6f4ee;--card:#fff;--ink:#1d211c;--muted:#5d665a;
--line:#dcd8cc;--red:#a32020;--red-bg:#fbeaea;--amber-bg:#fff5df;--ok-bg:#e9f4e6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{background:var(--green);color:#fff;padding:12px 20px;display:flex;align-items:center;gap:12px}
header img{width:36px;height:36px;border-radius:8px;background:#fff}
header a{color:#fff;text-decoration:none}header h1{font-size:19px;margin:0}
header nav{margin-left:auto;display:flex;gap:16px;font-size:15px;white-space:nowrap}
main{max-width:980px;margin:0 auto;padding:20px 16px 48px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:18px}
h2{font-size:18px;margin:0 0 12px}label{display:block;font-weight:600;margin:10px 0 4px}
textarea,input[type=text],select{width:100%;padding:9px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;background:#fff}
textarea{min-height:80px}.row{display:flex;gap:16px;flex-wrap:wrap}.row>div{flex:1;min-width:180px}
.check{display:flex;gap:8px;align-items:center;font-weight:400;margin-top:12px}
button{background:var(--green);color:#fff;border:0;border-radius:8px;padding:10px 18px;font:inherit;font-weight:600;cursor:pointer;margin-top:14px}
button:hover{background:var(--green-dark)}button.reject{background:var(--red)}
table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:.03em}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:13px;font-weight:600}
.pending{background:var(--amber-bg);color:#7a5200}.approved{background:var(--ok-bg);color:var(--green-dark)}
.rejected{background:var(--red-bg);color:var(--red)}.urgent{background:var(--red);color:#fff}
.draft h3{font-size:15px;margin:12px 0 2px;color:var(--green-dark)}.draft h3:first-child{margin-top:0}
.draft{white-space:pre-wrap;background:#fbfaf6;border:1px solid var(--line);border-radius:8px;padding:14px;font-size:15px}
.muted{color:var(--muted);font-size:14px}code{font-size:13px;word-break:break-all}
.notice{border-left:4px solid var(--green);background:var(--ok-bg);padding:10px 14px;border-radius:6px}
.warn{border-left:4px solid var(--red);background:var(--red-bg);padding:10px 14px;border-radius:6px}
details{margin:8px 0}summary{cursor:pointer;font-weight:600}
@media (max-width:600px){header nav{gap:10px;font-size:14px}main{padding:14px 12px}}
"""


def page(title, body):
    return HTMLResponse(
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)} - Murimi Fara officer review</title><style>{CSS}</style></head><body>"
        f"<header><img src='/logo.png' alt=''><h1><a href='/'>Murimi Fara - officer review</a></h1>"
        f"<nav><a href='/'>Advisories</a><a href='/audit'>Audit log</a></nav></header>"
        f"<main>{body}</main></body></html>")


def render_draft(text):
    """Escape the draft, then show its '### ' headings and **bold** as such."""
    lines = []
    for line in escape(text).split("\n"):
        if line.startswith("### "):
            lines.append(f"<h3>{line[4:]}</h3>")
        else:
            lines.append(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line))
    return re.sub(r"\n?(<h3>.*?</h3>)\n?", r"\1", "\n".join(lines))


def badge(state):
    return f"<span class='badge {escape(state)}'>{escape(state)}</span>"


def create_app(db_path, model_url=None, allow_online=False):
    app = FastAPI(title="Murimi Fara officer review", docs_url=None, redoc_url=None, openapi_url=None)
    store = Store(db_path)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        # Bound to 127.0.0.1, and also refuse requests that name another host or
        # come from another website (DNS rebinding / cross-site form posts).
        host = (request.headers.get("host") or "").rsplit(":", 1)[0]
        origin = request.headers.get("origin")
        if host not in LOCAL_HOSTS:
            return JSONResponse({"detail": "local access only"}, status_code=403)
        if request.method == "POST" and origin and origin.split("//")[-1].rsplit(":", 1)[0] not in LOCAL_HOSTS:
            return JSONResponse({"detail": "cross-site request refused"}, status_code=403)
        return await call_next(request)

    @app.get("/logo.png")
    def logo():
        path = ROOT / "murimifara.png"
        if not path.exists():
            raise HTTPException(404)
        return FileResponse(path)

    @app.get("/")
    def home(message: str = ""):
        def row(a):
            flags = badge(a["state"])
            if a["urgent"]:
                flags += " <span class='badge urgent'>urgent</span>"
            if a["exported"]:
                flags += " <span class='muted'>exported</span>"
            when = escape((a["staged_at"] or "")[:16].replace("T", " "))
            return (f"<tr><td><a href='/advisory/{escape(a['id'])}'>{escape(a['query'][:90])}</a></td>"
                    f"<td>{flags}</td><td class='muted'>{when}</td></tr>")
        rows = "".join(row(a) for a in store.list()) or \
            "<tr><td colspan='3' class='muted'>No advisories yet.</td></tr>"
        options = "".join(f"<option value='{r}'>{('Natural Region ' + r) if r else 'Not needed / unknown'}</option>"
                          for r in REGIONS)
        model_note = (f"Drafts are written by the local model at <code>{escape(model_url)}</code>."
                      if model_url else "No local model configured: drafts are evidence-only templates.")
        online_box = ("<label class='check'><input type='checkbox' name='online' value='1'> Also fetch the FAO "
                      "fall-armyworm reference (third-party Fetch MCP server, needs internet)</label>"
                      if allow_online else "")
        msg = f"<p class='notice'>{escape(message)}</p>" if message else ""
        return page("Advisories", f"""
            {msg}
            <section class='card'><h2>New farmer question</h2>
            <form method='post' action='/draft'>
              <label for='q'>Farmer's message (English, Shona or Ndebele)</label>
              <textarea id='q' name='query' required minlength='3' maxlength='2000'
                placeholder='e.g. My maize has ragged holes and frass in the whorl'></textarea>
              <div class='row'><div><label for='r'>Farm location</label><select id='r' name='region'>{options}</select></div></div>
              {online_box}
              <button type='submit'>Ask the agent to draft an advisory</button>
              <p class='muted'>{model_note} Nothing is sent to the farmer: every draft waits for your decision.</p>
            </form></section>
            <section class='card'><h2>Advisories</h2>
            <table><tr><th>Question</th><th>Status</th><th>Drafted (UTC)</th></tr>{rows}</table></section>""")

    @app.post("/draft")
    async def make_draft(query: str = Form(...), region: str = Form(""), online: str = Form("")):
        try:
            result = await draft(query, db_path, region, model_url, allow_online and online == "1")
        except Exception as exc:
            return page("Draft failed", f"<p class='warn'>The agent could not draft this: {escape(str(exc))}</p>"
                                        f"<p><a href='/'>Back</a></p>")
        if result.get("state") == "needs_information":
            return page("More information needed",
                        f"<section class='card'><h2>The agent needs more information</h2>"
                        f"<p class='muted'>Question: {escape(query)}</p>"
                        f"<div class='draft'>{escape(result['message'])}</div>"
                        f"<p class='muted'>No draft was stored. Ask the farmer, then submit a new question.</p>"
                        f"<p><a href='/'>Back</a></p></section>")
        return RedirectResponse(f"/advisory/{result['id']}", status_code=303)

    @app.get("/advisory/{advisory_id}")
    def show(advisory_id: str, message: str = ""):
        try:
            advisory = store.get(advisory_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc))
        doc, state, code = advisory["document"], advisory["state"], advisory["digest"][:8]
        sources = "".join(f"<details><summary>{escape(s['title'].lstrip('# '))}</summary>"
                          f"<div class='draft'>{escape(s['text'])}</div></details>" for s in doc.get("sources", []))
        extra = ""
        if doc.get("supplementary_reference"):
            ref = doc["supplementary_reference"]
            extra = (f"<details><summary>Third-party reference (untrusted, for your information)</summary>"
                     f"<p class='muted'>{escape(ref['url'])} - {escape(ref['notice'])}</p>"
                     f"<div class='draft'>{escape(ref['text'])}</div></details>")
        if doc.get("region"):
            extra += f"<p class='muted'>Farm location: Natural Region {escape(doc['region'])}</p>"
        if state == "pending":
            action = f"""
              <section class='card'><h2>Your decision</h2>
              <form method='post' action='/advisory/{escape(advisory_id)}/review'>
                <input type='hidden' name='digest' value='{escape(advisory['digest'])}'>
                <div class='row'><div><label for='n'>Your name</label><input type='text' id='n' name='name' required maxlength='100'></div>
                <div><label for='d'>Decision</label><select id='d' name='decision'>
                  <option value='approve'>Approve</option><option value='reject'>Reject</option></select></div></div>
                <label for='why'>Reason</label><input type='text' id='why' name='reason' required maxlength='2000'
                  placeholder='e.g. Matches field inspection; advice checked against AGRITEX guidance'>
                <label for='c'>To confirm you have read the whole draft and its evidence, type
                  <code>APPROVE {code}</code> or <code>REJECT {code}</code></label>
                <input type='text' id='c' name='confirmation' required autocomplete='off'>
                <button type='submit'>Save decision</button>
              </form></section>"""
        elif state == "approved":
            action = (f"<section class='card'><h2>Approved by {escape(advisory['reviewer'] or '')}</h2>"
                      f"<p class='muted'>Reason: {escape(advisory['reason'] or '')}</p>"
                      f"<form method='post' action='/advisory/{escape(advisory_id)}/export'>"
                      f"<button type='submit'>Export approved advisory</button></form></section>")
        else:
            action = (f"<section class='card'><h2>Rejected by {escape(advisory['reviewer'] or '')}</h2>"
                      f"<p class='muted'>Reason: {escape(advisory['reason'] or '')}. "
                      f"Revisions need a new draft and a new decision.</p></section>")
        msg = f"<p class='notice'>{escape(message)}</p>" if message else ""
        urgent = "<p class='warn'><b>Urgent case.</b> The farmer should contact a veterinary officer today.</p>" if doc.get("urgent") else ""
        return page("Advisory", f"""
            {msg}<section class='card'><h2>Farmer's question {badge(state)}</h2>
            <p>{escape(doc.get('query', ''))}</p>{urgent}
            <h2>Draft advisory <span class='muted'>({escape(doc.get('generation', ''))})</span></h2>
            <div class='draft'>{render_draft(doc.get('text', ''))}</div>
            <p class='muted'>{escape(doc.get('notice', ''))}</p>
            <h2>Evidence used</h2>{sources}{extra}
            <p class='muted'>Content digest: <code>{escape(advisory['digest'])}</code></p></section>
            {action}<p><a href='/'>Back to all advisories</a></p>""")

    @app.post("/advisory/{advisory_id}/review")
    def review(advisory_id: str, digest: str = Form(...), name: str = Form(...), decision: str = Form(...),
               reason: str = Form(...), confirmation: str = Form(...)):
        if decision not in {"approve", "reject"}:
            raise HTTPException(400, "Unknown decision")
        expected = f"{decision.upper()} {digest[:8]}"
        if confirmation.strip() != expected:
            return RedirectResponse(f"/advisory/{advisory_id}?message=" + _q(
                f"Confirmation did not match - type exactly: {expected}. No decision saved."), status_code=303)
        reviewer = f"{name.strip()} (web review, OS user {getpass.getuser()})"
        try:
            store.review(advisory_id, digest, reviewer, decision == "approve", reason)
        except ValueError as exc:
            return RedirectResponse(f"/advisory/{advisory_id}?message=" + _q(str(exc)), status_code=303)
        return RedirectResponse(f"/advisory/{advisory_id}?message=" + _q("Decision saved and logged."),
                                status_code=303)

    @app.post("/advisory/{advisory_id}/export")
    def export(advisory_id: str):
        try:
            result = store.export(advisory_id, getpass.getuser() + " (web)")
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return JSONResponse(result, headers={
            "Content-Disposition": f"attachment; filename=advisory-{advisory_id[:8]}.json"})

    @app.get("/audit")
    def audit():
        try:
            events = store.audit()
            status = "<p class='notice'>Audit chain verified: every entry links to the one before it.</p>"
        except ValueError as exc:
            events, status = [], f"<p class='warn'>{escape(str(exc))}</p>"
        rows = "".join(f"<tr><td>{e['seq']}</td><td class='muted'>{escape(e['timestamp'][:19].replace('T', ' '))}</td>"
                       f"<td>{escape(e['event'])}</td><td>{escape(e['actor'])}</td>"
                       f"<td><code>{escape(json.dumps(e['payload'], ensure_ascii=False)[:160])}</code></td></tr>"
                       for e in reversed(events))
        return page("Audit log", f"<section class='card'><h2>Audit log ({len(events)} events)</h2>{status}"
                                 f"<table><tr><th>#</th><th>Time (UTC)</th><th>Event</th><th>Actor</th><th>Details</th></tr>"
                                 f"{rows}</table></section>")

    return app


def _q(text):
    from urllib.parse import quote
    return quote(text)
