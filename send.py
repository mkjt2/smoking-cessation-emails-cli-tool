#!/usr/bin/env python3
"""Render smoking cessation newsletters mail-merge style into per-recipient text files.

Usage:
    ./send.py --recipient-list <csv_file> --payload-template <text_file> --output-dir <output_subdir>
"""

import argparse
import csv
import re
import sys
from pathlib import Path

SUPPORTED_VARIABLES = {"FULL_NAME"}

# Matches `{FULL_NAME}` and `{ FULL_NAME }`. Braces around anything that is not a
# bare identifier (e.g. CSS or JSON snippets) are left untouched.
PLACEHOLDER_RE = re.compile(r"\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}")

# Deliberately loose: one "@", no whitespace, and no characters that would escape
# or corrupt a file name when the address is used as one.
EMAIL_RE = re.compile(r"^[^@\s/\\]+@[^@\s/\\]+$")


class SendError(Exception):
    """A user-facing error; reported on stderr with a non-zero exit."""


def load_recipients(path):
    """Return [(full_name, email)] from a headerless two-column CSV.

    Blank lines are skipped. Rows with the wrong column count, empty fields,
    invalid email addresses, or duplicate addresses (case-insensitive) are errors.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    except OSError as e:
        raise SendError(f"cannot read recipient list {path}: {e.strerror}") from e
    except UnicodeDecodeError as e:
        raise SendError(f"recipient list {path} is not valid UTF-8") from e

    recipients = []
    seen = {}
    for lineno, row in enumerate(rows, start=1):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != 2:
            raise SendError(f"{path}:{lineno}: expected 2 columns (full name, email), got {len(row)}")
        name, email = row[0].strip(), row[1].strip()
        if not name:
            raise SendError(f"{path}:{lineno}: full name is empty")
        if not EMAIL_RE.match(email):
            raise SendError(f"{path}:{lineno}: invalid email address {email!r}")
        key = email.lower()
        if key in seen:
            raise SendError(f"{path}:{lineno}: duplicate email address {email!r} (first seen on line {seen[key]})")
        seen[key] = lineno
        recipients.append((name, email))

    if not recipients:
        raise SendError(f"recipient list {path} has no recipients")
    return recipients


def load_template(path):
    """Read the payload template and reject any unsupported template variables."""
    try:
        template = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise SendError(f"cannot read payload template {path}: {e.strerror}") from e
    except UnicodeDecodeError as e:
        raise SendError(f"payload template {path} is not valid UTF-8") from e

    unknown = sorted({m.group(1) for m in PLACEHOLDER_RE.finditer(template)} - SUPPORTED_VARIABLES)
    if unknown:
        supported = ", ".join(sorted(SUPPORTED_VARIABLES))
        raise SendError(
            f"payload template {path} uses unsupported variable(s): {', '.join(unknown)} (supported: {supported})"
        )
    return template


def render(template, full_name):
    """Substitute template variables. The name is inserted literally, never re-parsed."""
    return PLACEHOLDER_RE.sub(lambda m: full_name, template)


def output_path(output_dir, email):
    return Path(output_dir) / f"{email.lower()}.txt"


def run(recipient_list, payload_template, output_dir):
    """Render one file per recipient into output_dir. Returns the written paths."""
    # Validate every input before touching the filesystem so a bad row never
    # leaves a half-written output directory behind.
    recipients = load_recipients(recipient_list)
    template = load_template(payload_template)

    out = Path(output_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise SendError(f"cannot create output directory {out}: {e.strerror}") from e
    if not out.is_dir():
        raise SendError(f"output path {out} is not a directory")

    written = []
    for name, email in recipients:
        path = output_path(out, email)
        try:
            path.write_text(render(template, name), encoding="utf-8")
        except OSError as e:
            raise SendError(f"cannot write {path}: {e.strerror}") from e
        written.append(path)
    return written


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Render smoking cessation newsletters, one text file per recipient."
    )
    parser.add_argument(
        "--recipient-list", required=True, metavar="CSV_FILE",
        help="headerless CSV with two columns: full name, email address",
    )
    parser.add_argument(
        "--payload-template", required=True, metavar="TEXT_FILE",
        help="text email payload; {FULL_NAME} is replaced with each recipient's name",
    )
    parser.add_argument(
        "--output-dir", required=True, metavar="OUTPUT_SUBDIR",
        help="directory for rendered payloads (created if missing); files are named <email>.txt",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        written = run(args.recipient_list, args.payload_template, args.output_dir)
    except SendError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Rendered {len(written)} newsletter(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
