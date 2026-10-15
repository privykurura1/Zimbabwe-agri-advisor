"""HTML for the extras pages, styled to match the main Murimi Fara app.

Everything is in this one file (CSS inline, icons as inline SVG) so the pages
work with no internet and nothing extra to copy. Every value that comes from a
person or a file is passed through esc() before it reaches the page.
"""
from html import escape

DESIGN_VERSION = "2"


def esc(value):
    return escape(str(value if value is not None else ""), quote=True)


# ---------------------------------------------------------------- icons
_ICON_PATHS = {
    "chat": '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
    "pulse": '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>',
    "book": '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5z"/><path d="M8 7h7M8 11h5"/>',
    "phone": '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
    "bell": '<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "alert": '<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17h.01"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "map": '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "upload": '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v4h16v-4"/>',
    "leaf": '<path d="M5 19c0-8 6-14 15-14 0 9-6 15-14 15"/><path d="M5 19l7-7"/>',
}


def icon(name, size=18):
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{_ICON_PATHS[name]}</svg>')


# ---------------------------------------------------------------- styles
CSS = """
:root{
 --canopy:#10291a;--canopy-2:#173a24;--leaf:#3f8f3a;--leaf-dark:#2f6f2c;--leaf-wash:#e9f3e6;
 --harvest:#e3a72f;--harvest-wash:#fdf6e6;--mist:#eef1ea;--surface:#fff;--rule:#dbe1d6;
 --ink:#152018;--ink-2:#4c5a4f;--ink-3:#7c887e;--danger:#b8432c;--danger-wash:#fbece8;
 --sky:#2f6f9f;--sky-wash:#eaf2f9;
 --font:"Segoe UI Variable Text","Segoe UI",-apple-system,"SF Pro Text",Roboto,"Helvetica Neue",Arial,sans-serif;
 --display:"Segoe UI Variable Display","Segoe UI",-apple-system,"SF Pro Display",Roboto,"Helvetica Neue",Arial,sans-serif;
 --radius:14px;--shadow:0 1px 2px rgba(16,41,26,.06),0 4px 14px rgba(16,41,26,.05);
}
*{box-sizing:border-box}
html{font-size:16px}
body{margin:0;min-height:100vh;background:var(--mist);color:var(--ink);font-family:var(--font);line-height:1.5;
 -webkit-font-smoothing:antialiased}
a{color:var(--leaf-dark)}
.ic{flex-shrink:0;vertical-align:middle}

/* header + tabs */
.mf-top{background:var(--canopy);color:#e9efe6;border-bottom:1px solid rgba(227,167,47,.35)}
.mf-top-in{max-width:880px;margin:0 auto;padding:.7rem 1rem;display:flex;align-items:center;gap:.75rem}
.mf-logo{width:2.4rem;height:2.4rem;border-radius:.6rem;background:#fff;object-fit:contain;padding:2px}
.mf-brand{color:#fff;text-decoration:none;display:flex;flex-direction:column;line-height:1.2}
.mf-brand b{font-family:var(--display);font-size:1.1rem;font-weight:600}
.mf-brand small{font-size:.75rem;color:#b9c7b8}
.mf-tabs{background:var(--canopy-2)}
.mf-tabs-in{max-width:880px;margin:0 auto;padding:0 .6rem;display:flex;gap:.15rem;overflow-x:auto;scrollbar-width:none}
.mf-tabs-in::-webkit-scrollbar{display:none}
.mf-tab{display:inline-flex;align-items:center;gap:.4rem;padding:.7rem .8rem;color:#cfdacd;text-decoration:none;
 font-size:.86rem;white-space:nowrap;border-bottom:3px solid transparent}
.mf-tab:hover,.mf-tab:focus-visible{color:#fff;outline:none;border-bottom-color:rgba(227,167,47,.5)}
.mf-tab[aria-current=page]{color:#fff;font-weight:600;border-bottom-color:var(--harvest)}

/* page */
.mf-main{max-width:880px;margin:0 auto;padding:1.5rem 1rem 3.5rem}
.mf-intro{display:flex;gap:.9rem;align-items:flex-start;margin-bottom:1.3rem}
.mf-intro-ic{width:2.8rem;height:2.8rem;border-radius:.8rem;background:var(--canopy);color:var(--harvest);
 display:grid;place-items:center;flex-shrink:0}
.mf-intro h1{font-family:var(--display);font-size:1.65rem;line-height:1.2;margin:.05rem 0 .2rem;letter-spacing:-.01em}
.mf-intro p{margin:0;color:var(--ink-2);max-width:42rem}
.mf-section{margin-top:1.6rem}
.mf-section>h2{font-family:var(--display);font-size:1.05rem;margin:0 0 .65rem;display:flex;align-items:center;gap:.5rem}
.mf-count{font-family:var(--font);font-size:.75rem;font-weight:600;color:var(--ink-3);background:#fff;
 border:1px solid var(--rule);border-radius:999px;padding:0 .5rem}
.mf-card{background:var(--surface);border:1px solid var(--rule);border-radius:var(--radius);box-shadow:var(--shadow)}
.mf-pad{padding:1rem 1.1rem}
.mf-muted{color:var(--ink-3);font-size:.85rem}
.mf-foot{margin-top:1.5rem;color:var(--ink-3);font-size:.82rem;display:flex;gap:.4rem;align-items:center}

/* notices */
.mf-note{display:flex;gap:.7rem;align-items:flex-start;border-radius:var(--radius);padding:.85rem 1rem;margin:.6rem 0;
 border:1px solid}
.mf-note b{display:block}
.mf-note.warn{background:var(--harvest-wash);border-color:#edd29a;color:#5c4210}
.mf-note.warn .ic{color:#b07a10}
.mf-note.good{background:var(--leaf-wash);border-color:#c7dfc2;color:#24502a}
.mf-note.good .ic{color:var(--leaf)}
.mf-note.bad{background:var(--danger-wash);border-color:#efc7bd;color:#7a2a1a}
.mf-note.bad .ic{color:var(--danger)}
.mf-note.info{background:var(--sky-wash);border-color:#cfe0ef;color:#1f4a6b}

/* stat tiles */
.mf-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem}
.mf-stat{padding:.9rem 1rem}
.mf-stat b{display:block;font-family:var(--display);font-size:1.9rem;line-height:1.1}
.mf-stat span{font-size:.82rem;color:var(--ink-2)}
.mf-stat.hot b{color:#b07a10}

/* condition rows */
.mf-list{list-style:none;margin:0;padding:0}
.mf-row{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) auto;gap:.4rem 1rem;align-items:center;
 padding:.8rem 1.1rem;border-top:1px solid var(--rule)}
.mf-row:first-child{border-top:none}
.mf-row-title{font-weight:600}
.mf-row-sub{font-size:.8rem;color:var(--ink-3)}
.mf-bar{height:.5rem;background:#eef1ea;border-radius:999px;overflow:hidden}
.mf-bar i{display:block;height:100%;background:var(--leaf);border-radius:999px}
.mf-bar i.hot{background:var(--harvest)}
.mf-num{font-variant-numeric:tabular-nums;font-weight:600;text-align:right;min-width:4.5rem}
.mf-num small{display:block;font-weight:400;font-size:.75rem;color:var(--ink-3)}
.mf-chips{display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.35rem}
.mf-chip{font-size:.75rem;background:#f4f6f1;border:1px solid var(--rule);border-radius:999px;padding:.05rem .55rem;color:var(--ink-2)}
.mf-alert{border-left:4px solid var(--harvest)}
.mf-alert h3{margin:0 0 .25rem;font-size:1rem;display:flex;gap:.45rem;align-items:center}
.mf-alert h3 .ic{color:#b07a10}
.mf-alert p{margin:0;color:var(--ink-2)}
.mf-alert+.mf-alert{margin-top:.6rem}

/* forms */
.mf-form{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.75rem .9rem;align-items:end}
.mf-form .wide{grid-column:1/-1}
.mf-field{display:flex;flex-direction:column;gap:.3rem}
.mf-field>span{font-size:.78rem;font-weight:600;color:var(--ink-2)}
.mf-field em{font-style:normal;font-weight:400;color:var(--ink-3)}
input,select{font:inherit;font-size:.95rem;color:var(--ink);background:#fff;border:1px solid #cdd5c8;border-radius:.6rem;
 padding:.55rem .7rem;width:100%;min-height:2.6rem}
input:focus,select:focus{outline:none;border-color:var(--leaf);box-shadow:0 0 0 3px rgba(63,143,58,.18)}
.mf-btn{font:inherit;font-size:.92rem;font-weight:600;display:inline-flex;align-items:center;justify-content:center;gap:.4rem;
 color:#fff;background:var(--leaf);border:0;border-radius:.6rem;padding:.6rem 1.1rem;min-height:2.6rem;cursor:pointer;
 text-decoration:none;white-space:nowrap}
.mf-btn:hover,.mf-btn:focus-visible{background:var(--leaf-dark);outline:none}
.mf-btn.ghost{background:#fff;color:var(--leaf-dark);border:1px solid #cdd5c8}
.mf-btn.ghost:hover{border-color:var(--leaf);background:var(--leaf-wash)}
.mf-btn.small{min-height:2.1rem;padding:.35rem .8rem;font-size:.85rem}
details.mf-card>summary{list-style:none;cursor:pointer;padding:.9rem 1.1rem;font-weight:600;display:flex;align-items:center;gap:.5rem}
details.mf-card>summary::-webkit-details-marker{display:none}
details.mf-card>summary::after{content:"+";margin-left:auto;font-size:1.3rem;line-height:1;color:var(--ink-3)}
details.mf-card[open]>summary::after{content:"\\2212"}
details.mf-card[open]>summary{border-bottom:1px solid var(--rule)}
details.mf-card+details.mf-card{margin-top:.6rem}

/* farm */
.mf-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;align-items:start}
.mf-rem{display:flex;gap:.8rem;align-items:center;padding:.8rem 1rem;border-top:1px solid var(--rule)}
.mf-rem:first-child{border-top:none}
.mf-date{width:3.3rem;flex-shrink:0;text-align:center;border-radius:.6rem;background:var(--leaf-wash);color:var(--leaf-dark);
 padding:.3rem 0;line-height:1.1}
.mf-date b{display:block;font-size:1.2rem;font-family:var(--display)}
.mf-date small{font-size:.68rem;text-transform:uppercase;letter-spacing:.05em}
.mf-date.late{background:var(--danger-wash);color:var(--danger)}
.mf-rem-body{flex:1;min-width:0}
.mf-rem-body b{display:block;font-weight:600}
.mf-tag{display:inline-block;font-size:.72rem;font-weight:600;border-radius:999px;padding:.02rem .5rem;margin-right:.3rem}
.mf-tag.late{background:var(--danger-wash);color:var(--danger)}
.mf-tag.soon{background:var(--harvest-wash);color:#8a5e0a}
.mf-tag.rep{background:#f1f4ee;color:var(--ink-2)}
.mf-timeline{list-style:none;margin:0;padding:.4rem 1.1rem}
.mf-timeline li{position:relative;padding:.55rem 0 .55rem 1.3rem;border-left:2px solid var(--rule);margin-left:.3rem}
.mf-timeline li::before{content:"";position:absolute;left:-.42rem;top:.85rem;width:.7rem;height:.7rem;border-radius:50%;
 background:#fff;border:2px solid var(--leaf)}
.mf-timeline time{font-size:.78rem;color:var(--ink-3);display:block}
.mf-suggest{background:var(--harvest-wash);border:1px dashed #e3c47a;border-radius:var(--radius);padding:.9rem 1rem;margin-bottom:.6rem}
.mf-suggest b{display:flex;gap:.4rem;align-items:center}

/* contacts */
.mf-contacts{display:grid;grid-template-columns:repeat(auto-fill,minmax(16rem,1fr));gap:.7rem}
.mf-contact{padding:1rem 1.1rem;display:flex;flex-direction:column;gap:.5rem}
.mf-contact-type{font-size:.72rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--leaf-dark)}
.mf-contact b{font-size:1.02rem}
.mf-contact .mf-btn{margin-top:auto;align-self:flex-start}
.mf-empty{text-align:center;padding:2rem 1.2rem}
.mf-empty .mf-intro-ic{margin:0 auto .8rem;background:var(--leaf-wash);color:var(--leaf-dark)}
.mf-empty h3{margin:0 0 .3rem;font-family:var(--display)}
.mf-empty p{margin:0 auto;color:var(--ink-2);max-width:30rem}

/* photo */
.mf-drop{display:flex;flex-direction:column;align-items:center;gap:.4rem;text-align:center;border:2px dashed #c3cfbd;
 border-radius:var(--radius);padding:1.6rem 1rem;background:#fafbf8;cursor:pointer;color:var(--ink-2)}
.mf-drop:hover{border-color:var(--leaf);background:var(--leaf-wash)}
.mf-drop .ic{color:var(--leaf)}
.mf-drop input{max-width:18rem;border:0;background:none;min-height:auto;padding:.3rem;font-size:.85rem}
.mf-result{overflow:hidden}
.mf-result-head{display:flex;gap:.7rem;align-items:center;padding:1rem 1.1rem;font-weight:600}
.mf-result-head.problem{background:var(--danger-wash);color:var(--danger)}
.mf-result-head.no_problem_seen{background:var(--leaf-wash);color:var(--leaf-dark)}
.mf-result-head.unsure{background:var(--harvest-wash);color:#8a5e0a}
.mf-meter{height:.6rem;background:#eef1ea;border-radius:999px;overflow:hidden;margin:.35rem 0 .2rem}
.mf-meter i{display:block;height:100%;background:var(--leaf)}

@media (max-width:700px){
 .mf-grid{grid-template-columns:1fr}
 .mf-stats{grid-template-columns:1fr 1fr 1fr;gap:.5rem}
 .mf-stat{padding:.7rem}
 .mf-stat b{font-size:1.45rem}
 .mf-row{grid-template-columns:1fr auto}
 .mf-row .mf-bar{grid-column:1/-1;order:3}
 .mf-intro h1{font-size:1.35rem}
 .mf-brand small{display:none}
}
@media (prefers-reduced-motion:no-preference){.mf-btn,.mf-tab,.mf-drop{transition:background .15s,border-color .15s,color .15s}}
"""

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

