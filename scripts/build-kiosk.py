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
from datetime import datetime
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

    addr = (ev.get("geo_address_info") or {}).get("address", "")
    venue = addr.split("@", 1)[1] if "@" in addr else addr
    venue = re.split(r"\s*995\s*Market", venue)[0].strip()
    where = (f"<b>{esc(venue)}</b> · 995 Market St, San Francisco" if venue
             else "<b>Frontier Tower</b> · 995 Market St, San Francisco")

    hosts = [h["name"] for h in data.get("hosts", [])]
    primary = next((h for h in hosts if h.lower() != "frontier tower"), "")
    host = (f"Hosted by <b>{esc(primary)}</b><br>&amp; Frontier Tower" if primary
            else "Hosted by <b>Frontier Tower</b>")

    cover = transform_cover(ov.get("cover") or ev.get("cover_url", ""))
    return dict(title=esc(title), subtitle=esc(subtitle), badge=esc(badge),
                when_date=esc(when_date), when_time=esc(when_time), where=where,
                host=host, cover=cover, tagline=esc(ov.get("tagline", "")), rsvp=url)


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

CALENDAR_TMPL = '''  <section class="screen" id="calendar">
    <header class="ft-head">
      <div class="head-main">
        <div class="brand"><div class="logo">ft</div><div class="word">frontiertower</div></div>
        <h1>Frontier Tower SF</h1>
        <div class="meta"><span>San Francisco</span><span class="dot"></span><span id="clock">&nbsp;</span><span class="dot"></span><span>frontiertower.io</span></div>
      </div>
      <div class="qr-card">__CALQR__<span>Scan for events</span></div>
    </header>
    <iframe class="cal" title="Frontier Tower events" src="__EMBED__" referrerpolicy="no-referrer-when-downgrade"></iframe>
  </section>'''

BRAND_TMPL = '''  <section class="screen" id="brand">
    <div class="b-logo">ft</div>
    <h2>Frontier Tower<br>San Francisco</h2>
    <div class="tag">16 floors. Countless founders. One constitution, written from the inside.</div>
    <div class="verticals"><span class="chip">AI</span><span class="chip">crypto</span><span class="chip">biotech</span><span class="chip">robotics</span><span class="chip">neurotech</span><span class="chip">longevity</span></div>
    <div class="url">frontiertower.io</div>
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
  #brand .url{margin-top:7vw;font-family:var(--mono);font-size:3vw;color:var(--gold-2);letter-spacing:.04em;}

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
  #home{background:#f6f7fb;color:#15171e;padding:7vw 7vw;align-items:center;text-align:center;overflow:hidden;}
  #home::before{content:"";position:absolute;inset:4vw;border:1px dashed rgba(90,63,224,.28);pointer-events:none;}
  .h-hud{position:absolute;font-family:var(--mono);font-size:2.4vw;letter-spacing:.18em;color:rgba(21,23,30,.55);}
  .h-tl{top:6vw;left:7vw;} .h-tr{top:6vw;right:7vw;} .h-bl{bottom:6vw;left:7vw;color:var(--crimson);} .h-br{bottom:6vw;right:7vw;}
  .hx{position:absolute;top:12vw;bottom:12vw;width:7vw;font-family:var(--mono);font-size:2.2vw;line-height:2.1;color:rgba(90,63,224,.14);white-space:pre-wrap;word-break:break-all;overflow:hidden;pointer-events:none;}
  .hx-l{left:3vw;} .hx-r{right:3vw;text-align:right;}
  .h-pill{margin-top:10vw;font-family:var(--mono);font-size:3vw;letter-spacing:.14em;color:#5a3fe0;background:rgba(125,92,255,.1);border:1px solid rgba(125,92,255,.3);border-radius:999px;padding:1.4vw 4vw;}
  .h-head{font-size:11vw;font-weight:800;letter-spacing:-.03em;line-height:1;margin:5vw 0 0;}
  .h-head .hw-word{color:#5a3fe0;font-style:italic;}
  .caret{display:inline-block;width:.5vw;height:9vw;background:#5a3fe0;margin-left:1vw;vertical-align:-1.4vw;animation:blink 1s step-end infinite;}
  @keyframes blink{50%{opacity:0}}
  .h-tower{width:48vw;max-width:360px;height:40vh;margin:4vw auto 0;}
  .h-sub{font-size:3.4vw;color:#4a505c;line-height:1.5;max-width:82vw;margin:3vw auto 0;}
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
    setInterval(function(){i=(i+1)%words.length;w.textContent=words[i];},2200);
    function hx(n){var s='',h='0123456789ABCDEF';for(var k=0;k<n;k++){s+=h[Math.floor(Math.random()*16)]+((k%3===2)?'\\n':' ');}return s;}
    var cols=home.querySelectorAll('.hx');function fill(){cols.forEach(function(c){c.textContent=hx(80);});}
    fill();setInterval(fill,1500);})();
  var order=__ORDER__,i=0,screens=document.querySelectorAll('.screen');
  function show(){screens.forEach(function(s){s.classList.remove('on');});
    document.getElementById(order[i].id).classList.add('on');
    setTimeout(function(){i=(i+1)%order.length;show();},order[i].ms);}
  show();
</script>
</body>
</html>'''


# ---------------------------------------------------------------- build
def build(conf):
    embed = conf.get("calendar_embed", "")
    slides, order, evn = [], [], 0
    for item in conf["rotation"]:
        t, ms = item["type"], int(item.get("ms", 15000))
        if t == "home":
            slides.append(HOME_TMPL.replace("__TOWER__", tower_svg()))
            order.append(("home", ms))
        elif t == "brand":
            slides.append(BRAND_TMPL); order.append(("brand", ms))
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
            slides.append(s); order.append((eid, ms))
        else:
            sys.stderr.write(f"  skipping unknown slide type: {t}\n")
    order_js = "[" + ",".join(f'{{id:"{i}",ms:{m}}}' for i, m in order) + "]"
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
