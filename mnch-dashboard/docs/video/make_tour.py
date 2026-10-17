"""Record the Shiny for Python tour, in the style of the Power BI tour.

    python -m shiny run app.py --port 8795      # in mnch-dashboard/, then:
    python docs/video/make_tour.py [--url http://127.0.0.1:8795]

Writes media/shiny-tour.mp4 (with title and end cards) and
media/shiny-tour-body.mp4 (the screen part only, used by make_linkedin.py).
Captions only describe what the app actually shows; see docs/VIDEO.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recorder import H, OVERLAY_JS, W, Tour, fresh_dir  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "media"
PLUM, PINK = "#4a1942", "#ffc0cb"
CARD_BG = "linear-gradient(165deg, #4a1942 0%, #2c0e27 100%)"
HEART = f"""<div style="width:96px;height:96px;border-radius:22px;background:{PINK};display:grid;place-items:center">
<svg width="58" height="58" viewBox="0 0 24 24" fill="none" stroke="{PLUM}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
<path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"/></svg></div>"""


def title_card() -> str:
    return f"""{HEART}
<div style="font-size:76px;font-weight:600;margin-top:14px">DHIS2 MNCH Dashboard</div>
<div style="font-size:36px;color:#f3d5e3">Shiny for Python edition · a two-minute tour</div>
<div style="font-size:27px;color:#e7b9d3;margin-top:10px">Live maternal and child health data from DHIS2, plus a facility risk forecast</div>"""


def end_card() -> str:
    return f"""{HEART}
<div style="font-size:72px;font-weight:600;margin-top:10px">That's the tour</div>
<div style="font-size:30px;color:#f3d5e3">Shiny for Python + React (shinyreact) · pandas · numpy logistic regression</div>
<div style="font-size:30px;color:#f3d5e3">Same DHIS2 queries and measures as the Power BI report</div>
<div style="font-size:24px;color:#e7b9d3;margin-top:18px;max-width:1400px;line-height:1.45">For education and demonstration only. Demo data from the DHIS2 play server (Sierra Leone):
not evidence of real facility performance. The risk model is not validated for real-world decisions.</div>"""


