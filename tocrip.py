import argparse
import os
import re
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def clean_title(title):
    """Clean up common PDF text extraction artifacts in titles."""
    # Remove multiple spaces first
    title = re.sub(r"\s+", " ", title)

    # Remove common PDF extraction artifacts at the start of titles
    # Only remove if they're clearly not part of the title (standalone symbols/letters)
    # Common bullet points and decorative symbols
    title = re.sub(r"^[\s•·▪▸▹►▻◆◇○●◉◎◦⦁⦾]+", "", title)

    # Remove standalone single letters only if followed by another space and then a capital letter
    # This preserves "A " in "A Time for Us" but removes "W " in "W Everything"
    title = re.sub(r"^[A-Z]\s+(?=[A-Z])", "", title)

    # Remove Chinese characters and other non-Latin symbols
    title = re.sub(r"[门具贝]", "", title)

    # Remove # symbols at start
    title = re.sub(r"^#\s*", "", title)

    # Fix common single-character spacing issues
    # Pattern: single uppercase letter followed by space and more letters
    title = re.sub(r"\b([A-Z])\s+([A-Za-z])", r"\1\2", title)

    # Fix words that got split with spaces between characters
    title = re.sub(r"\b([A-Z])\s([A-Z])\s([A-Z])\s([A-Z])\b", r"\1\2\3\4", title)
    title = re.sub(r"\b([A-Z])\s([A-Z])\s([A-Z])\b", r"\1\2\3", title)
    title = re.sub(r"\b([A-Z])\s([A-Z])\b", r"\1\2", title)

    # Fix "You ' re" -> "You're" and similar contractions
    title = re.sub(r"\b([A-Za-z]+)\s+'\s*([a-z]+)", r"\1'\2", title)

    # Fix specific common split words
    title = re.sub(r"\bY\s+ou\b", "You", title)
    title = re.sub(r"\bT\s+he\b", "The", title)
    title = re.sub(r"\bT\s+ears?\b", "Tears", title)
    title = re.sub(r"\bY\s+our?\b", "Your", title)
    title = re.sub(r"\bY\s+ou\'?re?\b", "You're", title)
    title = re.sub(r"\bW\s+hat\b", "What", title)
    title = re.sub(r"\bW\s+hen\b", "When", title)
    title = re.sub(r"\bW\s+here\b", "Where", title)
    title = re.sub(r"\bW\s+hich\b", "Which", title)
    title = re.sub(r"\bW\s+ho\b", "Who", title)
    title = re.sub(r"\bW\s+hy\b", "Why", title)
    title = re.sub(r"\bW\s+e\'?ve?\b", "We've", title)
    title = re.sub(
        r"\bI\s+(?=[a-z])", "I", title
    )  # Fix "I Fall" -> "IFall" -> "I Fall" issue

    # Apply the general fix multiple times for remaining cases
    for _ in range(3):
        title = re.sub(r"\b([A-Z])\s+([a-z])", r"\1\2", title)

    # Fix merged words that should be separate (like "IFall" -> "I Fall")
    title = re.sub(r"\bI([A-Z][a-z]+)\b", r"I \1", title)

    # Remove leading/trailing whitespace and dots
    title = title.strip()
    title = re.sub(r"\.{2,}$", "", title)
    title = re.sub(r"[-–]\s*$", "", title)

    return title


def should_skip_title(title):
    """Check if a title should be skipped (e.g., 'Registration' entries)."""
    # List of titles to skip (case-insensitive)
    skip_titles = [
        "registration",
        "registrations",
    ]

    # Clean and normalize the title for comparison
    normalized = title.strip().lower()

    # Check exact matches
    if normalized in skip_titles:
        return True

    # Check if title starts with or contains common patterns to skip
    # This catches variations like "Registration Form", "Registration Page", etc.
    if normalized.startswith("registration") or " registration" in normalized:
        return True

    return False


