# tocRip

A command-line tool for working with the table of contents (TOC) of a PDF — typically a music score book where each TOC entry is a song and its starting page.

It can either:

- **Add bookmarks** to the PDF, one per song, so the TOC becomes clickable outline entries; or
- **Split the PDF by song**, writing a separate PDF for each entry in the TOC.

The TOC can come from a text file you provide, or the script will attempt to extract it from the PDF's own text layer.

## Requirements

- Python 3.7+
- [`pypdf`](https://pypi.org/project/pypdf/)

```bash
pip install pypdf
```

## Usage

```bash
# Add bookmarks (default mode)
python tocrip.py book.pdf
python tocrip.py book.pdf output.pdf

# Split into one PDF per song
python tocrip.py book.pdf --split
python tocrip.py book.pdf --split --split-dir songs
python tocrip.py book.pdf --split --split-bookmarks
```

Run `python tocrip.py --help` for the full option list.

### Arguments and options

| Argument / option | Description |
| --- | --- |
| `input_pdf` | Path to the input PDF (required). |
| `output_pdf` | Output path for bookmark mode. Optional; defaults to `<input>_with_bookmarks.pdf`. Ignored when `--split` is used. |
| `--split` | Split the PDF into a separate file per song instead of adding bookmarks. |
| `--split-dir DIR` | Directory to write the split song PDFs into. Defaults to `<pdfname>_songs`. |
| `--split-bookmarks` | Add a bookmark inside each individual song PDF (only meaningful with `--split`). |

## How the TOC is found

When run, the script tries these sources in order:

1. **A local TOC file** in the current directory. It looks for `toc.txt`, `TOC.txt`, `contents.txt`, `bookmarks.txt`, or any `*.toc` / `*.contents` file.
2. **The PDF's text layer.** If no TOC file is found, it attempts to parse the first 15 pages for title/page-number pairs. Extracted results are saved to `extracted_toc.txt` so you can review and reuse them.

If neither produces a usable TOC, the script prints the accepted file formats and exits.

### TOC file formats

Lines starting with `#` are treated as comments. Each entry can be written in any of these forms:

```
# Page number first
5 Ashitaka and San
8 Ask Me Why

# Title first, page number last
Ashitaka and San 5
Ask Me Why 8

# Pipe-separated
Ashitaka and San|5
Ask Me Why|8
```

Titles are cleaned automatically to fix common PDF text-extraction artifacts (stray spacing, decorative bullets, split words, etc.).

## Interactive flow

After loading the TOC, the script:

1. Validates every page number against the actual length of the PDF.
2. If any entries reference pages beyond the PDF, offers to fix them interactively, skip them, or abort.
3. Shows the full list of entries and asks you to confirm.

At the confirmation prompt you can:

- `y` / `yes` — proceed as-is
- `n` / `no` — cancel
- any integer (e.g. `1`, `-2`, `5`) — shift **every** page number by that offset, then re-validate

The offset is applied before either bookmarking or splitting, so it affects both modes. This is handy when the TOC page numbers are off by a fixed amount (for example, when the printed page numbering doesn't match the PDF's physical page order).

## How splitting works

Songs are sorted by starting page. Each song spans from its own start page up to the page just before the next song begins; the final song runs to the end of the PDF.

Given a 12-page PDF and this TOC:

```
1 Ashitaka and San
4 Ask Me Why
7 A Time for Us
10 You're the One
```

`--split` produces:

```
book_songs/
├── 01 - Ashitaka and San.pdf   (pages 1–3)
├── 02 - Ask Me Why.pdf         (pages 4–6)
├── 03 - A Time for Us.pdf      (pages 7–9)
└── 04 - You're the One.pdf     (pages 10–12)
```

Notes on the output:

- Files are named `NN - Title.pdf`, where the numeric prefix preserves order and keeps songs that share a title from colliding.
- Characters that are illegal in filenames on Windows/macOS/Linux (`/ \ : * ? " < > |`) are stripped from titles, and trailing dots/spaces are trimmed.
- If two consecutive entries point at the same page, each still receives at least that one page rather than an empty file.

## Notes

- Bookmark mode preserves the original page content and adds an outline entry per song.
- Split mode copies pages into new files and does not modify the original PDF.