TABS = [("/", "Advisor", "chat"), ("/extras/dashboard", "Outbreak watch", "pulse"),
        ("/extras/farm", "Farm records", "book"), ("/extras/help", "Find help", "phone"),
        ("/extras/photo", "Photo checks", "camera"), ("/officer/", "Officer review", "check")]


def shell(title, lead, icon_name, current, body):
    tabs = "".join(f'<a class="mf-tab" href="{href}"{" aria-current=page" if href == current else ""}>'
                   f'{icon(ic, 16)}{label}</a>' for href, label, ic in TABS)
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<meta name='murimi-extras-design' content='{DESIGN_VERSION}'>"
            f"<title>{esc(title)} - Murimi Fara</title><link rel='icon' href='/murimifara.png'>"
            f"<style>{CSS}</style></head><body>"
            f"<header class='mf-top'><div class='mf-top-in'>"
            f"<img class='mf-logo' src='/murimifara.png' alt='' onerror=\"this.style.display='none'\">"
            f"<a class='mf-brand' href='/'><b>Murimi Fara</b><small>Farm advisor for livestock and crops</small></a>"
            f"</div></header>"
            f"<nav class='mf-tabs' aria-label='Sections'><div class='mf-tabs-in'>{tabs}</div></nav>"
            f"<main class='mf-main'><div class='mf-intro'><div class='mf-intro-ic'>{icon(icon_name, 22)}</div>"
            f"<div><h1>{esc(title)}</h1><p>{esc(lead)}</p></div></div>{body}</main></body></html>")


