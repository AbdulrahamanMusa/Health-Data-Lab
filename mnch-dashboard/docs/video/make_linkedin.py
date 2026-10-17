"""Join the Power BI tour and the Shiny tour into one LinkedIn film.

    python docs/video/make_linkedin.py

Needs media/shiny-tour-body.mp4 (from make_tour.py) and the Power BI tour
video. Writes media/dhis2-interoperability-linkedin.mp4 and a thumbnail.
Cards share one layout (the Power BI tour's title card): navy for Power BI,
plum for Shiny, so viewers always know which application they are watching.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_tour import HEART  # noqa: E402  (the plum/pink heart tile)
from recorder import FPS, H, W, fresh_dir  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "media"
PBI_TOUR = ROOT.parents[1] / "PowerBI_NCD_DHIS2" / "DHIS2 Demo" / "DHIS2 MNCH Dashboard - tour.mp4"
SHINY_BODY = MEDIA / "shiny-tour-body.mp4"
POST_URL = "am-datasolution.com/posts/dhis2-interoperability-power-bi-shiny"

NAVY = "linear-gradient(165deg, #0f2747 0%, #0a1d38 100%)"
PLUM = "linear-gradient(165deg, #4a1942 0%, #2c0e27 100%)"
SPLIT = "linear-gradient(110deg, #0f2747 0%, #0f2747 49.9%, #4a1942 50.1%, #4a1942 100%)"
BLUE_HEART = HEART.replace("#ffc0cb", "#2a78d6").replace('stroke="#4a1942"', 'stroke="#ffffff"')

BASE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;width:1920px;height:1080px;overflow:hidden;font-family:"Segoe UI",sans-serif;color:#fff}
.c{width:1920px;height:1080px;display:grid;place-content:center;justify-items:center;text-align:center;gap:18px;background:BG}
.t{font-size:76px;font-weight:600;margin-top:12px}.s{font-size:36px;color:SUB}.l{font-size:28px;color:LINE;max-width:1500px;line-height:1.45}
.k{font-size:26px;letter-spacing:.08em;text-transform:uppercase;color:KICK}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:0;width:1920px;height:1080px}
.col{display:grid;align-content:center;justify-items:center;gap:20px;padding:0 90px;text-align:center}
.col .t{font-size:54px}.col .l{font-size:29px}
ul{margin:8px 0 0;padding:0;list-style:none;font-size:29px;line-height:1.55;color:LINE}
.dis{max-width:1560px;text-align:left;font-size:27px;line-height:1.5;color:#e9eef6}
.dis li{margin:0 0 12px;padding-left:28px;position:relative}.dis li:before{content:"";position:absolute;left:0;top:17px;width:10px;height:10px;border-radius:50%;background:#ffc0cb}
</style></head><body>BODY</body></html>"""


def page(body: str, bg: str, sub="#cfe0f7", line="#9fb3cf", kick="#6da7ec") -> str:
    return BASE.replace("BG", bg).replace("SUB", sub).replace("LINE", line).replace("KICK", kick).replace("BODY", body)


