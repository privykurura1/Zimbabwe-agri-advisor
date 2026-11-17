"""Pages and endpoints for the extras, added to app.py with include_router.

    /extras/dashboard      outbreak early warning (counts from the query log)
    /extras/farm           farm records and reminders
    /extras/help           who to contact, by province
    /api/extras/answer     summary / contacts / outlook shown under an answer
    /api/extras/outbreak   the dashboard numbers as JSON
    /audio/<file>          recorded summaries

The HTML for the pages is in views.py; this file only handles data and routes.
"""
from datetime import date
import os
import re
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from . import content, outbreak, views
from .farm import SUGGESTED, Farm

_AUDIO_NAME = re.compile(r"^[A-Z]\d{1,2}_(en|sn|nd)\.(mp3|ogg|wav|m4a)$")
_AUDIO_TYPES = {"mp3": "audio/mpeg", "ogg": "audio/ogg", "wav": "audio/wav", "m4a": "audio/mp4"}


def condition_titles(chunks, rag):
    """Entry id -> condition name, for entries that are diseases or pests."""
    titles = {}
    for chunk in chunks:
        cid = rag.chunk_id(chunk)
        name = rag.condition_name([chunk]) if cid else None
        if cid and name:
            titles[cid] = name
    return titles


def same_origin(request: Request):
    """Refuse form posts made by another web site in the farmer's browser."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin and urlparse(origin).netloc != request.headers.get("host", ""):
        raise HTTPException(403, "Cross-site request refused")


def create_router(chunks, rag, log_path, farm_path=None):
    router = APIRouter()
    titles = condition_titles(chunks, rag)
    state = {}

    def farm():
        if "farm" not in state:
            state["farm"] = Farm(farm_path)
        return state["farm"]

    def report():
        return outbreak.summarise(outbreak.read_log(log_path), titles)

    @router.get("/api/extras/answer")
    def answer_extras(ids: str = "", language: str = "english", province: str = "",
                      domain: str = "animal", region: str = ""):
        entry_ids = [i for i in ids.split(",") if re.match(r"^[A-Z]\d{1,2}$", i)][:6]
        return content.extras_for_answer(entry_ids, language, province, domain, region)

    @router.get("/api/extras/outbreak")
    def outbreak_json():
        return report()

    @router.get("/audio/{name}")
    def audio(name: str):
        m = _AUDIO_NAME.match(name)
        path = os.path.join(content.AUDIO_DIR, name)
        if not m or not os.path.isfile(path):
            raise HTTPException(404)
        return FileResponse(path, media_type=_AUDIO_TYPES[m.group(2)])

    @router.get("/extras/dashboard")
    def dashboard():
        return HTMLResponse(views.dashboard(report()))

    @router.get("/extras/help")
    def help_page(province: str = ""):
        province = province if province in outbreak.PROVINCES else ""
        return HTMLResponse(views.help_page(outbreak.PROVINCES, province,
                                            content.contacts_for(province, domain="all")))

    @router.get("/extras/farm")
    def farm_page(error: str = ""):
        f = farm()
        return HTMLResponse(views.farm_page(f.reminders(), f.records(), SUGGESTED["dipping"],
                                            date.today().isoformat(), error[:200]))

    def _do(request, action):
        same_origin(request)
        try:
            action()
        except (ValueError, KeyError) as e:
            return RedirectResponse("/extras/farm?error=" + quote(str(e)), status_code=303)
        return RedirectResponse("/extras/farm", status_code=303)

    @router.post("/extras/farm/record")
    def add_record(request: Request, day: str = Form(...), subject: str = Form(...), note: str = Form(...)):
        return _do(request, lambda: farm().add_record(day, subject, note))

    @router.post("/extras/farm/reminder")
    def add_reminder(request: Request, due: str = Form(...), text: str = Form(...), repeat_days: int = Form(0)):
        return _do(request, lambda: farm().add_reminder(due, text, repeat_days))

    @router.post("/extras/farm/suggested")
    def add_suggested(request: Request, key: str = Form(...), start: str = Form(...)):
        return _do(request, lambda: farm().add_suggested(key, start))

    @router.post("/extras/farm/done")
    def done(request: Request, reminder_id: int = Form(...)):
        return _do(request, lambda: farm().complete(reminder_id))

    return router