def note(kind, title, text="", icon_name=None):
    icon_name = icon_name or {"warn": "alert", "bad": "alert", "good": "check", "info": "leaf"}[kind]
    return (f"<div class='mf-note {kind}' role='{'alert' if kind == 'bad' else 'status'}'>{icon(icon_name)}"
            f"<div><b>{esc(title)}</b>{esc(text)}</div></div>")


def empty(icon_name, title, text):
    return (f"<div class='mf-card mf-empty'><div class='mf-intro-ic'>{icon(icon_name, 22)}</div>"
            f"<h3>{esc(title)}</h3><p>{esc(text)}</p></div>")


def section(title, inner, count=None):
    badge = f" <span class='mf-count'>{count}</span>" if count is not None else ""
    return f"<section class='mf-section'><h2>{esc(title)}{badge}</h2>{inner}</section>"


# ---------------------------------------------------------------- outbreak watch
def _when(iso):
    """'2026-10-15T09:49+00:00' -> '15 Oct 2026, 09:49 UTC'."""
    try:
        day, clock = iso.split("T")
        y, m, d = day.split("-")
        return f"{int(d)} {_MONTHS[int(m) - 1]} {y}, {clock[:5]} UTC"
    except (ValueError, IndexError):
        return iso


def dashboard(r):
    alerts, table, rule = r["alerts"], r["table"], r["rule"]
    week_total = sum(t["last_7_days"] for t in table)
    provinces = {p for t in table for p in t["provinces"] if p != "Not given"}
    stats = (f"<div class='mf-stats'>"
             f"<div class='mf-card mf-stat'><b>{week_total}</b><span>matched questions, last 7 days</span></div>"
             f"<div class='mf-card mf-stat{' hot' if alerts else ''}'><b>{len(alerts)}</b><span>conditions to look into</span></div>"
             f"<div class='mf-card mf-stat'><b>{len(provinces)}</b><span>provinces asking</span></div></div>")
    if alerts:
        cards = ""
        for a in alerts:
            before = (f"about {a['weekly_average_before']:g} a week before" if a["weekly_average_before"]
                      else "none in the 4 weeks before")
            chips = "".join(f"<span class='mf-chip'>{esc(p)}: {n}</span>" for p, n in a["provinces"].items())
            cards += (f"<article class='mf-card mf-pad mf-alert'><h3>{icon('alert')}Look into: {esc(a['condition'])}</h3>"
                      f"<p>{a['last_7_days']} questions in the last 7 days, {before}.</p>"
                      f"<div class='mf-chips'>{chips}</div></article>")
        alert_html = section("Rising this week", cards, len(alerts))
    else:
        alert_html = note("good", "No unusual rise in the last 7 days.", "")
    if table:
        top = max(max(t["last_7_days"], t["previous_4_weeks"] / 4) for t in table) or 1
        hot = {a["entry"] for a in alerts}
        rows = ""
        for t in table:
            width = round(100 * t["last_7_days"] / top)
            chips = "".join(f"<span class='mf-chip'>{esc(p)}: {n}</span>" for p, n in t["provinces"].items())
            chips = f"<div class='mf-chips'>{chips}</div>" if chips else ""
            rows += (f"<li class='mf-row'><div><div class='mf-row-title'>{esc(t['condition'])}</div>{chips}</div>"
                     f"<div class='mf-bar' title='{t['last_7_days']} this week'><i class='{'hot' if t['entry'] in hot else ''}' "
                     f"style='width:{width}%'></i></div>"
                     f"<div class='mf-num'>{t['last_7_days']}<small>{t['previous_4_weeks']} in 4 wks before</small></div></li>")
        table_html = section("All conditions asked about", f"<ul class='mf-card mf-list'>{rows}</ul>", len(table))
    else:
        table_html = section("All conditions asked about",
                             empty("pulse", "No answered questions yet",
                                   "Counts appear here as farmers ask the advisor about sick animals and crops."))
    rule_html = (f"<p class='mf-foot'>{icon('leaf', 15)}Flagged when a condition has at least {rule['min_cases']} questions "
                 f"in 7 days and at least {rule['spike_factor']:g}× its weekly average over the {rule['baseline_weeks']} "
                 f"weeks before. More questions is a reason to check with the district vet or AGRITEX, not proof of an "
                 f"outbreak. Updated {esc(_when(r['generated']))}.</p>")
    return shell("Outbreak watch",
                 "Which diseases and pests farmers are asking about, week by week. Counts only - no farmer messages are shown.",
                 "pulse", "/extras/dashboard", stats + alert_html + table_html + rule_html)