def extract_toc_from_pdf(pdf_path):
    """Try to extract TOC from PDF text layer with multiple pattern matching."""
    reader = PdfReader(pdf_path)
    all_entries = []

    print(f"Attempting to extract TOC from {pdf_path}...")

    # Try different patterns for TOC detection
    patterns = [
        # Pattern 1: "Title Name 123" (title then page number at end of line)
        r"(.+?)\s+(\d{1,4})\s*$",
        # Pattern 2: "123 Title Name" (page number then title at start of line)
        r"^\s*(\d{1,4})\s+(.+)",
        # Pattern 3: "Title Name ... 123" (title with dots then page)
        r"(.+?)\.{2,}\s*(\d{1,4})",
        # Pattern 4: "Title Name - 123" (title with dash then page)
        r"(.+?)\s*[-–]\s*(\d{1,4})(?:\s|$)",
        # Pattern 5: More aggressive - find title followed by number
        r"([A-Za-z][A-Za-z\s\(\)\-&'’,;:!?.]+?)\s+(\d{2,4})(?:\s|$)",
    ]

    # Check first 15 pages for TOC
    for page_num, page in enumerate(reader.pages[:15]):
        text = page.extract_text()
        if not text:
            continue

        # Split text into lines to process line by line
        lines = text.split("\n")

        for line in lines:
            # Clean the line first to remove artifacts
            line = line.strip()
            if not line or len(line) < 5:
                continue

            # Remove common PDF extraction artifacts from the line
            # Only remove standalone single letters at the very start if followed by space and capital
            line = re.sub(r"^[A-Z]\s+(?=[A-Z])", "", line)
            # Remove special Unicode characters
            line = re.sub(r"[门具贝◆◇○●◉◎◦•·▪▸▹►▻]", "", line)
            # Remove # at start
            line = re.sub(r"^#\s*", "", line)

            # Try each pattern on individual lines first
            for pattern in patterns:
                match = re.search(pattern, line, re.MULTILINE)

                if match:
                    groups = match.groups()
                    if len(groups) == 2:
                        # Determine which part is title and which is page
                        if groups[0].isdigit() and len(groups[0]) <= 4:
                            page = int(groups[0])
                            title = groups[1].strip()
                        elif groups[1].isdigit() and len(groups[1]) <= 4:
                            page = int(groups[1])
                            title = groups[0].strip()
                        else:
                            continue

                        # Clean up title using the cleaning function
                        title = clean_title(title)

                        # Skip titles that match our exclusion list
                        if should_skip_title(title):
                            continue

                        # Validate that the title isn't just numbers or too short
                        if (
                            len(title) >= 3
                            and re.search(r"[A-Za-z]{2,}", title)  # At least 2 letters
                            and 1 <= page <= len(reader.pages)
                            and not any(
                                word in title.lower()
                                for word in ["indd", "all pages", "collectionpiano"]
                            )
                        ):
                            # Additional check: title shouldn't contain another page number pattern
                            if not re.search(r"\b\d{2,4}\b", title):
                                all_entries.append((title, page))
                                break  # Found a match for this line, move to next line

    # If line-by-line parsing didn't work well, fall back to full text
    if len(all_entries) < 3:
        print("Line-by-line parsing found few entries, trying full text analysis...")
        all_entries = []

        for page_num, page in enumerate(reader.pages[:15]):
            text = page.extract_text()
            if not text:
                continue

            # Clean the text first
            text = re.sub(r"[门具贝◆◇○●◉◎◦•·▪▸▹►▻]", "", text)
            text = re.sub(r"^[A-Z]\s+(?=[A-Z])", "", text, flags=re.MULTILINE)
            text = re.sub(r"^#\s*", "", text, flags=re.MULTILINE)

            # Try to split by common delimiters
            # Look for patterns like "Title 123" separated by whitespace
            potential_entries = re.findall(
                r"([A-Za-z][^0-9]{3,80}?)\s+(\d{1,4})(?=\s|$)", text
            )

            for title, page_str in potential_entries:
                page = int(page_str)
                title = clean_title(title)

                # Skip titles that match our exclusion list
                if should_skip_title(title):
                    continue

                if (
                    len(title) >= 3
                    and re.search(r"[A-Za-z]{2,}", title)
                    and 1 <= page <= len(reader.pages)
                    and not any(
                        word in title.lower()
                        for word in ["indd", "all pages", "collectionpiano"]
                    )
                ):
                    all_entries.append((title, page))

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for title, page in all_entries:
        key = (title.lower(), page)  # Case-insensitive duplicate detection
        if key not in seen:
            seen.add(key)
            unique.append((title, page))

    # Sort by page number for consistency
    unique.sort(key=lambda x: x[1])

    return unique


