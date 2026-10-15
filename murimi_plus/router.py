"""Pages and endpoints for the extras, added to app.py with include_router.

    /extras/dashboard      outbreak early warning (counts from the query log)
    /extras/farm           farm records and reminders
    /extras/help           who to contact, by province
    /extras/photo          extra photo checks (models/photo/)
    /api/extras/answer     summary / contacts / outlook shown under an answer
    /api/extras/outbreak   the dashboard numbers as JSON
    /audio/<file>          recorded summaries

The HTML for the pages is in views.py; this file only handles data and routes.
"""
from datetime import date
import os
import re
from urllib.parse import quote, urlparse

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from . import content, outbreak, photo_checks, views
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


def create_router(chunks, rag, log_path, farm_path=None, models_dir=None):
    router = APIRouter()
    entry_titles = {rag.chunk_id(c): re.sub(r"^#+\s*[A-Z]\d+\.\s*", "", c.splitlines()[0])
                    for c in chunks if rag.chunk_id(c)}
    nets = {}

    def checks():
        return photo_checks.load_checks(models_dir or photo_checks.MODELS_DIR)

    def check_photo(name, data):
        import cv2
        import numpy as np
        found = checks()
        if name not in found:
            raise HTTPException(404, "No such photo check")
        if name not in nets:
            nets[name] = cv2.dnn.readNetFromONNX(found[name]["path"])
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(400, "Could not read the photo")
        cfg = found[name]["config"]
        result = photo_checks.run_check(cv2, nets[name], cfg, image)
        problems = [l.replace("_", " ") for l in cfg.get("problem_labels", {})]
        result["message"] = photo_checks.MESSAGES[result["decision"]].format(
            label=result["label"].replace("_", " "), title_problem=" or ".join(problems) or "a problem")
        result["entry_title"] = entry_titles.get(result["entry"]) if result["entry"] else None
        result["check"] = cfg.get("title", name)
        return result
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

    @router.get("/api/extras/photo_checks")
    def list_checks():
        return [{"name": n, "title": c["config"].get("title", n), "validation": c["config"].get("validation", {})}
                for n, c in checks().items()]

    @router.post("/api/extras/photo/{name}")
    async def photo_api(name: str, request: Request, file: UploadFile = File(...)):
        same_origin(request)
        return check_photo(name, await file.read())

    @router.get("/extras/photo")
    def photo_page():
        found = checks()
        return HTMLResponse(views.photo_form(found) if found else views.photo_none())

    @router.post("/extras/photo")
    async def photo_form(request: Request, name: str = Form(...), file: UploadFile = File(...)):
        same_origin(request)
        r = check_photo(name, await file.read())
        v = checks()[name]["config"].get("validation", {})
        tested = (f"Tested on {v.get('photos')} photos it had not seen; {v.get('accuracy')}% correct."
                  if v.get("photos") else "")
        return HTMLResponse(views.photo_result(r, tested, r["entry_title"]))

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
