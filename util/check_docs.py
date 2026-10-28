#!/usr/bin/env python3
"""Checks that the docs still match the repo. Run with `make docs-check`; see docs/testing.md.

Usage: check_docs.py ROOT

Fails (exit 1) when:
  - a relative link in a Markdown file doesn't resolve (docs/artifacts/ is skipped: it's history;
    so are TEMPLATE.md files, whose links are placeholders);
  - a folder in services/ isn't named in docs/codemap.md;
  - an entry in util/ isn't named, in backticks, in util/SCRIPTS.md;
  - an agent pointer file (CLAUDE.md, GEMINI.md, .github/copilot-instructions.md, .agents/rules/*.md)
    holds anything beyond its pointer to AGENTS.md, which is the single source of agent instructions.

Stdlib only, so it runs in any Python 3 image with no network.
"""
import os
import re
import sys
from urllib.parse import unquote

SKIP_DIRS = {".git", "node_modules"}
SKIP_PREFIX = "docs/artifacts/"

INLINE_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)")
REF_LINK = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>]+)")
CODE_SPAN = re.compile(r"`[^`]*`")
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def markdown_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        if rel_dir.startswith(SKIP_PREFIX):
            dirnames[:] = []
            continue
        for name in sorted(filenames):
            if name.endswith(".md"):
                yield rel_dir + name


def link_targets(text):
    """Yields the link targets in Markdown text, skipping fenced code blocks and code spans."""
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = CODE_SPAN.sub("", line)
        yield from INLINE_LINK.findall(line)
        yield from REF_LINK.findall(line)


def check_links(root, rel, text):
    problems = []
    for target in link_targets(text):
        if target.startswith("#") or SCHEME.match(target):
            continue
        path = unquote(re.split(r"[#?]", target, maxsplit=1)[0])
        if not path:
            continue
        if path.startswith("/"):
            resolved = os.path.join(root, path.lstrip("/"))
        else:
            resolved = os.path.join(root, os.path.dirname(rel), path)
        if not os.path.exists(resolved):
            problems.append(f"{rel}: broken link {target}")
    return problems


def check_listed(root, folder, index, pattern):
    """Every entry in FOLDER must match PATTERN (built from its name) somewhere in INDEX."""
    folder_path = os.path.join(root, folder)
    if not os.path.isdir(folder_path):
        return []
    index_path = os.path.join(root, index)
    if not os.path.isfile(index_path):
        return [f"{index}: missing (it must list every entry in {folder}/)"]
    with open(index_path, encoding="utf-8") as f:
        text = f.read()
    return [
        f"{index}: doesn't list {folder}/{name}"
        for name in sorted(os.listdir(folder_path))
        if os.path.join(folder, name) != index and not re.search(pattern(name), text)
    ]


def content_lines(text):
    """Lines that aren't blank, headings or leading frontmatter."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), 0)
        lines = lines[end + 1:]
    return [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]


def check_pointer(root, rel, text):
    lines = content_lines(text)
    name = os.path.basename(rel)
    if name in ("CLAUDE.md", "GEMINI.md") or rel.startswith(".agents/rules/"):
        if lines != ["@AGENTS.md"]:
            return [f"{rel}: must hold only '@AGENTS.md'; put instructions in AGENTS.md"]
        # .agents/rules/ files import the root AGENTS.md; the others import the one beside them.
        if rel.startswith(".agents/"):
            return []
        if not os.path.isfile(os.path.join(root, os.path.dirname(rel), "AGENTS.md")):
            return [f"{rel}: no AGENTS.md beside it"]
        return []
    if len(lines) != 1 or "AGENTS.md" not in lines[0]:
        return [f"{rel}: must hold only a one-line pointer to AGENTS.md"]
    return []


def is_pointer(rel):
    return (
        os.path.basename(rel) in ("CLAUDE.md", "GEMINI.md")
        or rel == ".github/copilot-instructions.md"
        or rel.startswith(".agents/rules/")
    )


def main(root):
    problems = []
    count = 0
    for rel in markdown_files(root):
        count += 1
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            text = f.read()
        if os.path.basename(rel) != "TEMPLATE.md":
            problems += check_links(root, rel, text)
        if is_pointer(rel):
            problems += check_pointer(root, rel, text)
    problems += check_listed(
        root, "services", "docs/codemap.md", lambda n: rf"services/{re.escape(n)}(?![\w-])"
    )
    problems += check_listed(root, "util", "util/SCRIPTS.md", lambda n: rf"`{re.escape(n)}/?`")
    for p in problems:
        print(f"FAIL {p}")
    print(f"docs-check: {count} Markdown file(s), {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