def load_toc_from_file(toc_file_path, pdf_page_count=None):
    """Load TOC entries from various file formats with page validation."""
    entries = []
    invalid_entries = []

    # Try to detect format from file extension or content
    with open(toc_file_path, "r", encoding="utf-8") as f:
        content = f.readlines()

    for line_num, line in enumerate(content, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        title = None
        page = None

        # Try different formats
        # Format 1: "Title|Page"
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                title = parts[0].strip()
                try:
                    page = int(parts[1].strip())
                except ValueError:
                    pass

        # Format 2: "Page Title" (page number first)
        if page is None:
            match_start = re.match(r"^(\d+)\s+(.+)", line)
            if match_start:
                page = int(match_start.group(1))
                title = match_start.group(2).strip()

        # Format 3: "Title Page" (page number last)
        if page is None:
            # Find the last number in the line
            match_end = re.search(r"\s+(\d+)\s*$", line)
            if match_end:
                try:
                    page = int(match_end.group(1))
                    title = line[: match_end.start()].strip()
                except ValueError:
                    pass

        if title and page:
            # Clean title from file input too
            title = clean_title(title)

            # Skip titles that match our exclusion list
            if should_skip_title(title):
                print(f"Note: Skipping entry with title '{title}' on line {line_num}")
                continue

            # Validate page number against PDF if available
            if pdf_page_count and page > pdf_page_count:
                invalid_entries.append(
                    (
                        title,
                        page,
                        f"Page {page} exceeds PDF length ({pdf_page_count} pages)",
                    )
                )
            else:
                entries.append((title, page))
        else:
            print(f"Warning: Could not parse line {line_num}: {line}")

    return entries, invalid_entries


def detect_toc_format(toc_file_path):
    """Detect the format of the TOC file."""
    with open(toc_file_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()

    if "|" in first_line:
        return "pipe"
    elif re.match(r"^\d+\s+", first_line):
        return "page_first"
    elif re.search(r"\s+\d+$", first_line):
        return "page_last"
    else:
        return "unknown"


def is_toc_valid(toc_entries, min_entries=3):
    """Check if extracted TOC looks valid."""
    if not toc_entries or len(toc_entries) < min_entries:
        return False

    # Check if most entries have reasonable titles
    valid_count = 0
    for title, page in toc_entries:
        # Valid title should be reasonable length and have some letters
        if (
            3 <= len(title) <= 100
            and re.search(r"[A-Za-z]", title)
            and 1 <= page <= 1000
        ):  # Assume reasonable page range
            valid_count += 1

    # If more than 70% are valid, it's good
    return valid_count / len(toc_entries) > 0.7


def find_toc_file():
    """Look for TOC file in current directory with various names."""
    toc_patterns = [
        "toc.txt",
        "TOC.txt",
        "contents.txt",
        "bookmarks.txt",
        "*.toc",
        "*.contents",
    ]

    # Look for exact matches first
    for pattern in toc_patterns:
        if "*" not in pattern and os.path.exists(pattern):
            return pattern

    # Look for wildcard patterns
    for pattern in toc_patterns:
        if "*" in pattern:
            matches = list(Path(".").glob(pattern))
            if matches:
                return str(matches[0])

    return None


def save_toc_to_file(toc_entries, filepath="toc.txt", format_type="auto"):
    """Save TOC entries to file in specified format."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# PDF Table of Contents\n")
        f.write(f"# Generated: {len(toc_entries)} entries\n")
        f.write("# Format: PageNumber Title\n\n")

        for title, page in toc_entries:
            f.write(f"{page} {title}\n")

    print(f"✓ Saved {len(toc_entries)} entries to {filepath}")


def fix_invalid_entries(invalid_entries, pdf_page_count):
    """Interactive fixing of invalid page numbers."""
    print("\n" + "=" * 60)
    print("⚠️  INVALID PAGE NUMBERS DETECTED")
    print("=" * 60)
    print(
        f"PDF has {pdf_page_count} pages, but some TOC entries reference higher pages.\n"
    )

    fixed_entries = []

    for title, old_page, error_msg in invalid_entries:
        print(f"\nEntry: {title}")
        print(f"  Problem: {error_msg}")
        print(f"  Options:")
        print(f"    1. Skip this entry")
        print(f"    2. Enter corrected page number (1-{pdf_page_count})")
        print(f"    3. Keep as is (will be ignored when adding bookmarks)")

        while True:
            choice = input(f"  Your choice (1-3): ").strip()

            if choice == "1":
                print(f"  → Skipping '{title}'")
                break
            elif choice == "2":
                try:
                    new_page = int(
                        input(f"  Enter correct page number (1-{pdf_page_count}): ")
                    )
                    if 1 <= new_page <= pdf_page_count:
                        fixed_entries.append((title, new_page))
                        print(f"  → Updated to page {new_page}")
                        break
                    else:
                        print(f"  Page must be between 1 and {pdf_page_count}")
                except ValueError:
                    print("  Please enter a valid number")
            elif choice == "3":
                fixed_entries.append((title, old_page))
                print(f"  → Keeping as is (will be ignored)")
                break
            else:
                print("  Invalid choice")

    return fixed_entries


def apply_offset_to_entries(toc_entries, offset):
    """Apply a page number offset to all TOC entries."""
    adjusted_entries = []
    for title, page in toc_entries:
        new_page = page + offset
        if new_page < 1:
            new_page = 1
        adjusted_entries.append((title, new_page))
    return adjusted_entries


def sanitize_filename(name, max_length=100):
    """Turn a song title into a filename that's safe on Windows/macOS/Linux."""
    # Strip characters that are illegal in filenames on common filesystems
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Windows dislikes trailing dots/spaces
    name = name.strip(". ")
    if not name:
        name = "untitled"
    return name[:max_length].strip()


def split_pdf_by_song(
    input_pdf_path, toc_entries, output_dir=None, add_bookmarks=False
):
    """Split a PDF into one file per song using the TOC entries as boundaries.

    Each song spans from its own start page up to the page just before the next
    song begins. The final song runs to the end of the PDF.
    """
    reader = PdfReader(input_pdf_path)
    total_pages = len(reader.pages)

    # Sort by page so that boundaries between consecutive songs are correct
    entries = sorted(toc_entries, key=lambda x: x[1])

    if not entries:
        print("❌ No TOC entries available to split by.")
        return 0

    # Determine output directory
    if output_dir is None:
        base = os.path.splitext(os.path.basename(input_pdf_path))[0]
        output_dir = f"{base}_songs"
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n✂️  Splitting into individual song PDFs → {output_dir}/")

    files_written = 0
    used_names = set()

    for i, (title, start_page) in enumerate(entries):
        # TOC page numbers are 1-based; convert to a 0-based index
        start_idx = start_page - 1

        # This song ends where the next one starts (exclusive, 0-based)
        if i + 1 < len(entries):
            end_idx = entries[i + 1][1] - 1
        else:
            end_idx = total_pages  # last song runs to the end of the PDF

        # Clamp to the valid page range and guarantee at least one page
        start_idx = max(0, min(start_idx, total_pages - 1))
        end_idx = max(start_idx + 1, min(end_idx, total_pages))

        writer = PdfWriter()
        for page_idx in range(start_idx, end_idx):
            writer.add_page(reader.pages[page_idx])

        if add_bookmarks:
            writer.add_outline_item(title, 0)

        # Build a unique, safe filename like "01 - Song Title.pdf"
        safe_title = sanitize_filename(title)
        base_name = f"{i + 1:02d} - {safe_title}"
        candidate = base_name
        dedupe = 2
        while candidate.lower() in used_names:
            candidate = f"{base_name} ({dedupe})"
            dedupe += 1
        used_names.add(candidate.lower())

        out_path = os.path.join(output_dir, f"{candidate}.pdf")
        with open(out_path, "wb") as f:
            writer.write(f)

        page_count = end_idx - start_idx
        plural = "s" if page_count != 1 else ""
        print(
            f"  ✓ {candidate}.pdf  "
            f"(pages {start_idx + 1}-{end_idx}, {page_count} page{plural})"
        )
        files_written += 1

    plural = "s" if files_written != 1 else ""
    print(f"\n✅ Wrote {files_written} song PDF{plural} to {output_dir}/")
    return files_written


def add_bookmarks_to_pdf(input_pdf_path, output_pdf_path, toc_entries):
    """Add bookmarks to PDF using TOC entries."""
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    print(f"\n📑 Adding bookmarks to PDF...")

    # Copy all pages
    for page in reader.pages:
        writer.add_page(page)

    # Add bookmarks
    bookmarks_added = 0
    skipped = []

    for title, page_num in toc_entries:
        target_page = page_num - 1  # Convert to 0-based index
        if 0 <= target_page < len(reader.pages):
            writer.add_outline_item(title, target_page)
            bookmarks_added += 1
            print(f"  ✓ {title} -> Page {page_num}")
        else:
            skipped.append((title, page_num))
            print(
                f"  ✗ Skipped: {title} -> Page {page_num} (invalid - PDF has {len(reader.pages)} pages)"
            )

    # Write output
    with open(output_pdf_path, "wb") as f:
        writer.write(f)

    print(f"\n✅ Added {bookmarks_added} bookmarks to {output_pdf_path}")
    if skipped:
        print(f"⚠️  Skipped {len(skipped)} entries due to invalid page numbers")

    return bookmarks_added


def get_user_confirmation(toc_entries):
    """
    Get user confirmation with support for y/n/digit responses.
    Returns either True/False for proceed/cancel, or an integer offset value.
    """
    print("\n" + "=" * 60)
    print("PROCEED OR ADJUST PAGES?")
    print("=" * 60)
    print(f"Found {len(toc_entries)} song entries.")
    print("\nOptions:")
    print("  y / yes     - Proceed with current page numbers")
    print("  n / no      - Cancel operation")
    print("  1           - Increment ALL page numbers by +1")
    print("  5           - Increment ALL page numbers by +5")
    print(" -1           - Decrement ALL page numbers by -1")
    print(" -5           - Decrement ALL page numbers by -5")
    print("  <number>    - Any integer to adjust all pages by that amount")

    while True:
        response = input("\nYour choice: ").strip().lower()

        # Check for y/n
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False

        # Check for digit (positive or negative integer)
        try:
            offset = int(response)
            return offset
        except ValueError:
            print(f"Invalid input: '{response}'. Please enter y, n, or a number.")


def main():
    parser = argparse.ArgumentParser(
        prog="pdf_bookmarker.py",
        description=(
            "Add a table of contents as bookmarks to a PDF, or split the PDF "
            "into a separate file for each song in the TOC."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Add bookmarks:   python pdf_bookmarker.py book.pdf output.pdf\n"
            "  Split by song:   python pdf_bookmarker.py book.pdf --split\n"
            "  Split to a dir:  python pdf_bookmarker.py book.pdf --split "
            "--split-dir songs\n\n"
            "The script will automatically:\n"
            "  1. Look for a local TOC file (toc.txt, contents.txt, etc.)\n"
            "  2. Validate page numbers against PDF length\n"
            "  3. Let you fix invalid page numbers interactively\n"
            "  4. Let you adjust all page numbers by an offset\n"
            "  5. Add bookmarks to the PDF, or split it into one PDF per song"
        ),
    )
    parser.add_argument("input_pdf", help="Path to the input PDF")
    parser.add_argument(
        "output_pdf",
        nargs="?",
        help="Output PDF path (bookmark mode only; ignored when --split is used)",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="Split the PDF into a separate PDF for each song in the TOC, "
        "instead of adding bookmarks",
    )
    parser.add_argument(
        "--split-dir",
        metavar="DIR",
        help="Directory to write split song PDFs into (default: <pdfname>_songs)",
    )
    parser.add_argument(
        "--split-bookmarks",
        action="store_true",
        help="Add a bookmark to each split song PDF (only with --split)",
    )
    args = parser.parse_args()

    input_pdf = args.input_pdf

    if not os.path.exists(input_pdf):
        print(f"Error: File '{input_pdf}' not found.")
        sys.exit(1)

    # Get PDF page count first
    reader = PdfReader(input_pdf)
    pdf_page_count = len(reader.pages)
    print(f"\n📄 PDF has {pdf_page_count} pages")

    # Set output PDF path (used in bookmark mode)
    if args.output_pdf:
        output_pdf = args.output_pdf
    else:
        name, ext = os.path.splitext(input_pdf)
        output_pdf = f"{name}_with_bookmarks{ext}"

    print("=" * 60)
    if args.split:
        print("PDF Song Splitter (Dynamic TOC Support)")
    else:
        print("PDF Bookmarker (Dynamic TOC Support)")
    print("=" * 60)

    toc_entries = []

    # Step 1: Look for local TOC file
    toc_file = find_toc_file()

    if toc_file:
        print(f"\n📄 Found TOC file: {toc_file}")
        format_type = detect_toc_format(toc_file)
        print(f"Detected format: {format_type}")

        toc_entries, invalid_entries = load_toc_from_file(toc_file, pdf_page_count)

        if invalid_entries:
            print(
                f"\n⚠️  Found {len(invalid_entries)} entries with invalid page numbers"
            )

            # Show summary of invalid entries
            print("\nInvalid entries summary:")
            for title, page, error in invalid_entries[:10]:
                print(f"  • {title[:50]}... -> page {page}")
            if len(invalid_entries) > 10:
                print(f"  ... and {len(invalid_entries) - 10} more")

            # Ask user how to handle
            print("\nHow would you like to handle invalid entries?")
            print("  1. Fix them interactively")
            print("  2. Skip all invalid entries")
            print("  3. Abort and fix TOC file manually")

            choice = input("Your choice (1-3): ").strip()

            if choice == "1":
                fixed_entries = fix_invalid_entries(invalid_entries, pdf_page_count)
                toc_entries.extend(fixed_entries)
                print(f"\n✓ Fixed {len(fixed_entries)} entries")
            elif choice == "2":
                print(f"\n→ Skipping {len(invalid_entries)} invalid entries")
            elif choice == "3":
                print("\nPlease fix your TOC file and run again.")
                print(f"Valid page range: 1-{pdf_page_count}")
                sys.exit(0)
            else:
                print("Invalid choice. Skipping invalid entries.")

        if toc_entries:
            print(f"\n✓ Loaded {len(toc_entries)} valid entries from {toc_file}")

            # Display first few entries as preview
            print("\nPreview of loaded TOC:")
            for i, (title, page) in enumerate(toc_entries[:5], 1):
                print(f"  {i}. Page {page}: {title[:60]}")
            if len(toc_entries) > 5:
                print(f"  ... and {len(toc_entries) - 5} more")
        else:
            print(f"⚠️  No valid entries found in TOC file")

    # Step 2: If no valid TOC from file, try to extract from PDF
    if not toc_entries:
        print("\n🔍 No valid TOC file found. Attempting to extract from PDF...")
        toc_entries = extract_toc_from_pdf(input_pdf)

        if toc_entries and is_toc_valid(toc_entries):
            print(f"✓ Successfully extracted {len(toc_entries)} entries from PDF")

            # Save extracted TOC for future use
            save_toc_to_file(toc_entries, "extracted_toc.txt")

            print("\nPreview of extracted TOC:")
            for i, (title, page) in enumerate(toc_entries[:5], 1):
                print(f"  {i}. Page {page}: {title[:60]}")
            if len(toc_entries) > 5:
                print(f"  ... and {len(toc_entries) - 5} more")
        else:
            print("\n❌ Could not extract valid TOC from PDF")
            print("\nPlease create a TOC file (toc.txt) with one of these formats:")
            print("  Format 1 (Page Number then Title):")
            print("    5 Ashitaka and San")
            print("    8 Ask Me Why (Mother's Message)")
            print("\n  Format 2 (Title then Page Number):")
            print("    Ashitaka and San 5")
            print("    Ask Me Why (Mother's Message) 8")
            print("\n  Format 3 (Pipe-separated):")
            print("    Ashitaka and San|5")
            print("    Ask Me Why (Mother's Message)|8")
            print(f"\n  Valid page range: 1-{pdf_page_count}")
            sys.exit(1)

    # Final validation
    if not toc_entries:
        print("\n❌ No valid TOC entries. Exiting.")
        sys.exit(1)

    # Filter entries that are within page range
    valid_entries = [
        (title, page) for title, page in toc_entries if 1 <= page <= pdf_page_count
    ]
    invalid_count = len(toc_entries) - len(valid_entries)

    if invalid_count > 0:
        print(
            f"\n⚠️  {invalid_count} entries have invalid page numbers and will be skipped"
        )

    # Display complete TOC
    print("\n" + "=" * 60)
    print(
        f"Using {len(valid_entries)} valid TOC entries (out of {len(toc_entries)} total):"
    )
    print("=" * 60)
    for i, (title, page) in enumerate(valid_entries, 1):
        print(f"{i:2d}. Page {page:3d}: {title}")

    # Get user confirmation with support for y/n/digit
    if valid_entries:
        result = get_user_confirmation(valid_entries)

        # Handle different response types
        if result is False:
            print("Operation cancelled.")
            sys.exit(0)
        elif isinstance(result, bool) and result is True:
            # Proceed with current entries
            pass
        elif isinstance(result, int):
            # Apply offset to all page numbers
            offset = result
            print(f"\n→ Applying offset of {offset:+d} to all page numbers...")
            valid_entries = apply_offset_to_entries(valid_entries, offset)

            # Show updated entries
            print("\nUpdated TOC entries after offset:")
            print("=" * 60)
            for i, (title, page) in enumerate(valid_entries, 1):
                print(f"{i:2d}. Page {page:3d}: {title}")

            # Re-validate against PDF page count
            revalidated = [
                (title, page)
                for title, page in valid_entries
                if 1 <= page <= pdf_page_count
            ]
            revalidated_invalid = len(valid_entries) - len(revalidated)

            if revalidated_invalid > 0:
                print(
                    f"\n⚠️  After offset, {revalidated_invalid} entries are outside PDF range (1-{pdf_page_count})"
                )
                print("These entries will be skipped.")
                valid_entries = revalidated

            if not valid_entries:
                print("\n❌ No valid entries remain after applying offset. Exiting.")
                sys.exit(1)

        # Perform the chosen action
        if args.split:
            split_pdf_by_song(
                input_pdf,
                valid_entries,
                output_dir=args.split_dir,
                add_bookmarks=args.split_bookmarks,
            )
        else:
            add_bookmarks_to_pdf(input_pdf, output_pdf, valid_entries)
    else:
        print("\n❌ No valid entries to process. Exiting.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
