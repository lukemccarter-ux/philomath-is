# philomath.is

Personal site for Luke McCarter. Static, single page, served by GitHub Pages from `main`
(custom domain in `CNAME`). No build step: push to `main` and the site is live within a minute
or two.

## Layout

| Path | What it is | Edit it? |
|---|---|---|
| `index.html` | The whole page: markup, CSS, JS. The master file. | Yes, for design or copy changes |
| `now.json` | The Now strip and the rotating hero completions | Yes, by hand, any time |
| `gallery.json` | The Sketchbook strip, newest first (`note` = longer blurb shown in the lightbox) | Usually via the importer; by hand to fix a caption or reorder |
| `gallery/` | Sketchbook images (WebP, 1600 px long edge) and clips (mp4 + WebP poster) | Via the importer |
| `img/` | Project screenshots, marks, diagrams used by the Projects cards | Rarely |
| `tools/import_media.py` | Inbox importer: resize, convert, caption, append to `gallery.json` | No |
| `build.py` | Validates the JSON files; writes self-contained previews to `dist/` | No |
| `import.bat`, `preview.bat` | One-click wrappers for the two scripts (Windows) | No |

## Update recipe

### 1. New images or clips (the Sketchbook)

1. Drop the files into **Desktop \ OpenRouter Inbox \ Personal Queue \ philomath_resources** (it is Drive-synced,
   so the phone works too). Any filename. To caption it yourself, add a text file with the same name:
   `IMG_0713.JPG` + `IMG_0713.txt` containing

   ```
   caption: MK7 GTI, bronze wheels, barn light
   tags: cars
   date: 2026
   note: Optional longer blurb. Shows under the caption when the image is opened. Use it for the story.
   ```

   Tags with filter chips: `art`, `watches`, `guitars`, `music`, `cars`. Comma-separate several. Project photos go under `watches`; anything that is a render says so in the caption.
   Or skip the sidecar and name the file `tags - caption.jpg`, e.g. `art+music - Stipple, bass guitar.jpg`.
   No caption anywhere: the filename becomes the caption and Claude tidies it on the next daily pass.
2. A scheduled Claude task checks the folder each weekday morning, imports what is new, writes captions
   from your notes (or drafts them), commits to the local clone and tells you what it did. Nothing is pushed
   until you say so. To do it yourself right now: double-click `import.bat` in this folder, or run
   `python tools\import_media.py "<folder>" --write --push`.
   Imported originals move to `_imported\`; things set aside for a decision sit in `_hold\` or `_skipped\`
   with a `_why.txt` beside them. Nothing is deleted.
3. Push (or say "publish"), then check https://philomath.is a minute later.

### 2. New notes (the Now strip and the hero)

Edit `now.json`, commit, push. That's the whole process. Shape:

```json
{
  "updated": "2026-09-07",
  "completions": ["…a lover of learning", "…a weekend watchmaker"],
  "now": [
    {"k": "On the bench", "w": 2, "v": "One sentence about the current watch build."},
    {"k": "Guitar",       "w": 2, "v": "One sentence about the current guitar build or mod."},
    {"k": "Drawing",      "w": 2, "v": "One sentence about the piece under the pen."},
    {"k": "Reading",   "w": 3, "title": "Book title", "cover": "https://covers.openlibrary.org/b/isbn/<ISBN13>-M.jpg", "v": "A sentence or two."},
    {"k": "Last read", "w": 3, "title": "Book title", "cover": "https://covers.openlibrary.org/b/isbn/<ISBN13>-M.jpg", "v": "A sentence or two."}
  ]
}
```

Rules that keep it safe:

- `w` is the column width out of 6 (2 = one third, 3 = half). Any mix that adds to 6 per row looks right.
- A value written `(like this)` in round brackets is a placeholder: it never shows on the site.
  Leave one in place rather than deleting the line when you have nothing to say.
- `cover` is optional. Missing or broken covers fall back to a drawn placeholder with the title.
- `updated` drives the "updated September 2026" stamp. Bump it when you change anything.
- Broken JSON (a stray comma) makes the page fall back to the first completion and hide the Now strip.
  `python build.py --check` tells you the line and column. The importer runs the same check before every push.

### 3. Anything else (copy, a new project card, design)

Edit `index.html` directly, run `python build.py` and open `dist\philomath-standalone.html` to eyeball it,
then commit and push. `dist\philomath-artifact.html` is the same page trimmed for the Claude Artifact tool
(for a shareable preview before it goes live). `dist/` is ignored by git.

## Conventions

- Canadian English, no em-dashes anywhere in copy.
- Gallery files are named `YYYY-slug.webp`; the year is the EXIF capture year, else the file date.
- Nothing is ever deleted by the scripts. Originals move to `inbox\_imported\`; git history keeps the rest.
