#!/usr/bin/env python3
"""Lint article files against the site contract. Stdlib only.

Usage: python3 scripts/check.py [path ...]
Exits 1 on errors; warnings don't fail the run.
"""

import datetime
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SLUG_RE = re.compile(r"^[a-z0-9-]+$")
TAG_RE = re.compile(r"^[a-z0-9-]+$")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
MAX_FILE = 1 << 20
DESC_MAX = 160
KNOWN_KEYS = {"title", "date", "tags", "description", "draft"}
META_FILES = {"readme.md", "claude.md", "agents.md", "contributing.md", "license.md"}


def article_files(args):
    if args:
        return [pathlib.Path(a) for a in args]
    files = []
    for p in sorted(ROOT.rglob("*.md")):
        rel = p.relative_to(ROOT)
        parts = rel.parts
        if any(part.startswith(".") for part in parts):
            continue
        if parts[0] in ("scripts",):
            continue
        if p.name.lower() in META_FILES:
            continue
        files.append(p)
    return files


def unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def parse_frontmatter(lines):
    """Parse the tolerant YAML subset the site contract uses."""
    fm, errors = {}, []
    if not lines or lines[0].strip() != "---":
        return None, None, ["missing frontmatter block (file must start with ---)"]
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return None, None, ["unterminated frontmatter block"]

    pending_list = None
    for raw in lines[1:end]:
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        item = line.strip()
        if pending_list is not None and item.startswith("- "):
            fm[pending_list].append(unquote(item[2:]))
            continue
        pending_list = None
        m = KEY_RE.match(line)
        if not m:
            errors.append(f"frontmatter line not understood: {line.strip()!r}")
            continue
        key, value = m.group(1), m.group(2).strip()
        if key == "tags":
            if value.startswith("[") and value.endswith("]"):
                items = [unquote(x) for x in value[1:-1].split(",") if x.strip()]
                fm[key] = items
            elif value == "":
                fm[key] = []
                pending_list = key
            else:
                fm[key] = [unquote(value)]
        else:
            fm[key] = unquote(value)
    body = "".join(lines[end + 1:]).strip()
    return fm, body, errors


def check_date(value):
    try:
        datetime.date.fromisoformat(value)
        return None
    except ValueError:
        pass
    if RFC3339_RE.match(value):
        return "warn"
    return "error"


def main(argv):
    files = article_files(argv[1:])
    errors, warnings = [], []
    slugs = {}

    def err(p, msg):
        errors.append(f"{p}: {msg}")

    def warn(p, msg):
        warnings.append(f"{p}: {msg}")

    for path in files:
        rel = path.relative_to(ROOT) if path.is_absolute() else path
        if path.stat().st_size > MAX_FILE:
            err(rel, f"file over 1 MB — the site skips it")
            continue
        slug = path.stem
        if not SLUG_RE.match(slug):
            err(rel, f"slug {slug!r} must match [a-z0-9-]+ (it is the URL)")
        if slug in slugs:
            err(rel, f"duplicate slug — also used by {slugs[slug]}; the site keeps only one")
        else:
            slugs[slug] = rel

        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        fm, body, fm_errors = parse_frontmatter(lines)
        for e in fm_errors:
            err(rel, e)
        if fm is None:
            continue

        for key in fm:
            if key not in KNOWN_KEYS:
                warn(rel, f"unknown frontmatter key {key!r} — the site silently ignores it")

        if not fm.get("title"):
            err(rel, "missing title")
        if not fm.get("date"):
            err(rel, "missing date")
        else:
            verdict = check_date(fm["date"])
            if verdict == "error":
                err(rel, f"date {fm['date']!r} is not YYYY-MM-DD")
            elif verdict == "warn":
                warn(rel, "RFC3339 date works but prefer bare YYYY-MM-DD")

        draft = str(fm.get("draft", "false")).lower()
        if draft not in ("true", "false"):
            err(rel, f"draft must be true or false, got {fm['draft']!r}")
        is_draft = draft == "true"

        desc = fm.get("description", "")
        if not desc and not is_draft:
            warn(rel, "no description — cards, share previews, and search snippets suffer")
        if desc and len(desc) > DESC_MAX:
            warn(rel, f"description is {len(desc)} chars; keep it under {DESC_MAX}")

        for tag in fm.get("tags", []):
            if not TAG_RE.match(tag):
                warn(rel, f"tag {tag!r} should be lowercase [a-z0-9-]+")

        if not body and not is_draft:
            err(rel, "published article has an empty body")

        if fm.get("date") and check_date(fm["date"]) is None:
            d = datetime.date.fromisoformat(fm["date"])
            expected = pathlib.Path(f"{d.year:04d}") / f"{d.month:02d}"
            if rel.parent != expected:
                warn(rel, f"filed under {rel.parent}/ but dated {fm['date']} — convention is {expected}/ (run /tidy)")

    for line in errors:
        print(f"error  {line}")
    for line in warnings:
        print(f"warn   {line}")
    print(f"\n{len(files)} article(s), {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