CARDS = {
    "intro": (
        page(
            f"""<div class="c">{BLUE_HEART.replace('#2a78d6', 'linear-gradient(135deg,#2a78d6 50%,#ffc0cb 50%)')}
<div class="t">From dashboards to risk prediction</div>
<div class="s">DHIS2 interoperability with Power BI and Shiny for Python</div>
<div class="l" style="margin-top:8px">One DHIS2 source, two ways to turn routine health data into decisions</div></div>""",
            SPLIT,
        ),
        6.0,
    ),
    "part1": (
        page(
            f"""<div class="c">{BLUE_HEART}<div class="k" style="margin-top:12px">Part 1</div>
<div class="t" style="margin-top:0">DHIS2 + Power BI</div>
<div class="s">Descriptive analytics: what has happened, and where</div></div>""",
            NAVY,
        ),
        3.8,
    ),
    "part2": (
        page(
            f"""<div class="c">{HEART}<div class="k" style="margin-top:12px">Part 2</div>
<div class="t" style="margin-top:0">DHIS2 + Shiny for Python</div>
<div class="s">The same dashboard, plus risk prediction: where problems may arise next</div></div>""",
            PLUM,
            sub="#f3d5e3",
            line="#e7b9d3",
            kick="#ffc0cb",
        ),
        3.8,
    ),
    "compare": (
        page(
            f"""<div class="cols">
<div class="col" style="background:#0f2747">{BLUE_HEART}<div class="t">Power BI</div><div class="l" style="color:#cfe0f7">Understand what has happened</div>
<ul><li>Live DHIS2 connection (Power Query)</li><li>Coverage, dropout, reporting by chiefdom</li><li>Written findings and recommended actions</li></ul></div>
<div class="col" style="background:#4a1942">{HEART}<div class="t">Shiny for Python</div><div class="l" style="color:#f3d5e3">Investigate where problems may arise</div>
<ul style="color:#e7b9d3"><li>The same measures, rebuilt in Python</li><li>Facility-level risk estimates (logistic regression)</li><li>Reasons for every estimate, tested on an unseen quarter</li></ul></div></div>""",
            "#0f2747",
        ),
        7.5,
    ),
    "disclaimer": (
        page(
            """<div class="c" style="gap:26px"><div class="k" style="color:#ffc0cb">For education and demonstration only</div>
<ul class="dis">
<li>Data come from the public DHIS2 demo database (Sierra Leone). They are not evidence of current real-world facility performance.</li>
<li>The risk model shows one possible analytical approach. It is not a validated clinical or operational decision-making system.</li>
<li>Its estimates depend on data quality, the chosen variables, model assumptions and validation.</li>
<li>Real-world use would need further validation, governance and interpretation by qualified public health staff.</li>
</ul></div>""",
            "linear-gradient(165deg,#1b1530 0%,#120d22 100%)",
        ),
        9.0,
    ),
    "close": (
        page(
            f"""<div class="c">{BLUE_HEART.replace('#2a78d6', 'linear-gradient(135deg,#2a78d6 50%,#ffc0cb 50%)')}
<div class="t">Interoperable data, better-informed decisions</div>
<div class="s">Read the full project story</div>
<div class="l" style="color:#fff;font-size:32px">{POST_URL}</div>
<div class="l" style="font-size:24px;margin-top:10px">Demo data: DHIS2 play server (Sierra Leone) · Power BI · Shiny for Python + React · pandas · numpy</div></div>""",
            SPLIT,
        ),
        5.0,
    ),
}


def run() -> None:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    work = fresh_dir(MEDIA / "_linkedin")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": W, "height": H})
        for name, (html, _) in CARDS.items():
            (work / f"{name}.html").write_text(html, encoding="utf-8")
            pg.goto((work / f"{name}.html").resolve().as_uri())
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(work / f"{name}.png"))
        b.close()

    norm = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p"
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-an"]

    def card_clip(name: str) -> Path:
        secs = CARDS[name][1]
        out = work / f"{name}.mp4"
        vf = f"{norm},fade=t=in:st=0:d=0.5,fade=t=out:st={secs - 0.5}:d=0.5"
        subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-t", str(secs), "-i", str(work / f"{name}.png"), "-vf", vf, *enc, str(out)], check=True)
        return out

    def video_clip(src: Path, name: str) -> Path:
        out = work / f"{name}.mp4"
        probe = subprocess.run([ff, "-i", str(src)], capture_output=True, text=True).stderr
        hh, mm, ss = probe.split("Duration: ")[1].split(",")[0].split(":")
        dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
        vf = f"{norm},fade=t=in:st=0:d=0.4,fade=t=out:st={dur - 0.4:.2f}:d=0.4"
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, *enc, str(out)], check=True)
        return out

    order = [card_clip("intro"), card_clip("part1"), video_clip(PBI_TOUR, "pbi"), card_clip("part2"), video_clip(SHINY_BODY, "shiny"), card_clip("compare"), card_clip("disclaimer"), card_clip("close")]
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in order), encoding="utf-8")
    final = MEDIA / "dhis2-interoperability-linkedin.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)], check=True, cwd=work)
    (MEDIA / "linkedin-thumbnail.png").write_bytes((work / "intro.png").read_bytes())
    probe = subprocess.run([ff, "-i", str(final)], capture_output=True, text=True).stderr
    print(final, probe.split("Duration: ")[1].split(",")[0], f"{final.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    run()