# ---------------------------------------------------------------- find help
TYPE_LABELS = {"vet": "Veterinary officer", "animal_health": "Animal health", "dip_tank": "Dip tank",
               "agritex": "AGRITEX extension"}


def help_page(provinces, province, contacts):
    opts = "".join(f"<option{' selected' if p == province else ''}>{esc(p)}</option>" for p in provinces)
    form = (f"<form class='mf-card mf-pad mf-form' method='get'>"
            f"<label class='mf-field'><span>Your province</span><select name='province' onchange='this.form.submit()'>"
            f"<option value=''>Choose a province</option>{opts}</select></label>"
            f"<div><button class='mf-btn'>{icon('map', 16)}Show contacts</button></div></form>")
    if contacts:
        cards = ""
        for c in contacts:
            kind = TYPE_LABELS.get(c.get("type"), c.get("type", ""))
            where = " · ".join(x for x in (c.get("place", ""), c.get("hours", "")) if x) or c.get("province", "")
            phone = c.get("phone", "")
            checked = f"<span class='mf-muted'>Checked {esc(c['checked_on'])}</span>" if c.get("checked_on") else ""
            cards += (f"<article class='mf-card mf-contact'><span class='mf-contact-type'>{esc(kind)}</span>"
                      f"<b>{esc(c.get('name', ''))}</b><span class='mf-muted'>{esc(where)}</span>"
                      f"<a class='mf-btn small' href='tel:{esc(phone.replace(' ', ''))}'>{icon('phone', 15)}{esc(phone)}</a>"
                      f"{checked}</article>")
        result = section("Who to call" + (f" in {province}" if province else ""), f"<div class='mf-contacts'>{cards}</div>",
                         len(contacts))
    else:
        result = section("Who to call", empty(
            "phone", "No checked contacts for this area yet",
            "Ask at your nearest AGRITEX office or dip tank. Contacts are added in data/help_directory.json "
            "after they have been checked by phone."))
    return shell("Find help", "Vets, animal health workers, dip tanks and AGRITEX officers near you.",
                 "phone", "/extras/help", form + result)


