"""Print the CHANGELOG.md section of a version (the text under "## <version>"): python tools/release_notes.py 1.1.0"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def section(text, ver):
    """Lines between '## <ver>' and the next '## ' heading, or '' when the version is not listed."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip() == ver
            continue
        if inside:
            lines.append(line)
    return "\n".join(lines).strip()


if __name__ == "__main__":
    notes = section(open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read(), sys.argv[1])
    if not notes:
        sys.exit("CHANGELOG.md has no section '## %s'" % sys.argv[1])
    print(notes)