def run(url: str) -> None:
    frames = fresh_dir(MEDIA / "_frames")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": W, "height": H}, reduced_motion="reduce")
        page.goto(url + "/#overview")
        page.evaluate("localStorage.setItem('mnch-theme','light')")
        page.reload()
        page.wait_for_selector(".kpis", timeout=90000)
        page.wait_for_timeout(2000)
        page.evaluate(OVERLAY_JS)
        page.evaluate("vt.theme('rgba(74,25,66,0.95)', '#ffc0cb', '#ffc0cb')")
        t = Tour(page, frames)

        def go(label: str, name: str, section: str, caption: str) -> None:
            t.no_caption()
            if t.cam != (1.0, 0.0, 0.0) or t.spot_rect:
                t.focus(None, seconds=0.8)
            t.move_to(".rail-nav button", nth=["overview", "districts", "actions", "risk", "connection"].index(name), seconds=0.9)
            t.click_effect()
            page.locator(".rail-nav button", has_text=label).click()
            page.mouse.move(2, 2)
            page.wait_for_selector(f".page.{name}", timeout=60000)
            page.wait_for_timeout(1300)
            t.caption(section, caption)
            t.hold(1.6)
            t.hide_cursor()

        # ---- title card
        t.card(title_card(), CARD_BG, hold=3.6, fade_in=0.0, fade_out=0.7)
        title_end = len(t.shots)

        # ---- 1 · overview
        t.caption("1 · Overview", "Same DHIS2 data and measures as the Power BI report")
        t.hold(2.4)
        t.focus(".kpis")
        t.caption("1 · Overview", "Six indicators against target, each with a 12-month trend")
        t.hold(2.8)
        t.focus(".slicers", zoom=False)
        t.caption("Filters", "Filter by district, chiefdom or month: every page follows")
        t.move_to(".slicer", nth=0, seconds=0.7)
        t.click_effect()
        page.select_option(".slicer >> nth=0 >> select", "Bo")
        page.wait_for_timeout(1600)
        t.focus(".kpis", zoom=False, seconds=0.6)
        t.caption("Filters", "District: Bo. The indicators recalculate from the DHIS2 numbers")
        t.hold(2.6)
        page.select_option(".slicer >> nth=0 >> select", "All")
        page.wait_for_timeout(1600)
        t.hide_cursor()
        t.focus(".span-trend", nth=0, zoom=False)
        r = t.js("([s,n]) => vt.rect(s,n)", ".span-trend svg", 0)
        hx, hy = r["x"] + r["w"] * 0.62, r["y"] + r["h"] * 0.4
        page.mouse.move(hx, hy)
        page.wait_for_timeout(400)
        t.cur = (hx, hy)
        t.js("([x,y]) => vt.cursor(x,y,1)", hx, hy)
        t.caption("1 · Overview", "Hover any chart for the exact values")
        t.hold(2.6)
        page.mouse.move(5, 5)
        t.hide_cursor()
        t.focus(".span-trend", nth=1)
        t.caption("1 · Overview", "Written findings update with your filters")
        t.hold(2.6)
        t.focus(".span-side")
        t.caption("1 · Overview", "Districts ranked: lowest Penta 3 coverage first")
        t.hold(2.4)

        # ---- 2 · districts
        go("Districts", "districts", "2 · Districts", "Open Districts")
        t.focus(".page.districts > .card", zoom=False)
        t.caption("2 · Districts", "A scorecard for every chiefdom, shaded against target")
        t.hold(2.6)
        t.focus(".score tfoot", smax=1.5)
        t.caption("2 · Districts", "A Total row that follows the filters")
        t.hold(2.4)
        t.focus(".side-stack .card", nth=0)
        t.caption("2 · Districts", "Where most children missed their third Penta dose")
        t.hold(2.4)

        # ---- 3 · actions
        go("Actions", "actions", "3 · Actions", "Open Actions")
        t.focus(".page.actions > .card", nth=0)
        t.caption("3 · Actions", "Recommended actions, with the numbers behind them")
        t.hold(2.8)
        t.focus(".page.actions > .card", nth=1)
        t.caption("3 · Actions", "Top left needs most help: low coverage and high dropout")
        t.hold(2.6)
        t.focus(".page.actions > .card", nth=3)
        t.caption("3 · Actions", "Coverage above 100%: check the population estimate first")
        t.hold(2.4)

        # ---- 4 · risk forecast (new)
        go("Risk forecast", "risk", "4 · Risk forecast · new", "Which facilities may fall behind next quarter?")
        t.focus(".risk-head", zoom=False)
        t.caption("4 · Risk forecast", "Outcome: Penta 3 coverage below 70% in the next 3 months")
        t.hold(2.8)
        t.focus(".risk-tiles")
        t.caption("4 · Risk forecast", "Risk estimates for the 226 facilities that report Penta doses")
        t.hold(2.8)
        t.focus(".risk-grid > .card", nth=0, smax=1.25)
        t.caption("4 · Risk forecast", "Each dot is a facility, coloured by its estimated risk")
        t.hold(2.6)
        t.focus(None, seconds=0.7)
        t.move_to(".risk-table tbody tr", nth=0, seconds=0.8)
        t.click_effect()
        page.locator(".risk-table tbody tr").first.click()
        page.mouse.move(2, 2)
        page.wait_for_selector(".drawer")
        page.wait_for_timeout(500)
        t.hide_cursor()
        t.focus(".drawer", zoom=False)
        t.caption("4 · Risk forecast", "Every estimate comes with the reasons behind it")
        t.hold(3.0)
        page.locator(".drawer .close").click()
        page.mouse.move(2, 2)
        page.wait_for_timeout(400)
        t.focus(None, seconds=0.5)
        t.move_to(".seg button", nth=1, seconds=0.7)
        t.click_effect()
        page.locator(".seg button").nth(1).click()
        page.mouse.move(2, 2)
        page.wait_for_timeout(1800)
        t.hide_cursor()
        t.focus(".risk-head", zoom=False)
        t.caption("4 · Risk forecast", "Second outcome: ANC 1 to 4 dropout above 50%")
        t.hold(2.6)
        t.focus(".model-card", smax=1.2)
        t.caption("4 · Risk forecast", "Tested on an unseen quarter against 'same as last quarter'")
        t.hold(3.2)
        t.caption("4 · Risk forecast", "A planning aid for follow-up visits, not a verdict")
        t.hold(2.4)

        # ---- 5 · connection
        go("Connection", "connection", "5 · Connection", "Open Connection")
        t.focus(".src-tiles")
        t.caption("5 · Connection", "Which DHIS2 server, which version, last refresh")
        t.hold(2.6)
        t.focus(".catalogue")
        t.caption("5 · Connection", "The same indicator catalogue as the Power BI model")
        t.hold(2.6)
        t.focus(".connected", zoom=False)
        t.caption("5 · Connection", "Refresh pulls fresh data from DHIS2 on demand")
        t.hold(2.4)
        t.no_caption()
        t.focus(None, seconds=0.6)
        body_end = len(t.shots)

        # ---- end card
        t.card(end_card(), CARD_BG, hold=4.5, fade_in=0.6, fade_out=0.0)
        browser.close()

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    full, body = MEDIA / "shiny-tour.mp4", MEDIA / "shiny-tour-body.mp4"
    t.encode(full, ff)
    body_tour = Tour(None, frames, shots=t.shots[title_end:body_end])
    body_tour.encode(body, ff)
    print(f"{full} ({t.duration:.1f} s), {body} ({body_tour.duration:.1f} s), {len(t.shots)} frames")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8795")
    run(ap.parse_args().url.rstrip("/"))
