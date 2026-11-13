"""Sandbox checks of Date added in the catalog: stamping, sorting, the menu entry and the newest packages."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_catalog as cat  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def card(package, repo="nvidia/simready-assets"):
    return {"key": package, "filename": package + ".usd", "title": None, "bytes": 1, "dims": None, "joints": 0,
            "modified": None, "asset": {"ref": {"repo": repo, "package": package}}}


def main():
    cards = [card("old"), card("new"), card("unknown")]
    added = {("nvidia/simready-assets", "new"): "2026-11-10T08:00:00.000Z",
             ("nvidia/simready-assets", "old"): "2026-10-01T08:00:00.000Z", ("ForgeCAD/simready-assets", "tagine"): "2026-11-12"}
    stamped = cat.stamp_added(cards, added)
    results = [
        check("cards carry no date before the history", cards[0].get("added"), None),
        check("stamped dates", [c["added"] for c in stamped], ["2026-10-01T08:00:00.000Z", "2026-11-10T08:00:00.000Z", None]),
        check("newest first, undated last", [c["key"] for c in cat.sort_cards(stamped, "added", True)], ["new", "old", "unknown"]),
        check("oldest first, undated still last", [c["key"] for c in cat.sort_cards(stamped, "added")], ["old", "new", "unknown"]),
        check("not offered from undated cards alone", "added" in dict(cat.available_sort_options(stamped[2:])), False),
        check("offered once the history is known", "added" in dict(cat.available_sort_options(stamped[2:], cat.ALWAYS_SORTS + ("added",))), True),
        check("newest packages", cat.newest_packages(added, 2), [("ForgeCAD/simready-assets", "tagine"), ("nvidia/simready-assets", "new")]),
        check("day format", (cat.format_day("2026-11-02T10:00:00.000Z"), cat.format_day("2026-11-15"), cat.format_day(None)),
              ("02.11.2026", "15.11.2026", "")),
    ]
    print(all(results))
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
