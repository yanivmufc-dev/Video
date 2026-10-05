# /// script
# requires-python = ">=3.10"
# dependencies = ["requests>=2.31"]
# ///
"""Get legally-safe assets into the studio library (remotion/public/library/).

    uv run tools/fetch_assets.py --workspace . starter                 # sound packs + common emoji (setup)
    uv run tools/fetch_assets.py --workspace . emoji 🔥 🤯 ✅          # Fluent emoji (MIT), scalable SVG
    uv run tools/fetch_assets.py --workspace . emoji 🔥 --style animated   # Noto animated (CC BY 4.0 → credit)
    uv run tools/fetch_assets.py --workspace . icon lucide:rocket tabler:brand-youtube --color "#F71C8A"
    uv run tools/fetch_assets.py --workspace . broll "typing on laptop" --n 3      # Pexels, then Pixabay
    uv run tools/fetch_assets.py --workspace . credits projects/my-reel            # caption credit line

Every downloaded file gets a <file>.license.json next to it (source, author, license, url, date).
Only sources whose license allows commercial social-media use are used:
  emoji  Fluent Emoji (Microsoft, MIT) · Noto (Google, Apache 2.0) · Noto Animated (CC BY 4.0 — credit!)
  icons  Iconify open sets: lucide (ISC), tabler/ph (MIT), mdi/material-symbols (Apache 2.0)
  broll  Pexels / Pixabay APIs — needs the member's own free key in api-keys.txt (PEXELS_API_KEY /
         PIXABAY_API_KEY). The member creates the free account and pastes the key into that file.
Never used: Mixkit "Restricted" clips, LottieFiles scraping, meme sounds, BBC SFX (non-commercial),
YouTube Audio Library (YouTube-only), anything CC BY-NC or ShareAlike.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _studio import KEYS_FILE, api_key, ffmpeg, read_json, utf8_console, write_json  # noqa: E402

TODAY = datetime.date.today().isoformat()
UA = {"User-Agent": "video-studio-skill/1.0 (asset fetcher)"}
STARTER_EMOJI = "🔥 🤯 😱 😂 🤔 👀 👇 👉 👆 ✅ ❌ ⚠️ 💡 🚀 💰 💸 📈 📉 ⭐ ❤️ 🎯 ⚡ 🧠 💯 🙏 💪 🎉 😎 🤖 ⏰ 📌 🔑 🛑 ✨ 👏"
ICONIFY_OK = {"lucide": "ISC", "tabler": "MIT", "ph": "MIT", "mdi": "Apache-2.0", "material-symbols": "Apache-2.0",
              "heroicons": "MIT", "iconoir": "MIT", "ri": "Apache-2.0", "carbon": "Apache-2.0",
              "fluent-emoji": "MIT", "fluent-emoji-flat": "MIT", "noto": "Apache-2.0", "logos": "CC0-1.0",
              "simple-icons": "CC0-1.0"}


def lib(ws: Path) -> Path:
    return ws / "remotion" / "public" / "library"


def save_license(path: Path, **info) -> None:
    write_json(path.with_name(path.name + ".license.json"), {**info, "retrieved": TODAY})


def get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=kw.pop("timeout", 60), **kw)
    r.raise_for_status()
    return r


# ------------------------------------------------------------------ emoji

def emoji_code(e: str) -> str:
    return "_".join(f"{ord(c):x}" for c in e)


_CHARS: dict = {}


def iconify_name(e: str) -> str | None:
    """Emoji -> Iconify icon name (fire, exploding-head…) via the Noto chars table."""
    if not _CHARS:
        _CHARS.update(get("https://cdn.jsdelivr.net/npm/@iconify-json/noto/chars.json").json())
    key = "-".join(f"{ord(c):x}" for c in e)
    return _CHARS.get(key) or _CHARS.get(key.replace("-fe0f", ""))


def fetch_emoji(ws: Path, emojis: list[str], style: str) -> int:
    ok = 0
    for e in emojis:
        code = emoji_code(e)
        folder = lib(ws) / "emoji" / code
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if style == "animated":
                dst = folder / "noto-animated.json"
                if not dst.exists():
                    dst.write_bytes(get(f"https://fonts.gstatic.com/s/e/notoemoji/latest/{code}/lottie.json").content)
                    save_license(dst, source="Google Noto Animated Emoji", license="CC-BY-4.0",
                                 attribution_required=True, credit="Emoji: Google Noto (CC BY 4.0)",
                                 url=f"https://googlefonts.github.io/noto-emoji-animation/")
            else:
                name = iconify_name(e)
                if not name:
                    raise ValueError("no Iconify name for this emoji")
                sets = [("fluent-emoji", "fluent.svg"), ("noto", "noto.svg")]
                if style == "flat":
                    sets.reverse()
                for prefix, fname in sets:
                    dst = folder / fname
                    if dst.exists():
                        break
                    r = requests.get(f"https://api.iconify.design/{prefix}/{name}.svg?height=512", headers=UA, timeout=30)
                    if r.status_code == 200 and r.text.startswith("<svg"):
                        dst.write_text(r.text, encoding="utf-8")
                        save_license(dst, source=f"Iconify {prefix} ({name})", license=ICONIFY_OK[prefix],
                                     attribution_required=False, url=f"https://icon-sets.iconify.design/{prefix}/{name}/")
                        break
                else:
                    raise ValueError("not found in fluent-emoji or noto")
            ok += 1
            print(f"[fetch] emoji {e} -> library/emoji/{code}/", file=sys.stderr)
        except Exception as err:  # keep going; the build falls back to the system emoji font
            print(f"[fetch] emoji {e}: {err}", file=sys.stderr)
    return 0 if ok == len(emojis) else 1


# ------------------------------------------------------------------ icons

def fetch_icons(ws: Path, names: list[str], color: str | None) -> int:
    for full in names:
        prefix, _, name = full.partition(":")
        if prefix not in ICONIFY_OK:
            print(f"[fetch] {prefix}: not on the approved list ({', '.join(ICONIFY_OK)}) — "
                  "some icon sets need credit (twemoji, fa) or are ShareAlike (openmoji)", file=sys.stderr)
            continue
        params = {"height": "512"}
        if color:
            params["color"] = color
        r = requests.get(f"https://api.iconify.design/{prefix}/{name}.svg", params=params, headers=UA, timeout=30)
        if r.status_code != 200 or not r.text.startswith("<svg"):
            print(f"[fetch] icon {full}: not found (search: https://icon-sets.iconify.design/?query={name})",
                  file=sys.stderr)
            continue
        dst = lib(ws) / "icons" / prefix / f"{name}.svg"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(r.text, encoding="utf-8")
        save_license(dst, source=f"Iconify {prefix}", license=ICONIFY_OK[prefix], attribution_required=False,
                     url=f"https://icon-sets.iconify.design/{prefix}/{name}/",
                     note="brand logos are trademarks: fine to identify a product, never imply endorsement"
                     if prefix in ("logos", "simple-icons") else None)
        print(dst.relative_to(ws / "remotion" / "public").as_posix())
    return 0


# ------------------------------------------------------------------ b-roll

def normalize_broll(src: Path, dst: Path) -> None:
    """Stock clips arrive 4K/60fps: make them light 30 fps H.264, no audio."""
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-an",
                    "-vf", "scale='if(gt(iw,ih),min(1920,iw),-2)':'if(gt(iw,ih),-2,min(1920,ih))',fps=30,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-g", "30",
                    "-movflags", "+faststart", str(dst)], check=True)
    src.unlink(missing_ok=True)


def fetch_broll(ws: Path, query: str, n: int, orientation: str) -> int:
    out = lib(ws) / "broll"
    out.mkdir(parents=True, exist_ok=True)
    got = 0
    pexels, pixabay = api_key("PEXELS_API_KEY"), api_key("PIXABAY_API_KEY")
    if not pexels and not pixabay:
        print("[fetch] no stock key. The member creates a FREE account at pexels.com/api (or pixabay.com/api/docs) "
              f"and adds a line PEXELS_API_KEY=... to {KEYS_FILE} in the studio folder.", file=sys.stderr)
        return 2
    if pexels:
        j = get("https://api.pexels.com/videos/search", headers={"Authorization": pexels},
                params={"query": query, "orientation": orientation, "size": "medium", "per_page": max(n * 2, 6)}).json()
        for v in j.get("videos", []):
            if got >= n:
                break
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
            if not files:
                continue
            target = 1920 if orientation == "portrait" else 1080
            best = min(files, key=lambda f: abs(max(f["height"], f["width"]) - target))
            dst = out / f"pexels-{v['id']}.mp4"
            if not dst.exists():
                tmp = out / f"_pexels-{v['id']}.mp4"
                tmp.write_bytes(get(best["link"], timeout=300).content)
                normalize_broll(tmp, dst)
                save_license(dst, source="Pexels", id=v["id"], url=v.get("url"), author=v.get("user", {}).get("name"),
                             license="Pexels License (free commercial use, no attribution required)",
                             license_url="https://www.pexels.com/license/", attribution_required=False, query=query)
            got += 1
            print(dst.relative_to(ws / "remotion" / "public").as_posix())
    if got < n and pixabay:
        j = get("https://pixabay.com/api/videos/", params={"key": pixabay, "q": query, "per_page": max(n * 2, 6),
                                                          "safesearch": "true"}).json()
        for h in j.get("hits", []):
            if got >= n:
                break
            vids = h.get("videos", {})
            best = vids.get("large") or vids.get("medium")
            if not best or not best.get("url"):
                continue
            dst = out / f"pixabay-{h['id']}.mp4"
            if not dst.exists():
                tmp = out / f"_pixabay-{h['id']}.mp4"
                tmp.write_bytes(get(best["url"], timeout=300).content)
                normalize_broll(tmp, dst)
                save_license(dst, source="Pixabay", id=h["id"], url=h.get("pageURL"), author=h.get("user"),
                             license="Pixabay Content License (free commercial use, no attribution required)",
                             license_url="https://pixabay.com/service/license-summary/", attribution_required=False,
                             query=query)
            got += 1
            print(dst.relative_to(ws / "remotion" / "public").as_posix())
    if got == 0:
        print(f"[fetch] nothing found for '{query}' — try simpler English keywords", file=sys.stderr)
        return 1
    print(f"[fetch] {got} clip(s). Make a contact sheet and LOOK before using any of them.", file=sys.stderr)
    return 0


# ------------------------------------------------------------------ starter + credits

def starter(ws: Path, assets: Path) -> int:
    sfx = lib(ws) / "sfx"
    bundled = sfx / "bundled"
    bundled.mkdir(parents=True, exist_ok=True)
    src = assets / "sfx"
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, bundled / f.name)
    for d in ("mine", "synth"):
        (sfx / d).mkdir(parents=True, exist_ok=True)
    for d in ("emoji", "icons", "broll", "images", "music", "fonts"):
        (lib(ws) / d).mkdir(parents=True, exist_ok=True)
    make = Path(__file__).with_name("make_sfx.py")
    subprocess.run([sys.executable, str(make), str(sfx / "synth")], check=True)
    print(f"[fetch] sounds: {len(list(bundled.glob('*.wav')))} recorded (CC0) + synthesized pack", file=sys.stderr)
    fetch_emoji(ws, STARTER_EMOJI.split(), "fluent")
    return 0


def credits(ws: Path, project: Path) -> int:
    edit = project / "edit.json"
    if not edit.exists():
        raise SystemExit("[fetch] build the project first")
    text = edit.read_text(encoding="utf-8")
    public = ws / "remotion" / "public"
    lines = set()
    for lic in public.rglob("*.license.json"):
        rel = lic.relative_to(public).as_posix().removesuffix(".license.json")
        if rel in text:
            info = read_json(lic)
            if info.get("attribution_required"):
                lines.add(info.get("credit") or f"{info.get('source')} ({info.get('license')})")
    print("\n".join(sorted(lines)) if lines else "no credit line needed")
    return 0


def main() -> int:
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", type=Path, default=Path(os.environ.get("STUDIO_WORKSPACE", ".")))
    sub = ap.add_subparsers(dest="kind", required=True)
    s = sub.add_parser("starter")
    here = Path(__file__).resolve().parent
    s.add_argument("--assets", type=Path,  # workspace copy (tools/studio/assets) or the skill's own assets/
                   default=here / "assets" if (here / "assets").exists() else here.parent / "assets")
    e = sub.add_parser("emoji")
    e.add_argument("emojis", nargs="+")
    e.add_argument("--style", choices=["fluent", "3d", "animated", "flat"], default="fluent")
    i = sub.add_parser("icon")
    i.add_argument("names", nargs="+", help="prefix:name, e.g. lucide:rocket")
    i.add_argument("--color", default=None)
    b = sub.add_parser("broll")
    b.add_argument("query")
    b.add_argument("--n", type=int, default=3)
    b.add_argument("--orientation", choices=["portrait", "landscape", "square"], default="portrait")
    c = sub.add_parser("credits")
    c.add_argument("project", type=Path)
    args = ap.parse_args()
    ws = args.workspace.resolve()

    if args.kind == "starter":
        return starter(ws, args.assets)
    if args.kind == "emoji":
        return fetch_emoji(ws, args.emojis, "fluent" if args.style == "3d" else args.style)
    if args.kind == "icon":
        return fetch_icons(ws, args.names, args.color)
    if args.kind == "broll":
        return fetch_broll(ws, args.query, args.n, args.orientation)
    if args.kind == "credits":
        return credits(ws, args.project.resolve())
    return 2


if __name__ == "__main__":
    sys.exit(main())
