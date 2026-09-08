#!/usr/bin/env python3
"""
reconcile_gallery.py: make gallery.json agree with whatever is actually in gallery/.

Run this after editing the gallery folder by hand (deleting images, dropping in edited versions,
adding new ones). It is safe to run any time; nothing is deleted.

    python tools/reconcile_gallery.py            report only
    python tools/reconcile_gallery.py --write    apply

Rules
- An entry whose file is gone, but a .jpg/.jpeg/.png/.webp with the same stem exists (a trailing
  digit, "-2" or " (1)" is tolerated): that file is an edited replacement. It is converted to WebP at
  the entry's original path (1600 px long edge), the entry keeps its caption, tags, date and note,
  and the replacement source moves to gallery/_replaced/.
- An entry whose file is gone with no replacement: the entry is removed from gallery.json.
- A file in gallery/ that no entry points at: imported as a new entry. Caption is drawn from the
  filename ("2026-teal-tele-bench.jpg" becomes "Teal tele bench"), tags are empty, so fix both in
  gallery.json afterwards. Non-WebP files are converted; the source moves to gallery/_replaced/.
- The list is then re-ordered with the same subject interleave the importer uses.
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY_DIR = os.path.join(ROOT, "gallery")
GALLERY_JSON = os.path.join(ROOT, "gallery.json")
REPLACED = os.path.join(GALLERY_DIR, "_replaced")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_media import spread, LONG_EDGE, WEBP_Q  # noqa: E402

IMG = (".webp", ".jpg", ".jpeg", ".png")


def to_webp(src, dst, write):
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(Image.open(src))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, LONG_EDGE / float(max(w, h)))
    if scale < 1.0:
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    if write:
        img.save(dst, "WEBP", quality=WEBP_Q, method=6)
    return img.size


def stem_key(name):
    s = os.path.splitext(os.path.basename(name))[0].lower()
    s = re.sub(r"(\s*\(\d+\)|[-_ ]?\d)$", "", s)   # "windings2", "windings-2", "windings (1)" -> "windings"
    return s


def main():
    write = "--write" in sys.argv
    gal = json.load(open(GALLERY_JSON, encoding="utf-8"))
    files = [f for f in os.listdir(GALLERY_DIR) if os.path.isfile(os.path.join(GALLERY_DIR, f)) and f.lower().endswith(IMG + (".mp4", ".webm", ".mov"))]
    by_key = {}
    for f in files:
        by_key.setdefault(stem_key(f), []).append(f)
    referenced = set()
    for e in gal:
        referenced.add(os.path.basename(e["src"]))
        if e.get("poster"):
            referenced.add(os.path.basename(e["poster"]))

    kept, removed, replaced, added = [], [], [], []
    print("WRITING" if write else "DRY RUN (add --write to apply)")
    for e in gal:
        path = os.path.join(ROOT, e["src"])
        if os.path.exists(path):
            kept.append(e)
            continue
        cands = [f for f in by_key.get(stem_key(e["src"]), []) if f not in referenced]
        if cands:
            src = os.path.join(GALLERY_DIR, sorted(cands)[0])
            e["w"], e["h"] = to_webp(src, path, write)
            referenced.add(os.path.basename(src))
            if write:
                os.makedirs(REPLACED, exist_ok=True)
                shutil.move(src, os.path.join(REPLACED, os.path.basename(src)))
            replaced.append((e["cap"], os.path.basename(src)))
            kept.append(e)
        else:
            removed.append(e["cap"])
    for f in sorted(files):
        if f in referenced:
            continue
        stem = os.path.splitext(f)[0]
        year = stem[:4] if re.match(r"^20\d\d-", stem) else ""
        cap = re.sub(r"^20\d\d-", "", stem).replace("-", " ").replace("_", " ").strip().capitalize() or "Untitled"
        dst_name = (stem if f.lower().endswith(".webp") else stem) + ".webp"
        dst = os.path.join(GALLERY_DIR, dst_name)
        if f.lower().endswith((".mp4", ".webm", ".mov")):
            print("  NOTE  %s: a clip with no entry; run the importer on it instead (needs a poster)" % f)
            continue
        if f.lower().endswith(".webp"):
            from PIL import Image
            w, h = Image.open(os.path.join(GALLERY_DIR, f)).size
        else:
            w, h = to_webp(os.path.join(GALLERY_DIR, f), dst, write)
            if write:
                os.makedirs(REPLACED, exist_ok=True)
                shutil.move(os.path.join(GALLERY_DIR, f), os.path.join(REPLACED, f))
        entry = {"src": "gallery/" + dst_name, "cap": cap, "tags": [], "date": year, "w": w, "h": h}
        kept.append(entry)
        added.append((cap, f))
        referenced.add(f); referenced.add(dst_name)

    gal = spread(kept)
    if write:
        json.dump(gal, open(GALLERY_JSON, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        open(GALLERY_JSON, "a", encoding="utf-8").write("\n")

    print("replaced with edited files (%d):" % len(replaced))
    for cap, f in replaced: print("  ~ %s   <- %s" % (cap, f))
    print("removed, file gone and no replacement (%d):" % len(removed))
    for cap in removed: print("  - " + cap)
    print("added from loose files, need caption + tags (%d):" % len(added))
    for cap, f in added: print("  + %s   <- %s" % (cap, f))
    print("%d entries %s" % (len(gal), "written" if write else "would result"))


if __name__ == "__main__":
    main()
