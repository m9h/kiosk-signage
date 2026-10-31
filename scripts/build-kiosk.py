#!/usr/bin/env python3
"""
Build the Frontier Tower kiosk rotation page from web/kiosk-cycle.conf.json.

For each "event" slide it fetches the Luma event page, parses the embedded
__NEXT_DATA__ JSON (name, start time, venue, hosts, cover image), derives a
title/subtitle/badge, generates the RSVP QR, and emits a featured-event panel.
"home", "calendar" and "brand" slides are built from templates.

Usage:
    python3 scripts/build-kiosk.py                # build -> web/kiosk-cycle.html
    python3 scripts/build-kiosk.py --out /tmp/x.html

Adding a featured event = add one {"type":"event","url":...} line to the conf
and re-run (or run scripts/push-cycle.sh <ip...> which builds then deploys).

Dependency: segno (pip install segno). Run with a python that has it, e.g. the
project QR venv.
"""
import argparse, io, json, os, re, sys, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "web", "kiosk-cycle.conf.json")
OUT  = os.path.join(ROOT, "web", "kiosk-cycle.html")

try:
    import segno
except ImportError:
    sys.exit("error: segno not installed. `pip install segno` (or run with the QR venv's python).")


# ---------------------------------------------------------------- helpers
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))

def qr_svg(url):
    """Inline, viewBox'd QR SVG with a white background (dark modules)."""
    buf = io.BytesIO()
    segno.make(url, error="q").save(buf, kind="svg", border=2, dark="#0c0e14",
                                    light=None, xmldecl=False, svgns=True)
    s = buf.getvalue().decode("utf-8")
    n = re.search(r'width="(\d+)"', s).group(1)
    path = re.search(r"(<path[^>]*/>)", s).group(1)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" '
            f'shape-rendering="crispEdges"><rect width="{n}" height="{n}" fill="#fff"/>{path}</svg>')