# ---------------------------------------------------------------- farm records
def _date_badge(iso, late=False):
    y, m, d = iso.split("-")
    return f"<div class='mf-date{' late' if late else ''}'><b>{int(d)}</b><small>{_MONTHS[int(m) - 1]}</small></div>"


def farm_page(reminders, records, suggested, today, error=""):
    out = [note("bad", "That was not saved.", " " + error) if error else ""]
    if reminders:
        items = ""
        for r in reminders:
            tags = ("<span class='mf-tag late'>Overdue</span>" if r["overdue"] else
                    "<span class='mf-tag soon'>Due soon</span>" if r["soon"] else "")
            tags += (f"<span class='mf-tag rep'>Every {r['repeat_days']} days</span>" if r["repeat_days"]
                     else "<span class='mf-tag rep'>Once</span>")
            source = f"<div class='mf-muted'>{esc(r['source'])}</div>" if r["source"] else ""
            items += (f"<li class='mf-rem'>{_date_badge(r['due'], r['overdue'])}<div class='mf-rem-body'>"
                      f"<b>{esc(r['text'])}</b>{tags}{source}</div>"
                      f"<form method='post' action='/extras/farm/done'><input type='hidden' name='reminder_id' value='{int(r['id'])}'>"
                      f"<button class='mf-btn small ghost' title='Mark done'>{icon('check', 15)}Done</button></form></li>")
        rem_html = f"<ul class='mf-card mf-list'>{items}</ul>"
    else:
        rem_html = empty("bell", "No reminders yet", "Add one on the right, or start the weekly dipping reminder.")
    left = section("Reminders", rem_html, len(reminders) or None)

    s = suggested
    right = section("Add", f"""
<div class='mf-suggest'><b>{icon('leaf', 16)}Suggested: {esc(s['text'])}</b>
<p class='mf-muted' style='margin:.25rem 0 .7rem'>{esc(s['source'])}</p>
<form class='mf-form' method='post' action='/extras/farm/suggested'><input type='hidden' name='key' value='dipping'>
<label class='mf-field'><span>Start on</span><input type='date' name='start' value='{today}' required></label>
<div><button class='mf-btn'>{icon('plus', 16)}Add weekly dipping</button></div></form></div>
<details class='mf-card' open><summary>{icon('book', 16)}Add a record</summary><div class='mf-pad'>
<form class='mf-form' method='post' action='/extras/farm/record'>
<label class='mf-field'><span>Date</span><input type='date' name='day' value='{today}' required></label>
<label class='mf-field'><span>Animal, herd or plot</span><input name='subject' required maxlength='300' placeholder='e.g. Cattle (12)'></label>
<label class='mf-field wide'><span>What happened</span><input name='note' required maxlength='300' placeholder='e.g. dipped; one cow with red urine, vet called'></label>
<div class='wide'><button class='mf-btn'>Save record</button></div></form></div></details>
<details class='mf-card'><summary>{icon('bell', 16)}Add a reminder</summary><div class='mf-pad'>
<form class='mf-form' method='post' action='/extras/farm/reminder'>
<label class='mf-field'><span>Due</span><input type='date' name='due' value='{today}' required></label>
<label class='mf-field'><span>Repeat every <em>(days, 0 = once)</em></span><input type='number' name='repeat_days' value='0' min='0' max='366'></label>
<label class='mf-field wide'><span>What</span><input name='text' required maxlength='300' placeholder='e.g. vaccinate chickens (date from your vet)'></label>
<div class='wide'><button class='mf-btn'>Add reminder</button></div></form></div></details>""")

    if records:
        rows = "".join(f"<li><time>{esc(r['day'])}</time><b>{esc(r['subject'])}</b> - {esc(r['note'])}</li>" for r in records)
        rec_html = section("Records", f"<div class='mf-card'><ul class='mf-timeline'>{rows}</ul></div>", len(records))
    else:
        rec_html = section("Records", empty("book", "No records yet",
                                            "Write down dipping, treatments, vaccinations, sales and spraying here."))
    body = "".join(out) + f"<div class='mf-grid'><div>{left}</div><div>{right}</div></div>" + rec_html + \
        f"<p class='mf-foot'>{icon('check', 15)}Saved on this computer only.</p>"
    return shell("Farm records", "Reminders and a simple diary for your animals and fields.", "book", "/extras/farm", body)


