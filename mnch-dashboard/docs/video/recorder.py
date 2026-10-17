"""Frame-accurate screen tours of a web app, in the style of the Power BI tour.

Drives the real app in Edge (Playwright) and adds overlays in the page: a
spotlight that dims everything except one visual, a caption pill, a cursor
and full-screen title cards. Each frame is a screenshot, so the video is
sharp; still moments are a single frame held for their duration.

ffmpeg comes from the imageio-ffmpeg package (pip install imageio-ffmpeg).
"""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

W, H, FPS = 1920, 1080, 30

OVERLAY_JS = r"""
(() => {
  if (window.vt) return;
  const root = document.createElement('div');
  root.id = 'vt-root';
  root.innerHTML = `
    <div id="vt-spot"></div>
    <div id="vt-cap"><span id="vt-cap-label"></span><span id="vt-cap-text"></span></div>
    <div id="vt-card"></div>
    <svg id="vt-cursor" width="34" height="34" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.6 14.8 L11.7 21.5 L14.6 20.2 L11.6 13.6 L17.8 13.6 Z" fill="#fff" stroke="#111" stroke-width="1.3" stroke-linejoin="round"/></svg>
    <div id="vt-ring"></div>`;
  document.body.appendChild(root);
  const css = document.createElement('style');
  css.textContent = `
    html, body { overflow: hidden !important; }
    #app-root { transform-origin: 0 0; will-change: transform; }
    #vt-root { position: fixed; inset: 0; z-index: 99999; pointer-events: none; font-family: "Segoe UI", sans-serif; }
    #vt-spot { position: absolute; border: 4px solid #2a78d6; border-radius: 14px; box-shadow: 0 0 0 4000px rgba(15, 26, 50, 0.42); opacity: 0; }
    #vt-cap { position: absolute; left: 50%; bottom: 44px; transform: translateX(-50%); width: max-content; display: grid; justify-items: center; gap: 4px;
              padding: 18px 54px 22px; border-radius: 26px; background: var(--vt-cap-bg); color: #fff; opacity: 0; max-width: 1700px; text-align: center;
              box-shadow: 0 18px 50px rgba(0,0,0,.28); }
    #vt-cap-label { font-size: 25px; letter-spacing: .04em; color: var(--vt-cap-label); text-transform: uppercase; }
    #vt-cap-text { font-size: 38px; font-weight: 600; line-height: 1.2; }
    #vt-cap.top { bottom: auto; top: 44px; }
    #vt-card { position: absolute; inset: 0; display: grid; place-content: center; justify-items: center; text-align: center; gap: 18px; opacity: 0; color: #fff; }
    #vt-cursor { position: absolute; left: 0; top: 0; opacity: 0; filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); }
    #vt-ring { position: absolute; width: 10px; height: 10px; border-radius: 50%; border: 3px solid var(--vt-ring); opacity: 0; transform: translate(-50%, -50%); }`;
  document.head.appendChild(css);
  const app = () => document.getElementById('app-root');
  const cam = { s: 1, tx: 0, ty: 0 };
  window.vt = {
    theme(capBg, capLabel, ring) { root.style.setProperty('--vt-cap-bg', capBg); root.style.setProperty('--vt-cap-label', capLabel); root.style.setProperty('--vt-ring', ring); },
    camera(s, tx, ty) { Object.assign(cam, { s, tx, ty }); app().style.transform = `translate(${tx}px, ${ty}px) scale(${s})`; },
    // Untransformed page rectangle of an element (whatever the camera is doing).
    rect(sel, nth = 0) {
      const el = document.querySelectorAll(sel)[nth];
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: (r.left - cam.tx) / cam.s, y: (r.top - cam.ty) / cam.s, w: r.width / cam.s, h: r.height / cam.s };
    },
    pageHeight() { return Math.max(app().scrollHeight, innerHeight); },
    spot(r, o) {
      const s = document.getElementById('vt-spot');
      if (!r) { s.style.opacity = 0; return; }
      const p = 8;
      Object.assign(s.style, { left: r.x - p + 'px', top: r.y - p + 'px', width: r.w + 2 * p + 'px', height: r.h + 2 * p + 'px', opacity: o });
    },
    capTop(on) { document.getElementById('vt-cap').classList.toggle('top', !!on); },
    caption(label, text, o) {
      document.getElementById('vt-cap-label').textContent = label;
      document.getElementById('vt-cap-text').textContent = text;
      document.getElementById('vt-cap').style.opacity = o;
    },
    card(html, bg, o) { const c = document.getElementById('vt-card'); if (html !== null) c.innerHTML = html; c.style.background = bg; c.style.opacity = o; },
    cursor(x, y, o) { Object.assign(document.getElementById('vt-cursor').style, { left: x - 4 + 'px', top: y - 2 + 'px', opacity: o }); },
    ring(x, y, k) { const r = document.getElementById('vt-ring'); const d = 10 + 60 * k; Object.assign(r.style, { left: x + 'px', top: y + 'px', width: d + 'px', height: d + 'px', opacity: k > 0 && k < 1 ? 1 - k : 0 }); },
  };
})();
"""


def ease(k: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, k)))


@dataclass
class Shot:
    path: Path
    seconds: float