def fetch_event(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (kiosk-builder)"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError(f"no __NEXT_DATA__ in {url}")
    return json.loads(m.group(1))["props"]["pageProps"]["initialData"]["data"]

def transform_cover(u, w=760):
    if not u:
        return ""
    marker = "images.lumacdn.com/"
    if marker in u and "/cdn-cgi/" not in u:
        host, _, path = u.partition(marker)
        return f"{host}{marker}cdn-cgi/image/format=auto,fit=cover,quality=85,width={w},height={w}/{path}"
    return u

def event_fields(url, data, ov):
    ev = data["event"]
    name = re.sub(r"\s*·\s*Luma$", "", ev["name"]).strip()
    clean = re.sub(r"\s*[–-]\s*Members.*$", "", name, flags=re.I).strip()
    # membership tier is carried in the name suffix ("- Members +3"), not Luma's
    # event_type (which is 'independent' for these). Override via conf "badge".
    mb = re.search(r"[–-]\s*(Members.*?)\s*$", name, flags=re.I)
    badge = ov.get("badge", re.sub(r"\s+", " ", mb.group(1)).upper() if mb else "")
    if "title" in ov:
        title, subtitle = ov["title"], ov.get("subtitle", "")
    elif ":" in clean:
        title, subtitle = (x.strip() for x in clean.split(":", 1))
    else:
        title, subtitle = clean, ov.get("subtitle", "")

    tz = ZoneInfo(ev.get("timezone", "America/Los_Angeles"))
    dt = datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00")).astimezone(tz)
    when_date = dt.strftime("%a · %b %-d").upper()
    when_time = dt.strftime("%-I:%M %p")
    end = (datetime.fromisoformat(ev["end_at"].replace("Z", "+00:00")) if ev.get("end_at")
           else dt + timedelta(hours=3))
    until = int(end.timestamp() * 1000)    # the slide drops out of rotation once the event ends

    addr = (ev.get("geo_address_info") or {}).get("address", "")
    venue = addr.split("@", 1)[1] if "@" in addr else addr
    venue = re.split(r"\s*995\s*Market", venue)[0].strip().rstrip(",").strip()
    where = (f"<b>{esc(venue)}</b> · 995 Market St, San Francisco" if venue
             else "<b>Frontier Tower</b> · 995 Market St, San Francisco")

    hosts = [h["name"] for h in data.get("hosts", [])]
    primary = next((h for h in hosts if h.lower() != "frontier tower"), "")
    host = (f"Hosted by <b>{esc(primary)}</b><br>&amp; Frontier Tower" if primary
            else "Hosted by <b>Frontier Tower</b>")

    cover = transform_cover(ov.get("cover") or ev.get("cover_url", ""))
    return dict(title=esc(title), subtitle=esc(subtitle), badge=esc(badge),
                when_date=esc(when_date), when_time=esc(when_time), where=where,
                host=host, cover=cover, tagline=esc(ov.get("tagline", "")), rsvp=url, until=until)


# ---------------------------------------------------------------- tower svg
def tower_svg():
    cx, w, hh, p, floors, y0 = 100, 62, 25, 15, 14, 44
    out = []
    for k in range(floors - 1, -1, -1):            # bottom-up so top floor paints last
        yc = y0 + k * p
        wk = w + (floors - 1 - k) * 2.2            # widen toward base
        lx, rx = cx - wk, cx + wk
        out.append(f'<polygon points="{lx},{yc} {cx},{yc+hh} {cx},{yc+hh+p} {lx},{yc+p}" fill="rgba(72,50,196,.30)"/>')
        out.append(f'<polygon points="{rx},{yc} {cx},{yc+hh} {cx},{yc+hh+p} {rx},{yc+p}" fill="rgba(125,92,255,.16)"/>')
        out.append(f'<polygon points="{cx},{yc-hh} {rx},{yc} {cx},{yc+hh} {lx},{yc}" '
                   f'fill="rgba(125,92,255,.20)" stroke="rgba(125,92,255,.55)" stroke-width="1"/>')
    return ('<svg viewBox="0 0 200 300" width="100%" height="100%" '
            'preserveAspectRatio="xMidYMid meet">' + "".join(out) + "</svg>")


def network_svg():
    """The [01] THE FRONTIERS hub-and-spoke node diagram from the poster."""
    import math
    cx, cy, R, SR = 200.0, 212.0, 132.0, 134.0
    fr, cr, sr = 47, 42, 21
    frontiers = [(90, ["AI"]), (30, ["Robotics"]), (-30, ["Bio &amp;", "Neurotech"]),
                 (-90, ["Ethereum &amp;", "Blockchain"]), (-150, ["Art &amp;", "Music"]),
                 (150, ["Other", "Minds"])]
    spaces = [(120, ["Private", "Offices"]), (60, ["Cowork"]), (0, ["Lounge"]),
              (-120, ["Podcast", "+ Gym"])]

    def pos(angle, r):
        a = math.radians(angle)
        return cx + r * math.cos(a), cy - r * math.sin(a)

    def label(x, y, eyebrow, lines, color, ecolor, fs, efs=6):
        n, lh = len(lines), fs + 1
        top = y - (n - 1) * lh / 2.0
        s = [f'<text x="{x:.1f}" y="{top - fs*0.8 - 2:.1f}" text-anchor="middle" '
             f'font-family="ui-monospace,monospace" font-size="{efs}" fill="{ecolor}" '
             f'letter-spacing="0.6">{eyebrow}</text>']
        for i, ln in enumerate(lines):
            s.append(f'<text x="{x:.1f}" y="{top + i*lh + fs*0.34:.1f}" text-anchor="middle" '
                     f'font-family="Inter,system-ui,sans-serif" font-weight="700" '
                     f'font-size="{fs}" fill="{color}">{ln}</text>')
        return "".join(s)

    out = []
    ring = [pos(a, R) for a, _ in frontiers]
    for i in range(len(ring)):
        x1, y1 = ring[i]; x2, y2 = ring[(i + 1) % len(ring)]
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="#cbc3ef" stroke-width="1" stroke-dasharray="2 3"/>')
    for a, _ in frontiers:
        x, y = pos(a, R)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#9a8be8" stroke-width="1.4"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{cr}" fill="#15121b"/>')
    out.append(label(cx, cy, "• EVENTS", ["The", "Spaceship"], "#fff", "#b9a9ff", 13))
    for a, lines in frontiers:
        x, y = pos(a, R)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{fr}" fill="#6b5bd6" stroke="#5a3fe0" stroke-width="1.5"/>')
        out.append(label(x, y, "// FRONTIER", lines, "#fff", "#d7cff6", 12))
    for a, lines in spaces:          # drawn last so they nestle in the ring gaps, labels on top
        x, y = pos(a, SR)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{sr}" fill="#e4dff9" stroke="#c3b9f0" stroke-width="1.2"/>')
        out.append(label(x, y, "SPACE", lines, "#3a2b6b", "#8a7bd6", 9, 4.6))
    return ('<svg viewBox="0 0 400 420" width="100%" height="100%" '
            'preserveAspectRatio="xMidYMid meet">' + "".join(out) + "</svg>")


# ---------------------------------------------------------------- templates
EVENT_TMPL = '''  <section class="screen" id="__ID__">
    <div class="fx-eyebrow"><span class="live"></span>Featured event · Frontier Tower SF</div>
    <div class="fx-cover" style="background-image:url('__COVER__')"></div>
    <h1 class="fx-title">__TITLE____SUBWRAP__</h1>
    __BADGEWRAP__
    <div class="fx-when"><span class="d">__WHEN_DATE__</span><span class="t">__WHEN_TIME__</span></div>
    <div class="fx-where">__WHERE__</div>
    __TAGWRAP__
    <div class="fx-foot">
      <div class="fx-host">__HOST__</div>
      <div class="fx-qr">__QR__<span>SCAN TO RSVP</span></div>
    </div>
  </section>'''

HOME_TMPL = '''  <section class="screen" id="home">
    <div class="hx hx-l"></div><div class="hx hx-r"></div>
    <div class="h-hud h-tl">SYS / 01</div><div class="h-hud h-tr">NODE / 16</div>
    <div class="h-pill">● 00.1 // FRONTIER.TOWER</div>
    <h1 class="h-head">Where the frontier is<br><span class="hw-word">built</span><span class="caret"></span></h1>
    <div class="h-tower">__TOWER__</div>
    <p class="h-sub">16 floors. Countless founders. One constitution, written from the inside.<br>AI · crypto · biotech · robotics · neurotech · longevity.</p>
    <div class="h-hud h-bl">● LIVE</div><div class="h-hud h-br">37.78°N</div>
  </section>'''

IMAGE_TMPL = '''  <section class="screen" id="__ID__" style="align-items:center;justify-content:center;padding:0;background:__BG__;">
    <img src="__SRC__" alt="Frontier Tower poster" style="width:100%;height:100%;object-fit:contain;display:block;">
  </section>'''

STATS_TMPL = '''  <section class="screen" id="stats">
    <div class="st-eye">[ 02 // BUILT FROM HERE ]</div>
    <div class="st-head">A member-run vertical village.</div>
    <div class="st-sub">16 floors of AI, robotics, biotech, crypto, longevity and the arts — inside a 1908 landmark.</div>
    <div class="st-grid">
      <div><b>450+</b><span>Citizens in the tower</span></div>
      <div><b>500+</b><span>Events in year one</span></div>
      <div><b class="pu">$150m</b><span>Raised by tower founders</span></div>
      <div><b>70K+</b><span>Visitors through the doors</span></div>
    </div>
    <div class="st-foot">frontiertower.io · 995 Market St, San Francisco</div>
  </section>'''

CITIZEN_TMPL = '''  <section class="screen" id="citizen">
    <div class="cz-eye">[ 04 // BECOME A CITIZEN ]</div>
    <h2 class="cz-title">The frontier<br>has an address.</h2>
    <div class="cz-perks"><span>Hundreds of events a year</span><span>Hot desks + conference rooms</span><span>Podcast studio + fitness center</span><span>Open until 2 AM</span><span>Founders on every floor</span></div>
    <div class="cz-foot">
      <div class="cz-qr">__QR__<span>SCAN TO APPLY</span></div>
      <div class="cz-url">APPLY ▸<br>frontiertower.io/apply</div>
    </div>
  </section>'''

MOMENTUM_TMPL = '''  <section class="screen" id="momentum">
    <div class="mo-eye">[ 05 // MOMENTUM ]</div>
    <h2 class="mo-head">The frontier<br>is funded.</h2>
    <div class="mo-big"><b>$150M+</b><span>raised by tower founders in under 18 months.</span></div>
    <div class="mo-tags">AI &middot; Biotech &middot; Neurotech &middot; Robotics &middot; Crypto</div>
    <div class="mo-launch">Now launching <b>Frontier Heroes</b> &mdash; the Tower&rsquo;s own venture arm.</div>
    <div class="mo-proof">
      <span class="mo-proof-eye">RECENTLY IN THE BUILDING</span>
      <span class="mo-proof-name">Boost VC &middot; Adam Draper</span>
      <span class="mo-proof-sub">&ldquo;Backing science fiction since 2012.&rdquo;</span>
    </div>
  </section>'''

NETWORK_TMPL = '''  <section class="screen" id="network">
    <div class="nw-top">
      <div class="nw-label">[ 01 // THE FRONTIERS ]<em>16 floors // one network</em></div>
      <h2 class="nw-head">Where the frontier is.</h2>
      <p class="nw-tag">A member-run vertical village &mdash; 16 floors of AI, robotics, biotech, crypto, longevity and the arts, inside a 1908 landmark.</p>
    </div>
    <div class="nw-diagram">__SVG__</div>
    <div class="nw-bottom">
      <div class="nw-note">Communities, not floors. Every frontier runs across the whole tower.</div>
      <div class="nw-legend"><span class="lg f">Frontiers</span><span class="lg s">Spaces</span><span class="lg e">Events</span></div>
      <div class="nw-foot"><span>Open until 2&nbsp;AM</span><span>Founders on every floor</span><span>frontiertower.io</span></div>
    </div>
  </section>'''

CALENDAR_TMPL = '''  <section class="screen" id="calendar">
    <header class="ft-head">
      <div class="head-main">
        <div class="brand"><div class="logo">ft</div><div class="word">frontiertower</div></div>
        <h1>Frontier Tower SF</h1>
        <div class="meta"><span>San Francisco</span><span class="dot"></span><span id="clock">&nbsp;</span><span class="dot"></span><span>frontiertower.io</span></div>
      </div>
      <div class="qr-card">__CALQR__<span>Scan for events</span></div>
    </header>
    <iframe class="cal" title="Frontier Tower events" src="about:blank" data-src="__EMBED__" referrerpolicy="no-referrer-when-downgrade"></iframe>
  </section>'''

BRAND_TMPL = '''  <section class="screen" id="brand">
    <div class="b-logo">ft</div>
    <h2>Frontier Tower<br>San Francisco</h2>
    <div class="tag">Communities, not floors — every frontier runs across the whole tower.</div>
    <div class="verticals"><span class="chip">Frontier AI</span><span class="chip">Robotics</span><span class="chip">Bio &amp; Neurotech</span><span class="chip">Ethereum &amp; Blockchain</span><span class="chip">Art &amp; Music</span><span class="chip">Other Minds</span></div>
    <div class="b-spaces">+ The Spaceship · Cowork · Private Offices · Podcast + Gym · Lounge</div>
    <div class="url">frontiertower.io</div>
  </section>'''

POSTER_TMPL = '''  <section class="screen" id="poster">
    <div class="po-head">
      <div class="po-brand"><span class="po-logo">ft</span>frontiertower</div>
      <div class="po-loc">[ 995 MARKET ST // SAN FRANCISCO ]</div>
    </div>
    <div class="po-label">[ 00 // FRONTIER.TOWER ]</div>
    <h2 class="po-title"><span class="pu">FRONTIER</span> TOWER</h2>

    <div class="po-stats">
      <div><b>450+</b><span>Citizens in the tower</span></div>
      <div><b>200+</b><span>Events per year</span></div>
      <div><b>$150m</b><span>Raised by founders</span></div>
      <div><b>70K+</b><span>Visitors &amp; network</span></div>
    </div>

    <div class="po-label">[ 01 // THE FRONTIERS ] <em>16 floors // one network</em></div>
    <div class="po-frontiers">
      <span>Frontier AI</span><span>Robotics</span><span>Bio &amp; Neurotech</span><span>Ethereum &amp; Blockchain</span><span>Art &amp; Music</span><span>Other Minds</span><span class="hub">The Spaceship · Events</span>
    </div>
    <div class="po-note">Communities, not floors. Every frontier runs across the whole tower.</div>

    <div class="po-label">[ 03 // CITIZENSHIP GETS YOU ]</div>
    <div class="po-perks"><span>Hundreds of events a year</span><span>Hot desks + conference rooms</span><span>Podcast studio + fitness center</span><span>Open 24/7</span><span>Founders on every floor</span></div>

    <div class="po-cta">
      <div class="po-cta-text">
        <div class="po-cta-label">[ 04 // BECOME A CITIZEN ]</div>
        <div class="po-cta-big">The frontier<br>has an address.</div>
        <div class="po-cta-url">frontiertower.io/apply</div>
      </div>
      <div class="po-qr">__QR__<span>SCAN TO APPLY</span></div>
    </div>
  </section>'''

CSS = r'''
  :root{
    --bg:#0c0e14;--fg:#eef0f5;--muted:#8b93a3;
    --gold:#e3b341;--gold-2:#f0c75e;--crimson:#e2405a;--teal:#3db39e;--cream:#f5ead1;
    --ft-grad:linear-gradient(135deg,#7d5cff 0%,#5a3fe0 55%,#4832c4 100%);
    --font:Inter,-apple-system,"Segoe UI",Roboto,system-ui,sans-serif;
    --mono:ui-monospace,"SFMono-Regular","Roboto Mono",Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box;}
  html,body{height:100%;margin:0;}
  body{background:var(--bg);color:var(--fg);font-family:var(--font);overflow:hidden;}
  .screen{position:fixed;inset:0;display:flex;flex-direction:column;opacity:0;visibility:hidden;transition:opacity .6s ease;}
  .screen.on{opacity:1;visibility:visible;}

  /* shared FT header band (calendar) */
  .ft-head{flex:0 0 auto;background:var(--ft-grad);color:#fff;padding:2.6vw 3vw 2.4vw;display:flex;align-items:flex-start;justify-content:space-between;gap:3vw;}
  .brand{display:flex;align-items:center;gap:1.4vw;}
  .logo{width:5.9vw;height:5.9vw;max-width:72px;max-height:72px;border-radius:1.6vw;background:#fff;color:#5a3fe0;display:grid;place-items:center;font-weight:800;font-size:3.4vw;letter-spacing:-.04em;}
  .word{font-weight:700;font-size:2.8vw;letter-spacing:-.01em;opacity:.96;}
  .ft-head h1{font-size:6vw;font-weight:800;letter-spacing:-.02em;margin:1.8vw 0 .6vw;line-height:1.05;}
  .meta{display:flex;align-items:center;gap:1.6vw;flex-wrap:wrap;font-size:2.5vw;opacity:.9;}
  .dot{width:.7vw;height:.7vw;border-radius:50%;background:currentColor;opacity:.7;}
  #clock{font-variant-numeric:tabular-nums;}
  .qr-card{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;gap:.8vw;background:#fff;border-radius:1.8vw;padding:1.2vw 1.2vw 1vw;box-shadow:0 .4vw 1.6vw rgba(0,0,0,.22);}
  .qr-card svg{width:15vw;max-width:168px;height:auto;display:block;}
  .qr-card span{color:#3a2b6b;font-size:1.9vw;font-weight:700;letter-spacing:.02em;}
  .cal{flex:1 1 auto;border:0;width:100%;background:var(--bg);}

  /* brand slide */
  #brand{align-items:center;justify-content:center;text-align:center;padding:8vw 7vw;background:radial-gradient(120vw 70vw at 50% -10%,rgba(125,92,255,.18),transparent 60%),var(--bg);}
  #brand .b-logo{width:16vw;height:16vw;border-radius:3.4vw;background:var(--ft-grad);display:grid;place-items:center;font-weight:800;font-size:9vw;color:#fff;letter-spacing:-.04em;box-shadow:0 2vw 6vw rgba(90,63,224,.4);}
  #brand h2{font-size:9vw;font-weight:800;letter-spacing:-.02em;margin:6vw 0 2vw;line-height:1.02;}
  #brand .tag{font-size:3.4vw;color:var(--muted);line-height:1.4;max-width:80vw;}
  #brand .verticals{display:flex;flex-wrap:wrap;gap:1.6vw;justify-content:center;margin-top:5vw;}
  #brand .chip{font-family:var(--mono);font-size:2.6vw;border:1px solid rgba(125,92,255,.5);color:#b9a9ff;border-radius:999px;padding:1vw 2.6vw;}
  #brand .b-spaces{margin-top:3.4vw;font-family:var(--mono);font-size:2.2vw;color:var(--muted);letter-spacing:.02em;max-width:84vw;line-height:1.5;}
  #brand .url{margin-top:5vw;font-family:var(--mono);font-size:3vw;color:var(--gold-2);letter-spacing:.04em;}

  /* featured event */
  [id^="evt"]{padding:6vw 6vw 5vw;background:radial-gradient(90vw 60vw at 50% 8%,rgba(227,179,65,.14),transparent 62%),radial-gradient(70vw 50vw at 50% 100%,rgba(226,64,90,.12),transparent 60%),var(--bg);}
  .fx-eyebrow{font-family:var(--mono);font-size:2.6vw;letter-spacing:.22em;text-transform:uppercase;color:var(--gold);display:flex;align-items:center;gap:1.6vw;}
  .fx-eyebrow .live{width:1.6vw;height:1.6vw;border-radius:50%;background:var(--crimson);box-shadow:0 0 0 0 rgba(226,64,90,.6);animation:pulse 2s infinite;}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(226,64,90,.55)}70%{box-shadow:0 0 0 3vw rgba(226,64,90,0)}100%{box-shadow:0 0 0 0 rgba(226,64,90,0)}}
  .fx-cover{margin:4vw auto 0;width:62vw;max-width:520px;aspect-ratio:1/1;border-radius:3vw;background:#000 center/cover no-repeat;border:.4vw solid rgba(227,179,65,.45);box-shadow:0 0 0 .2vw rgba(0,0,0,.6),0 3vw 9vw rgba(0,0,0,.6),0 0 14vw rgba(227,179,65,.12);}
  .fx-title{margin:5vw 0 0;font-size:8.6vw;font-weight:800;line-height:.98;letter-spacing:-.02em;}
  .fx-title .sub{display:block;font-size:5.4vw;color:var(--cream);font-weight:700;margin-top:1.2vw;}
  .fx-badge{display:inline-block;margin-top:3vw;font-family:var(--mono);font-size:2.6vw;font-weight:700;letter-spacing:.1em;color:var(--bg);background:var(--gold);border-radius:999px;padding:1vw 3vw;}
  .fx-when{display:flex;align-items:baseline;gap:3vw;margin-top:5vw;flex-wrap:wrap;}
  .fx-when .d{font-size:7vw;font-weight:800;color:var(--gold-2);letter-spacing:-.01em;line-height:1;}
  .fx-when .t{font-size:5.4vw;font-weight:700;color:var(--fg);}
  .fx-where{margin-top:2.4vw;font-size:3.4vw;color:var(--muted);}
  .fx-where b{color:var(--teal);font-weight:700;}
  .fx-tag{margin-top:4vw;font-size:3.2vw;font-style:italic;color:#cdbf9a;line-height:1.45;max-width:82vw;}
  .fx-foot{margin-top:auto;display:flex;align-items:center;justify-content:space-between;gap:4vw;padding-top:5vw;}
  .fx-host{font-size:3vw;color:var(--muted);line-height:1.4;}
  .fx-host b{color:var(--fg);font-weight:700;}
  .fx-qr{display:flex;flex-direction:column;align-items:center;gap:1vw;background:#fff;border-radius:2.4vw;padding:2.2vw 2.2vw 1.6vw;box-shadow:0 1vw 4vw rgba(0,0,0,.5);}
  .fx-qr svg{width:24vw;max-width:220px;height:auto;display:block;}
  .fx-qr span{color:#0c0e14;font-family:var(--mono);font-size:2.3vw;font-weight:700;letter-spacing:.08em;}

  /* home hero (recreated FT homepage) */
  #home{background:radial-gradient(110vw 70vh at 50% 62%,rgba(125,92,255,.20),transparent 65%),var(--bg);color:var(--fg);padding:7vw 7vw;align-items:center;text-align:center;overflow:hidden;}
  #home::before{content:"";position:absolute;inset:4vw;border:1px dashed rgba(125,92,255,.30);pointer-events:none;}
  .h-hud{position:absolute;font-family:var(--mono);font-size:2.4vw;letter-spacing:.18em;color:rgba(238,240,245,.5);}
  .h-tl{top:6vw;left:7vw;} .h-tr{top:6vw;right:7vw;} .h-bl{bottom:6vw;left:7vw;color:var(--crimson);} .h-br{bottom:6vw;right:7vw;}
  .hx{position:absolute;top:12vw;bottom:12vw;width:7vw;font-family:var(--mono);font-size:2.2vw;line-height:2.1;color:rgba(125,92,255,.20);white-space:pre-wrap;word-break:break-all;overflow:hidden;pointer-events:none;}
  .hx-l{left:3vw;} .hx-r{right:3vw;text-align:right;}
  .h-pill{margin-top:10vw;font-family:var(--mono);font-size:3vw;letter-spacing:.14em;color:#b9a9ff;background:rgba(125,92,255,.14);border:1px solid rgba(125,92,255,.4);border-radius:999px;padding:1.4vw 4vw;}
  .h-head{font-size:11vw;font-weight:800;letter-spacing:-.03em;line-height:1;margin:5vw 0 0;}
  .h-head .hw-word{color:#8b6bff;font-style:italic;}
  .caret{display:inline-block;width:.5vw;height:9vw;background:#8b6bff;margin-left:1vw;vertical-align:-1.4vw;animation:blink 1s step-end infinite;}
  @keyframes blink{50%{opacity:0}}
  .h-tower{width:48vw;max-width:360px;height:40vh;margin:4vw auto 0;filter:drop-shadow(0 0 3vw rgba(125,92,255,.35));}
  .h-sub{font-size:3.4vw;color:var(--muted);line-height:1.5;max-width:82vw;margin:3vw auto 0;}

  /* poster slide — a digital recreation of the elevator poster */
  #poster{--ink:#1b1b2b;--pu:#4a3bd0;--pmut:#6b6b7a;--cream:#f1efe8;
    background:var(--cream);color:var(--ink);padding:5vw 5.5vw;gap:2.4vw;justify-content:flex-start;}
  #poster .po-head{display:flex;align-items:center;justify-content:space-between;}
  .po-brand{display:flex;align-items:center;gap:1.4vw;font-weight:700;font-size:3.2vw;letter-spacing:-.01em;}
  .po-logo{width:6vw;height:6vw;max-width:60px;max-height:60px;border-radius:1.4vw;background:var(--ft-grad);color:#fff;display:grid;place-items:center;font-weight:800;font-size:3.4vw;letter-spacing:-.04em;}
  .po-loc{font-family:var(--mono);font-size:2vw;letter-spacing:.08em;color:var(--pmut);}
  .po-label{font-family:var(--mono);font-size:2.3vw;letter-spacing:.12em;color:var(--pu);font-weight:700;}
  .po-label em{color:var(--pmut);font-style:normal;margin-left:1.2vw;}
  .po-title{font-size:10vw;font-weight:800;letter-spacing:-.03em;line-height:.9;margin:.4vw 0 1vw;}
  .po-title .pu{color:var(--pu);}
  .po-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:2vw;border-top:2px solid var(--ink);border-bottom:2px solid var(--ink);padding:2.4vw 0;}
  .po-stats div{display:flex;flex-direction:column;gap:.4vw;}
  .po-stats b{font-size:5.6vw;font-weight:800;line-height:1;letter-spacing:-.02em;}
  .po-stats div:nth-child(3) b{color:var(--pu);}
  .po-stats span{font-family:var(--mono);font-size:1.7vw;letter-spacing:.04em;color:var(--pmut);text-transform:uppercase;line-height:1.2;}
  .po-frontiers{display:flex;flex-wrap:wrap;gap:1.6vw;}
  .po-frontiers span{font-size:3vw;font-weight:700;color:#fff;background:#6b5bd6;border-radius:999px;padding:1.4vw 3.2vw;}
  .po-frontiers .hub{background:var(--ink);}
  .po-note{font-family:var(--mono);font-size:2vw;color:var(--pmut);letter-spacing:.02em;}
  .po-perks{display:flex;flex-wrap:wrap;gap:1.4vw;}
  .po-perks span{font-size:2.7vw;font-weight:600;color:var(--pu);border:1.5px solid rgba(74,59,208,.4);border-radius:999px;padding:1vw 2.6vw;}
  .po-cta{margin-top:auto;display:flex;align-items:center;justify-content:space-between;gap:4vw;
    background:var(--ft-grad);border-radius:3vw;padding:4vw 4.5vw;color:#fff;}
  .po-cta-label{font-family:var(--mono);font-size:2.1vw;letter-spacing:.12em;opacity:.85;}
  .po-cta-big{font-size:6.4vw;font-weight:800;letter-spacing:-.02em;line-height:1;margin:1.4vw 0 1.6vw;}
  .po-cta-url{font-family:var(--mono);font-size:2.8vw;letter-spacing:.04em;opacity:.95;}
  .po-qr{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;gap:1vw;background:#fff;border-radius:2.2vw;padding:2.2vw 2.2vw 1.6vw;}
  .po-qr svg{width:26vw;max-width:230px;height:auto;display:block;}
  .po-qr span{color:#1b1b2b;font-family:var(--mono);font-size:2vw;font-weight:700;letter-spacing:.08em;}

  /* stats piece — "built from here" */
  #stats{padding:9vw 7vw;justify-content:center;gap:2.6vw;background:radial-gradient(120vw 70vw at 50% 0%,rgba(125,92,255,.14),transparent 60%),var(--bg);}
  .st-eye{font-family:var(--mono);font-size:2.6vw;letter-spacing:.14em;color:#b9a9ff;}
  .st-head{font-size:7.4vw;font-weight:800;letter-spacing:-.02em;line-height:1.0;}
  .st-sub{font-size:3.1vw;color:var(--muted);line-height:1.45;max-width:84vw;}
  .st-grid{display:grid;grid-template-columns:1fr 1fr;gap:5vw 6vw;margin-top:3vw;}
  .st-grid b{display:block;font-size:11vw;font-weight:800;line-height:.95;letter-spacing:-.02em;}
  .st-grid b.pu{color:#8b6bff;}
  .st-grid span{font-family:var(--mono);font-size:2.2vw;letter-spacing:.03em;color:var(--muted);text-transform:uppercase;}
  .st-foot{margin-top:4vw;font-family:var(--mono);font-size:2.4vw;color:var(--gold-2);letter-spacing:.03em;}

  /* momentum piece — funding + venture arm (from the Boost VC visit post) */
  #momentum{padding:9vw 8vw;justify-content:center;gap:2.8vw;background:radial-gradient(120vw 80vw at 50% 100%,rgba(125,92,255,.18),transparent 60%),var(--bg);}
  .mo-eye{font-family:var(--mono);font-size:2.6vw;letter-spacing:.14em;color:#b9a9ff;}
  .mo-head{font-size:9vw;font-weight:800;letter-spacing:-.02em;line-height:.98;margin:0;}
  .mo-big{display:flex;flex-direction:column;gap:.6vw;margin-top:1vw;}
  .mo-big b{font-size:16vw;font-weight:800;line-height:.9;letter-spacing:-.03em;color:#8b6bff;}
  .mo-big span{font-size:3.1vw;color:var(--muted);line-height:1.35;max-width:82vw;}
  .mo-tags{font-family:var(--mono);font-size:2.5vw;letter-spacing:.05em;color:var(--fg);opacity:.82;}
  .mo-launch{font-size:3.6vw;line-height:1.35;font-weight:500;border-left:.8vw solid #7d5cff;padding-left:3vw;margin-top:1vw;}
  .mo-launch b{color:#b9a9ff;font-weight:800;}
  .mo-proof{margin-top:3vw;display:flex;flex-direction:column;gap:1.2vw;border-top:1px solid rgba(255,255,255,.12);padding-top:3.4vw;}
  .mo-proof-eye{font-family:var(--mono);font-size:2.2vw;letter-spacing:.16em;color:var(--muted);}
  .mo-proof-name{font-size:5vw;font-weight:800;letter-spacing:-.01em;}
  .mo-proof-sub{font-family:var(--mono);font-size:2.5vw;color:var(--gold-2);letter-spacing:.02em;}

  /* citizen piece — the apply CTA */
  #citizen{padding:11vw 8vw;justify-content:center;gap:4vw;background:var(--ft-grad);color:#fff;}
  .cz-eye{font-family:var(--mono);font-size:2.8vw;letter-spacing:.14em;opacity:.85;}
  .cz-title{font-size:11vw;font-weight:800;letter-spacing:-.02em;line-height:.98;margin:0;}
  .cz-perks{display:flex;flex-direction:column;gap:2vw;font-size:3.6vw;font-weight:600;}
  .cz-perks span{display:flex;align-items:center;gap:2vw;}
  .cz-perks span::before{content:"▸";color:#d9ccff;}
  .cz-foot{display:flex;align-items:center;gap:5vw;margin-top:3vw;}
  .cz-qr{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;gap:1vw;background:#fff;border-radius:2.4vw;padding:2.4vw 2.4vw 1.8vw;}
  .cz-qr svg{width:30vw;max-width:260px;height:auto;display:block;}
  .cz-qr span{color:#1b1b2b;font-family:var(--mono);font-size:2.2vw;font-weight:700;letter-spacing:.06em;}
  .cz-url{font-family:var(--mono);font-size:3.4vw;font-weight:700;letter-spacing:.02em;line-height:1.3;}

  /* network piece — THE FRONTIERS node diagram */
  #network{background:#f1efe8;color:#1b1b2b;padding:6vw 5vw 5vw;gap:2vw;align-items:center;justify-content:space-between;text-align:center;}
  .nw-top{display:flex;flex-direction:column;align-items:center;gap:1.4vw;width:100%;}
  .nw-label{font-family:var(--mono);font-size:2.4vw;letter-spacing:.1em;color:#4a3bd0;font-weight:700;}
  .nw-label em{color:#6b6b7a;font-style:normal;margin-left:1vw;}
  .nw-head{font-family:Inter,system-ui,sans-serif;font-weight:800;font-size:6.6vw;line-height:1.02;letter-spacing:-.01em;margin:0;text-wrap:balance;}
  .nw-tag{font-family:Inter,system-ui,sans-serif;font-size:2.7vw;line-height:1.4;color:#44444f;max-width:88%;margin:0;text-wrap:balance;}
  .nw-diagram{flex:1 1 auto;width:100%;min-height:0;display:flex;align-items:center;justify-content:center;}
  .nw-diagram svg{max-height:100%;max-width:100%;}
  .nw-bottom{display:flex;flex-direction:column;align-items:center;gap:1.8vw;width:100%;}
  .nw-note{font-family:var(--mono);font-size:2.1vw;color:#6b6b7a;}
  .nw-legend{display:flex;gap:4vw;font-family:var(--mono);font-size:2.1vw;color:#3a3a4a;}
  .nw-legend .lg{display:flex;align-items:center;gap:1.2vw;}
  .nw-legend .lg::before{content:"";width:2.4vw;height:2.4vw;border-radius:50%;flex:0 0 auto;}
  .nw-legend .f::before{background:#6b5bd6;}
  .nw-legend .s::before{background:#dfd9f7;border:1px solid #c3b9f0;}
  .nw-legend .e::before{background:#15121b;border-radius:3px;}
  .nw-foot{display:flex;flex-wrap:wrap;justify-content:center;gap:1vw 2.2vw;font-family:var(--mono);font-size:2vw;color:#8a8a97;}
  .nw-foot span{position:relative;}
  .nw-foot span+span::before{content:"·";position:absolute;left:-1.3vw;color:#c3bfe0;}
'''

SHELL = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Frontier Tower Kiosk</title>
<style>__CSS__</style>
</head>
<body>
__SLIDES__
<script>
  (function(){var el=document.getElementById('clock');if(!el)return;
    function t(){try{el.textContent=new Date().toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZone:'America/Los_Angeles'})+' PDT';}catch(e){el.textContent='';}}
    t();setInterval(t,15000);})();
  (function(){var home=document.getElementById('home');if(!home)return;
    var words=['built','shipped','scaled','funded','alive'],w=home.querySelector('.hw-word'),i=0;
    function on(){return home.classList.contains('on');}
    setInterval(function(){if(!on())return;i=(i+1)%words.length;w.textContent=words[i];},2200);
    function hx(n){var s='',h='0123456789ABCDEF';for(var k=0;k<n;k++){s+=h[Math.floor(Math.random()*16)]+((k%3===2)?'\\n':' ');}return s;}
    var cols=home.querySelectorAll('.hx');function fill(){cols.forEach(function(c){c.textContent=hx(80);});}
    fill();setInterval(function(){if(on())fill();},1500);})();
  var order=__ORDER__,i=0,screens=document.querySelectorAll('.screen');
  function live(o){var t=Date.now();return (!o.until||t<o.until)&&(!o.since||t>=o.since);}
  function nextLive(k){for(var n=0;n<order.length;n++){k=(k+1)%order.length;if(live(order[k]))return k;}return k;}
  // An embedded page (the Luma calendar) is loaded one slide ahead of its own
  // and blanked once it has played, so it is not held in memory all loop long.
  function frames(cur,nxt){document.querySelectorAll('iframe[data-src]').forEach(function(f){
    var id=f.closest('.screen').id,want=(id===cur||id===nxt)?f.getAttribute('data-src'):'about:blank';
    if(f.getAttribute('src')!==want)f.setAttribute('src',want);});}
  function show(){for(var n=0;n<order.length&&!live(order[i]);n++){i=(i+1)%order.length;}
    screens.forEach(function(s){s.classList.remove('on');});
    document.getElementById(order[i].id).classList.add('on');
    frames(order[i].id,order[nextLive(i)].id);
    setTimeout(function(){i=(i+1)%order.length;show();},order[i].ms);}
  show();
