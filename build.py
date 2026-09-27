#!/usr/bin/env python3
"""
build.py: validate the site's data files and produce self-contained preview copies.

The live site (GitHub Pages) needs NO build step. index.html loads now.json and
gallery.json at runtime and references images by path. This script exists for two things:

  1. Validation. It fails loudly if now.json or gallery.json is not valid JSON, if a
     gallery entry points at a file that does not exist, or if a placeholder line
     "(like this)" is still sitting in now.json.
  2. Previews. It writes dist/philomath-standalone.html (open it from disk, everything
     inlined) and dist/philomath-artifact.html (the same page without the document
     skeleton, ready for the Claude Artifact tool, which wraps the page itself).

Usage:  python build.py            validate + write both previews
        python build.py --check    validate only, no output files
"""
import base64
import json
import mimetypes
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
MAX_INLINE_VIDEO = 4 * 1024 * 1024   # bigger clips are left out of the preview (poster still shows)
PLACEHOLDER = re.compile(r"^\(.*\)$")

mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/svg+xml", ".svg")


def fail(msg):
    print("BUILD FAILED: " + msg)
    sys.exit(1)


def load_json(name):
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        fail(name + " is missing")
    raw = open(path, encoding="utf-8").read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        fail("%s is not valid JSON: %s (line %d, column %d)" % (name, e.msg, e.lineno, e.colno))


def validate(now, gal):
    problems, warnings = [], []
    if not isinstance(now, dict):
        problems.append("now.json must be an object with 'updated', 'completions', 'now'")
    else:
        if not now.get("completions"):
            problems.append("now.json: 'completions' is empty; the hero needs at least one line")
        for it in now.get("now", []):
            if PLACEHOLDER.match(str(it.get("v", "")).strip()):
                warnings.append("now.json: '%s' still holds a placeholder and will not show on the site: %s" % (it.get("k"), it.get("v")))
            if it.get("cover") and not str(it["cover"]).startswith(("http://", "https://")):
                if not os.path.exists(os.path.join(ROOT, it["cover"])):
                    problems.append("now.json: cover not found: " + it["cover"])
    if not isinstance(gal, list):
        problems.append("gallery.json must be a list")
    else:
        seen = set()
        for i, g in enumerate(gal):
            src = g.get("src")
            if not src:
                problems.append("gallery.json entry %d has no 'src'" % i)
                continue
            if src in seen:
                problems.append("gallery.json: duplicate src " + src)
            seen.add(src)
            if not os.path.exists(os.path.join(ROOT, src)):
                problems.append("gallery.json: file not found: " + src)
            if g.get("type") == "video" or re.search(r"\.(mp4|webm|mov)$", src, re.I):
                if not g.get("poster"):
                    problems.append("gallery.json: video %s needs a 'poster' image" % src)
                elif not os.path.exists(os.path.join(ROOT, g["poster"])):
                    problems.append("gallery.json: poster not found: " + g["poster"])
            if not g.get("cap"):
                problems.append("gallery.json: %s has no caption" % src)
    for w in warnings:
        print("warning: " + w)
    if problems:
        fail("\n  " + "\n  ".join(problems))


def data_uri(rel):
    path = os.path.join(ROOT, rel)
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    raw = open(path, "rb").read()
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))


def inline_paths(html, gal):
    """Replace every local img/ and gallery/ reference (HTML and the JS sheet data) with a data URI."""
    def sub(m):
        q, rel = m.group(1), m.group(2)
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            fail("referenced file not found: " + rel)
        return q + data_uri(rel) + q
    html = re.sub(r"""(["'])((?:img|gallery)/[^"']+)\1""", sub, html)
    return html


def inline_gallery(gal):
    out = []
    for g in gal:
        g = dict(g)
        src = g["src"]
        is_vid = g.get("type") == "video" or re.search(r"\.(mp4|webm|mov)$", src, re.I)
        if is_vid:
            if os.path.getsize(os.path.join(ROOT, src)) <= MAX_INLINE_VIDEO:
                g["src"] = data_uri(src)
            else:
                print("  note: %s is over %d MB, preview shows the poster only" % (src, MAX_INLINE_VIDEO // 1024 // 1024))
                g["src"] = ""
            if g.get("poster"):
                g["poster"] = data_uri(g["poster"])
        else:
            g["src"] = data_uri(src)
        out.append(g)
    return out


def validate_free():
    """free/free.json: the Free to take page. Fails on bad JSON, missing keys, or an em-dash."""
    path = os.path.join(ROOT, "free", "free.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        d = json.loads(raw)
    except Exception as e:
        fail("free/free.json: %s" % e)
    if "\u2014" in raw or "\u2013" in raw:
        fail("free/free.json: contains an em-dash or en-dash")
    if not isinstance(d, dict) or not isinstance(d.get("items"), list):
        fail("free/free.json must be an object with an 'items' list")
    for i, it in enumerate(d["items"]):
        for k in ("id", "title", "kind", "state", "what", "take"):
            if not it.get(k):
                fail("free/free.json item %d is missing '%s'" % (i, k))
        if it["state"] not in ("live", "coming"):
            fail("free/free.json item %s: state must be 'live' or 'coming'" % it["id"])
    live = sum(1 for it in d["items"] if it["state"] == "live")
    print("free/free.json OK: %d items, %d live" % (len(d["items"]), live))


def main():
    check_only = "--check" in sys.argv
    now = load_json("now.json")
    gal = load_json("gallery.json")
    validate_free()
    validate(now, gal)
    print("now.json OK: %d completions, %d Now items, updated %s" % (len(now.get("completions", [])), len(now.get("now", [])), now.get("updated")))
    print("gallery.json OK: %d entries" % len(gal))
    if check_only:
        return

    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    html = html.replace('<script type="application/json" id="now-data"></script>',
                        '<script type="application/json" id="now-data">\n' + json.dumps(now, ensure_ascii=False) + '\n</script>')
    html = html.replace('<script type="application/json" id="gallery-data"></script>',
                        '<script type="application/json" id="gallery-data">\n' + json.dumps(inline_gallery(gal), ensure_ascii=False) + '\n</script>')
    html = inline_paths(html, gal)

    os.makedirs(DIST, exist_ok=True)
    standalone = os.path.join(DIST, "philomath-standalone.html")
    open(standalone, "w", encoding="utf-8").write(html)

    # Artifact version: drop the document skeleton, keep title + font link + style + body content.
    m = re.search(r"<head>(.*?)</head>\s*<body>(.*)</body>\s*</html>\s*$", html, re.S)
    if not m:
        fail("could not split head/body for the artifact build")
    head, body = m.group(1), m.group(2)
    keep = re.findall(r"<title>.*?</title>|<link[^>]+(?:fonts\.googleapis|fonts\.gstatic)[^>]*>|<style>.*?</style>", head, re.S)
    artifact = "\n".join(keep) + "\n" + body
    # The artifact host serves supporting files by exact path, so point the Free link at the file.
    artifact = artifact.replace('href="free/"', 'href="free/index.html"')
    art_path = os.path.join(DIST, "philomath-artifact.html")
    open(art_path, "w", encoding="utf-8").write(artifact)

    for p in (standalone, art_path):
        print("wrote %s (%.1f MB)" % (os.path.relpath(p, ROOT), os.path.getsize(p) / 1048576))


if __name__ == "__main__":
    main()
