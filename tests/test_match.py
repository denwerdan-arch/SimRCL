"""Sandbox checks of the match percentages: stream parsing, sort key, mode descriptions (no network)."""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_catalog as cat  # noqa: E402
import simready_client as client  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


STREAM = [
    {"id": "1", "verdict": {"is_match": True, "similarity_score": 99.6}},
    {"id": "0", "verdict": {"is_match": False, "similarity_score": 2.4}},
    {"id": "2", "error": "no preview"},
    {"done": {"completed": 2, "errored": 1}},
]


def card(key, match=None):
    found = {"key": key, "filename": key + ".usd", "title": None, "bytes": None, "dims": None, "joints": 0, "modified": None}
    if match is not None:
        found["match"] = match
    return found


def main():
    sent = {}

    def fake_urlopen(request, timeout=None):
        sent.update(json.loads(request.data))
        return FakeResponse(("\n".join(json.dumps(line) for line in STREAM) + "\n\n").encode())

    client.urllib.request.urlopen = fake_urlopen
    scores = client.match_scores("scissors", ["a", "b", "c"])
    ordered = cat.sort_cards([card("a", 2), card("b"), card("c", 100)], "match", descending=True)
    results = [
        check("percentages by asset, failures left out", scores, {"b": 100, "a": 2}),
        check("request", (sent["query_text"], [item["asset_url"] for item in sent["items"]]), ("scissors", ["a", "b", "c"])),
        check("match sort, unscored last", [c["key"] for c in ordered], ["c", "a", "b"]),
        check("match sort offered only with scores", "match" in dict(cat.available_sort_options([card("a"), card("b")])), False),
        check("every mode described", sorted(client.MODE_DESCRIPTIONS) == sorted(client.TEXT_MODES), True),
    ]
    print(all(results))


main()