</script>
</body>
</html>'''


# ---------------------------------------------------------------- build
def build(conf):
    embed = conf.get("calendar_embed", "")
    slides, order, evn, until, since, ends = [], [], 0, {}, {}, {}   # ends: event url -> end ms
    for item in conf["rotation"]:
        t, ms = item["type"], int(item.get("ms", 15000))
        if t == "home":
            slides.append(HOME_TMPL.replace("__TOWER__", tower_svg()))
            order.append(("home", ms))
        elif t == "brand":
            slides.append(BRAND_TMPL); order.append(("brand", ms))
        elif t == "poster":
            url = item.get("url", "https://frontiertower.io/apply")
            slides.append(POSTER_TMPL.replace("__QR__", qr_svg(url)))
            order.append(("poster", ms))
        elif t == "stats":
            slides.append(STATS_TMPL); order.append(("stats", ms))
        elif t == "network":
            slides.append(NETWORK_TMPL.replace("__SVG__", network_svg()))
            order.append(("network", ms))
        elif t == "momentum":
            slides.append(MOMENTUM_TMPL); order.append(("momentum", ms))
        elif t == "citizen":
            url = item.get("url", "https://frontiertower.io/apply")
            slides.append(CITIZEN_TMPL.replace("__QR__", qr_svg(url)))
            order.append(("citizen", ms))
        elif t == "image":
            iid = item.get("id", "image")
            slides.append(IMAGE_TMPL.replace("__ID__", iid)
                          .replace("__SRC__", item["url"]).replace("__BG__", item.get("bg", "#f1efe8")))
            order.append((iid, ms))
        elif t == "calendar":
            s = (CALENDAR_TMPL.replace("__CALQR__", qr_svg("https://luma.com/frontiertower"))
                              .replace("__EMBED__", embed))
            slides.append(s); order.append(("calendar", ms))
        elif t == "event":
            evn += 1; eid = f"evt{evn}"
            sys.stderr.write(f"  fetching {item['url']} ...\n")
            f = event_fields(item["url"], fetch_event(item["url"]), item)
            subwrap = f'<span class="sub">{f["subtitle"]}</span>' if f["subtitle"] else ""
            badgewrap = f'<div><span class="fx-badge">{f["badge"]}</span></div>' if f["badge"] else ""
            tagwrap = f'<div class="fx-tag">“{f["tagline"]}”</div>' if f["tagline"] else ""
            s = (EVENT_TMPL.replace("__ID__", eid).replace("__COVER__", f["cover"])
                 .replace("__TITLE__", f["title"]).replace("__SUBWRAP__", subwrap)
                 .replace("__BADGEWRAP__", badgewrap)
                 .replace("__WHEN_DATE__", f["when_date"]).replace("__WHEN_TIME__", f["when_time"])
                 .replace("__WHERE__", f["where"]).replace("__TAGWRAP__", tagwrap)
                 .replace("__HOST__", f["host"]).replace("__QR__", qr_svg(f["rsvp"])))
            slides.append(s); order.append((eid, ms)); until[eid] = f["until"]
            ends[item["url"]] = f["until"]
            if item.get("after"):            # stay hidden until that (earlier-listed) event has ended
                if item["after"] not in ends:
                    sys.exit(f"error: 'after' must name an event listed earlier: {item['after']}")
                since[eid] = ends[item["after"]]
        else:
            sys.stderr.write(f"  skipping unknown slide type: {t}\n")
    order_js = "[" + ",".join(f'{{id:"{i}",ms:{m}' + (f',until:{until[i]}' if i in until else '')
                              + (f',since:{since[i]}' if i in since else '') + '}'
                              for i, m in order) + "]"
    return (SHELL.replace("__CSS__", CSS)
                 .replace("__SLIDES__", "\n".join(slides))
                 .replace("__ORDER__", order_js))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", default=CONF)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    conf = json.load(open(a.conf, encoding="utf-8"))
    html = build(conf)
    open(a.out, "w", encoding="utf-8").write(html)
    sys.stderr.write(f"wrote {a.out} ({len(html)} bytes, {len(conf['rotation'])} slides)\n")


if __name__ == "__main__":
    main()