# ---------------------------------------------------------------- photo checks
def photo_none():
    return shell("Photo checks", "Extra photo checks for crop and animal problems.", "camera", "/extras/photo",
                 empty("camera", "No extra photo checks are switched on yet",
                       "The maize armyworm check is on the main Advisor page. New checks are added in models/photo/ "
                       "only after they have been tested on real farm photos."))


def photo_form(checks):
    opts = "".join(f"<option value='{esc(n)}'>{esc(c['config'].get('title', n))}</option>" for n, c in checks.items())
    body = (f"<form class='mf-card mf-pad mf-form' method='post' action='/extras/photo' enctype='multipart/form-data'>"
            f"<label class='mf-field wide'><span>What to check</span><select name='name'>{opts}</select></label>"
            f"<label class='mf-drop wide'>{icon('upload', 28)}<b>Take or choose a photo</b>"
            f"<span class='mf-muted'>Daylight, close to one leaf, in focus</span>"
            f"<input type='file' name='file' accept='image/*' capture='environment' required></label>"
            f"<div class='wide'><button class='mf-btn'>{icon('camera', 16)}Check photo</button></div></form>")
    return shell("Photo checks", "Take a photo and the app checks it for one specific problem.", "camera",
                 "/extras/photo", body)


_DECISION = {"problem": ("alert", "Possible problem found"), "no_problem_seen": ("check", "Problem not seen"),
             "unsure": ("alert", "Not sure")}


def photo_result(r, tested, entry_title):
    ic, head = _DECISION[r["decision"]]
    tested_html = f"<p class='mf-muted'>{esc(tested)}</p>" if tested else ""
    more = (note("info", "What to do next:", f" ask the Advisor about {entry_title}.", "chat") if entry_title else "")
    body = (f"<article class='mf-card mf-result'><div class='mf-result-head {r['decision']}'>{icon(ic, 20)}"
            f"{esc(head)} - {esc(r['check'])}</div><div class='mf-pad'><p style='margin-top:0'>{esc(r['message'])}</p>"
            f"<div class='mf-muted'>Result: {esc(r['label'])}, {r['confidence']}% sure</div>"
            f"<div class='mf-meter'><i style='width:{max(0, min(100, r['confidence']))}%'></i></div>"
            f"{tested_html}</div></article>{more}"
            f"<p><a class='mf-btn ghost' href='/extras/photo'>{icon('camera', 16)}Check another photo</a></p>")
    return shell("Photo check result", "The photo check only looks for the one problem it was trained on.",
                 "camera", "/extras/photo", body)