@dataclass
class Tour:
    page: object  # playwright Page
    frames: Path
    shots: list = field(default_factory=list)
    cam: tuple = (1.0, 0.0, 0.0)
    cur: tuple = (W / 2, H / 2)
    caption_state: tuple = ("", "", 0.0)
    spot_rect: dict | None = None

    # -- low level
    def js(self, expr: str, *args):
        return self.page.evaluate(expr, list(args)) if args else self.page.evaluate(expr)

    def shot(self, seconds: float) -> None:
        p = self.frames / f"f{len(self.shots):05d}.png"
        self.page.screenshot(path=str(p))
        self.shots.append(Shot(p, seconds))

    def hold(self, seconds: float) -> None:
        self.shot(seconds)

    def animate(self, seconds: float, step) -> None:
        n = max(1, round(seconds * FPS))
        for i in range(1, n + 1):
            step(ease(i / n))
            self.shot(1 / FPS)

    # -- camera
    def camera_for(self, r: dict, margin: float = 70, smax: float = 1.55) -> tuple:
        ph = self.js("vt.pageHeight()")
        s = max(1.0, min(smax, W / (r["w"] + 2 * margin), H / (r["h"] + 2 * margin + 150)))
        cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
        tx = W / 2 - s * cx
        ty = (H - 150) / 2 - s * cy  # leave room for the caption pill
        tx = min(0, max(W - s * W, tx))
        ty = min(0, max(H - s * ph, ty))
        return (s, tx, ty)

    def _apply(self, cam, spot_r, spot_o):
        s, tx, ty = cam
        self.js("([s,tx,ty]) => vt.camera(s,tx,ty)", s, tx, ty)
        if spot_r:
            v = {"x": spot_r["x"] * s + tx, "y": spot_r["y"] * s + ty, "w": spot_r["w"] * s, "h": spot_r["h"] * s}
            self.js("([r,o]) => vt.spot(r,o)", v, spot_o)
        else:
            self.js("vt.spot(null, 0)")

    def focus(self, sel: str | None, nth: int = 0, seconds: float = 1.1, zoom: bool = True, smax: float = 1.55) -> None:
        """Move the camera to an element and spotlight it (sel=None: back to the full page)."""
        r = self.js("([s,n]) => vt.rect(s,n)", sel, nth) if sel else None
        target = self.camera_for(r, smax=smax) if (r and zoom) else (1.0, 0.0, 0.0)
        a = self.cam
        old_r, new_r = self.spot_rect, r

        def step(k):
            cam = tuple(a[i] + (target[i] - a[i]) * k for i in range(3))
            if new_r:
                if old_r:
                    rr = {key: old_r[key] + (new_r[key] - old_r[key]) * k for key in new_r}
                    self._apply(cam, rr, 1)
                else:
                    self._apply(cam, new_r, k)
            elif old_r:
                self._apply(cam, old_r, 1 - k)
            else:
                self._apply(cam, None, 0)

        self.animate(seconds, step)
        self.cam, self.spot_rect = target, new_r

    # -- captions and cards
    def caption(self, label: str, text: str, seconds: float = 0.35) -> None:
        old = self.caption_state
        if old[2] > 0 and (old[0], old[1]) != (label, text):
            self.animate(0.2, lambda k: self.js("([l,t,o]) => vt.caption(l,t,o)", old[0], old[1], 1 - k))
        # Put the caption at the top when the spotlit visual reaches the bottom of the screen.
        top = False
        if self.spot_rect:
            s, _tx, ty = self.cam
            top = (self.spot_rect["y"] + self.spot_rect["h"]) * s + ty > H - 230
        self.js("([t]) => vt.capTop(t)", top)
        self.animate(seconds, lambda k: self.js("([l,t,o]) => vt.caption(l,t,o)", label, text, k))
        self.caption_state = (label, text, 1.0)

    def no_caption(self) -> None:
        l, t, o = self.caption_state
        if o > 0:
            self.animate(0.25, lambda k: self.js("([l,t,o]) => vt.caption(l,t,o)", l, t, 1 - k))
        self.caption_state = ("", "", 0.0)

    def card(self, html: str, bg: str, hold: float, fade_in: float = 0.0, fade_out: float = 0.6) -> None:
        self.js("([h,b]) => vt.card(h,b,0)", html, bg)
        if fade_in:
            self.animate(fade_in, lambda k: self.js("([b,o]) => vt.card(null,b,o)", bg, k))
        else:
            self.js("([b]) => vt.card(null,b,1)", bg)
        self.hold(hold)
        if fade_out:
            self.animate(fade_out, lambda k: self.js("([b,o]) => vt.card(null,b,o)", bg, 1 - k))

    # -- cursor
    def move_to(self, sel: str, nth: int = 0, seconds: float = 0.8, dx: float = 0, dy: float = 0) -> tuple:
        r = self.js("([s,n]) => vt.rect(s,n)", sel, nth)
        s, tx, ty = self.cam
        x, y = (r["x"] + r["w"] / 2 + dx) * s + tx, (r["y"] + r["h"] / 2 + dy) * s + ty
        x0, y0 = self.cur
        self.animate(seconds, lambda k: self.js("([x,y]) => vt.cursor(x,y,1)", x0 + (x - x0) * k, y0 + (y - y0) * k))
        self.cur = (x, y)
        return x, y

    def click_effect(self) -> None:
        x, y = self.cur
        self.animate(0.35, lambda k: self.js("([x,y,k]) => vt.ring(x,y,k)", x, y, k))
        self.js("([x,y]) => vt.ring(x,y,0)", x, y)

    def hide_cursor(self) -> None:
        x, y = self.cur
        self.js("([x,y]) => vt.cursor(x,y,0)", x, y)

    # -- output
    def encode(self, out: Path, ffmpeg: str) -> None:
        lst = self.frames / "list.txt"
        with lst.open("w", encoding="utf-8") as f:
            for s in self.shots:
                f.write(f"file '{s.path.name}'\nduration {s.seconds:.5f}\n")
            f.write(f"file '{self.shots[-1].path.name}'\n")
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-movflags", "+faststart", str(out)],
            check=True,
            cwd=self.frames,
        )

    @property
    def duration(self) -> float:
        return sum(s.seconds for s in self.shots)


def fresh_dir(p: Path) -> Path:
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    return p
