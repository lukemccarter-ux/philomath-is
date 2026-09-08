#!/usr/bin/env python3
"""
import_media.py: turn whatever landed in the inbox into sketchbook entries.

Drop photos or clips into the inbox folder (the Drive folder
Khub Dev/philomath-site-assets/inbox syncs to the laptop), then run:

    python tools/import_media.py "<inbox folder>"            preview what would happen
    python tools/import_media.py "<inbox folder>" --write    convert, add to gallery.json, move originals to inbox/_imported
    python tools/import_media.py "<inbox folder>" --write --push   ...and git commit + push (site is live a minute later)

Filename convention (optional, any name works):
    tags - caption.jpg          e.g.  "watches - Custom diver, hand-painted blue dial.jpg"
    tag1+tag2 - caption.jpg     e.g.  "art+music - Stipple, bass guitar.jpg"
Known tags: art, watches, guitars, music, cars. Project photos go under watches. Renders must say so in the caption.
No " - " in the name: the whole stem becomes the caption, tags empty (fix the caption later in gallery.json).

Images:  resized to 1600 px on the long edge, saved as WebP q82 into gallery/YYYY-slug.webp.
         HEIC works when pillow-heif is installed (pip install pillow-heif).
Videos:  transcoded with ffmpeg to H.264 mp4, max 1080p, plus a WebP poster frame. Without
         ffmpeg the clip is copied as-is (keep it small) and you must add a poster by hand.
Sidecar notes (optional): a .txt or .md with the SAME stem as the media file, e.g. photo.jpg + photo.txt.
    caption: Custom diver, hand-painted blue dial
    tags: watches, projects
    date: 2024
    note: A longer blurb. Shows under the caption when the image is opened. Several lines are fine.
  Or free text: first line is the caption, everything after it is the note.
  Sidecar values win over the filename. Sidecars move to _imported with their media.
Date: EXIF capture year, else a YYYYMMDD in the original filename, else the file's modified year;
      a sidecar "date:" wins over all three.
Docs:    other .md .txt .docx .pdf files are listed and left alone; hand them to Claude for the Now strip.

Every processed original is MOVED to inbox/_imported/ (never deleted). Entries are added to the
top of gallery.json, newest first. Existing entries are never touched.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY_DIR = os.path.join(ROOT, "gallery")
GALLERY_JSON = os.path.join(ROOT, "gallery.json")

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}
VID_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
DOC_EXT = {".md", ".txt", ".docx", ".pdf", ".rtf"}
LONG_EDGE = 1600
WEBP_Q = 82
KNOWN_TAGS = ["art", "watches", "guitars", "music", "cars"]
TAG_ALIASES = {"watch": "watches", "guitar": "guitars", "car": "cars", "band": "music", "bands": "music",
               "drawing": "art", "stipple": "art", "ink": "art", "project": "watches", "projects": "watches", "gti": "cars",
               "bass": "guitars", "violin": "music", "drums": "music", "render": "watches"}


def slugify(text, limit=48):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:limit].rstrip("-") or "item"


def parse_name(stem):
    """'art+music - Stipple, bass guitar' -> (['art','music'], 'Stipple, bass guitar')"""
    stem = re.sub(r"^(IMG|DSC|PXL|VID|MVI)[_-]?\d+[_-]*", "", stem, flags=re.I).strip()  # camera junk prefix
    if " - " in stem:
        left, right = stem.split(" - ", 1)
        tags = [TAG_ALIASES.get(t.strip().lower(), t.strip().lower()) for t in re.split(r"[+,]", left) if t.strip()]
        return tags, right.strip()
    return [], stem.replace("_", " ").replace("-", " ").strip() or "Untitled"


def exif_year(img):
    try:
        exif = img.getexif()
        val = exif.get(36867) or exif.get(306)  # DateTimeOriginal, DateTime
        if val:
            return str(val)[:4]
    except Exception:
        pass
    return None


def filename_year(stem):
    m = re.search(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)", stem)
    return m.group(1) if m else None


def read_sidecar(inbox, stem):
    """Return (path, dict) for stem.txt / stem.md next to the media file, else (None, {})."""
    for ext in (".txt", ".md"):
        p = os.path.join(inbox, stem + ext)
        if os.path.isfile(p):
            raw = open(p, encoding="utf-8-sig").read().strip()
            meta, free = {}, []
            for line in raw.splitlines():
                m = re.match(r"^(caption|tags|date|note)\s*:\s*(.*)$", line.strip(), re.I)
                if m and (m.group(1).lower() != "note" or "note" not in meta):
                    meta[m.group(1).lower()] = m.group(2).strip()
                elif "note" in meta:
                    meta["note"] = (meta["note"] + "\n" + line).strip()
                else:
                    free.append(line)
            if "caption" not in meta and free:
                meta["caption"] = free[0].strip()
                free = free[1:]
            if "note" not in meta and free:
                meta["note"] = "\n".join(free).strip()
            if "tags" in meta:
                meta["tags"] = [TAG_ALIASES.get(t.strip().lower(), t.strip().lower()) for t in re.split(r"[+,]", meta["tags"]) if t.strip()]
            return p, meta
    return None, {}


def unique_path(path):
    base, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = "%s-%d%s" % (base, n, ext)
        n += 1
    return path


def process_image(src, tags, cap, write, year=None, note=None):
    from PIL import Image, ImageOps
    try:
        import pillow_heif  # noqa: F401
        pillow_heif.register_heif_opener()
    except ImportError:
        if src.lower().endswith((".heic", ".heif")):
            print("  SKIP %s: HEIC needs 'pip install pillow-heif'" % os.path.basename(src))
            return None
    img = Image.open(src)
    year = year or exif_year(img) or filename_year(os.path.basename(src)) or str(dt.datetime.fromtimestamp(os.path.getmtime(src)).year)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, LONG_EDGE / float(max(w, h)))
    if scale < 1.0:
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    out = unique_path(os.path.join(GALLERY_DIR, "%s-%s.webp" % (year, slugify(cap))))
    rel = os.path.relpath(out, ROOT).replace(os.sep, "/")
    if write:
        img.save(out, "WEBP", quality=WEBP_Q, method=6)
    print("  IMAGE %s -> %s (%dx%d, %s)" % (os.path.basename(src), rel, img.size[0], img.size[1], year))
    e = {"src": rel, "cap": cap, "tags": tags, "date": year, "w": img.size[0], "h": img.size[1]}
    if note: e["note"] = note
    return e


def process_video(src, tags, cap, write, year=None, note=None):
    year = year or filename_year(os.path.basename(src)) or str(dt.datetime.fromtimestamp(os.path.getmtime(src)).year)
    stem = "%s-%s" % (year, slugify(cap))
    out = unique_path(os.path.join(GALLERY_DIR, stem + ".mp4"))
    poster = os.path.splitext(out)[0] + ".webp"
    rel, prel = (os.path.relpath(p, ROOT).replace(os.sep, "/") for p in (out, poster))
    has_ffmpeg = shutil.which("ffmpeg") is not None
    if write:
        if has_ffmpeg:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src,
                            "-vf", "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
                            "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], check=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", out, "-frames:v", "1",
                            "-vf", "scale='min(1600,iw)':-2", "-c:v", "libwebp", "-quality", str(WEBP_Q), poster], check=True)
        else:
            shutil.copy2(src, out)
            print("  WARN ffmpeg not found: copied %s as-is; add a poster image at %s by hand" % (os.path.basename(src), prel))
    print("  VIDEO %s -> %s (+ poster %s)%s" % (os.path.basename(src), rel, prel, "" if has_ffmpeg else " [no ffmpeg]"))
    e = {"type": "video", "src": rel, "poster": prel, "cap": cap, "tags": tags, "date": year}
    if write and os.path.exists(poster):
        try:
            from PIL import Image
            e["w"], e["h"] = Image.open(poster).size
        except Exception:
            pass
    if note: e["note"] = note
    return e


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inbox", help="folder holding the files to import")
    ap.add_argument("--write", action="store_true", help="actually convert files and update gallery.json (default is a dry run)")
    ap.add_argument("--push", action="store_true", help="git add/commit/push after writing")
    args = ap.parse_args()

    inbox = os.path.abspath(args.inbox)
    if not os.path.isdir(inbox):
        sys.exit("inbox folder not found: " + inbox)
    files = sorted(f for f in os.listdir(inbox) if not f.startswith((".", "_")) and os.path.isfile(os.path.join(inbox, f)))
    media_stems = {os.path.splitext(f)[0] for f in files if os.path.splitext(f)[1].lower() in IMG_EXT | VID_EXT}
    files = [f for f in files if not (os.path.splitext(f)[1].lower() in (".txt", ".md") and os.path.splitext(f)[0] in media_stems)]
    if not files:
        print("inbox is empty: " + inbox)
        return

    gal = json.load(open(GALLERY_JSON, encoding="utf-8"))
    os.makedirs(GALLERY_DIR, exist_ok=True)
    done_dir = os.path.join(inbox, "_imported")
    new_entries, moved, docs = [], [], []
    print("%s: %d file(s)" % ("WRITING" if args.write else "DRY RUN (add --write to apply)", len(files)))
    for f in files:
        src = os.path.join(inbox, f)
        stem, ext = os.path.splitext(f)
        ext = ext.lower()
        tags, cap = parse_name(stem)
        side_path, side = read_sidecar(inbox, stem)
        if side.get("tags"): tags = side["tags"]
        if side.get("caption"): cap = side["caption"]
        year, note = side.get("date"), side.get("note")
        unknown = [t for t in tags if t not in KNOWN_TAGS]
        if unknown:
            print("  note: %s uses tag(s) with no filter chip: %s" % (f, ", ".join(unknown)))
        try:
            if ext in IMG_EXT:
                entry = process_image(src, tags, cap, args.write, year, note)
            elif ext in VID_EXT:
                entry = process_video(src, tags, cap, args.write, year, note)
            elif ext in DOC_EXT:
                docs.append(f)
                print("  DOC   %s: left in place; hand it to Claude for the Now strip" % f)
                continue
            else:
                print("  SKIP  %s: unknown type" % f)
                continue
        except Exception as e:
            print("  ERROR %s: %s" % (f, e))
            continue
        if entry:
            new_entries.append(entry)
            moved.append(src)
            if side_path: moved.append(side_path)

    if not new_entries:
        print("nothing to add")
        return
    if args.write:
        gal = new_entries + gal
        gal.sort(key=lambda e: str(e.get("date", "")), reverse=True)   # newest year first; stable, so a batch keeps its order within a year
        json.dump(gal, open(GALLERY_JSON, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        open(GALLERY_JSON, "a", encoding="utf-8").write("\n")
        os.makedirs(done_dir, exist_ok=True)
        for src in moved:
            shutil.move(src, unique_path(os.path.join(done_dir, os.path.basename(src))))
        print("gallery.json: %d new entr%s at the top, %d total; originals moved to %s" % (
            len(new_entries), "y" if len(new_entries) == 1 else "ies", len(gal), os.path.relpath(done_dir, inbox)))
        check = subprocess.run([sys.executable, os.path.join(ROOT, "build.py"), "--check"])
        if check.returncode != 0:
            sys.exit("gallery.json was updated but the check above failed; fix it before pushing")
        if args.push:
            git("add", "-A", "gallery", "gallery.json")
            msg = "sketchbook: add " + ", ".join(e["cap"] for e in new_entries)[:120]
            git("commit", "-m", msg)
            git("push")
            print("pushed: " + msg)
    else:
        print("dry run complete; re-run with --write to apply")


if __name__ == "__main__":
    main()
