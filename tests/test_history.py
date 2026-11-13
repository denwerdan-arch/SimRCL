"""Sandbox checks of the package history: commit titles, date merging, first-seen tracking and paging."""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_history as history  # noqa: E402

KEY = "https://huggingface.co/datasets/%s/blob/%s/%s/simready_usd/%s.usd"


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def commit(cid, title, date):
    return {"id": cid, "title": title, "date": date}


def fake_api(pages):
    """get() that serves pages[repo][page] and counts the requests."""
    calls = []

    def get(url):
        calls.append(url)
        repo = url.split("/datasets/")[1].split("/commits/")[0]
        page = int(url.rsplit("p=", 1)[1])
        return pages[repo][page] if page < len(pages[repo]) else []
    return get, calls


def main():
    nv = [commit("c4", "deploy gone_a01 into nvidia/simready-assets@main", "2026-11-03T10:00:00.000Z"),
          commit("c3", "deploy soap_a01 from nvidia/srp-staging@a9", "2026-11-02T10:00:00.000Z"),
          commit("c2", "Update README.md", "2026-11-01T10:00:00.000Z"),
          commit("c1", "deploy soap_a01 from nvidia/srp-staging@a1", "2026-10-01T10:00:00.000Z")]
    keys = [KEY % ("nvidia/simready-assets", "aaaa111", "soap_a01", "sm_soap"),
            KEY % ("nvidia/simready-assets", "aaaa111", "old_a01", "sm_old"),
            KEY % ("ForgeCAD/simready-assets", "bbbb222", "tagine", "tagine")]
    forge = [commit("f1", "Add SimReady package: tagine", "2026-11-10T08:00:00.000Z")]
    get, calls = fake_api({"nvidia/simready-assets": [nv], "ForgeCAD/simready-assets": [forge]})
    folder = tempfile.mkdtemp()
    first = history.refresh(folder, keys, "2026-11-13", get)
    first_calls = len(calls)
    again = history.refresh(folder, keys, "2026-11-14", get)
    added_later = keys + [KEY % ("nvidia/simready-assets", "aaaa111", "batch_x", "sm_batch")]
    later = history.refresh(folder, added_later, "2026-11-15", get)
    today = datetime.date(2026, 11, 13)
    paged_get, paged_calls = fake_api({"r/x": [[commit("p%d" % i, "x", "d") for i in range(3)], [commit("p3", "x", "d")]]})
    history.PAGE_LIMIT, limit = 3, history.PAGE_LIMIT
    paged = history.fetch_commits("r/x", None, paged_get)
    stopped = history.fetch_commits("r/x", "p1", paged_get)
    history.PAGE_LIMIT = limit
    results = [
        check("deploy from", history.packages_of("deploy food_cereal_g01 from nvidia/srp-staging-controlled@a9"), ["food_cereal_g01"]),
        check("deploy into", history.packages_of("deploy box_flat_a16 into nvidia/simready-assets@main"), ["box_flat_a16"]),
        check("add title", history.packages_of("Add SimReady package: D01059"), ["D01059"]),
        check("qualified list", history.packages_of("Add qualified SimReady packages: D00593, D00594"), ["D00593", "D00594"]),
        check("batch title names nothing", history.packages_of("Publish 6 SimReady package/report requests"), []),
        check("evidence is no addition", history.packages_of("Preserve official SimReady benchmark evidence: D00972"), []),
        check("history packages outside the catalog are left out", ("nvidia/simready-assets", "gone_a01") in first, False),
        check("added is the first deploy", first[("nvidia/simready-assets", "soap_a01")][:10], "2026-10-01"),
        check("other repository", first[("ForgeCAD/simready-assets", "tagine")][:10], "2026-11-10"),
        check("packages present at the start have no date", ("nvidia/simready-assets", "old_a01") in first, False),
        check("one request per repository", first_calls, 2),
        check("unchanged revisions are not fetched again", (len(calls) - first_calls, again == first), (0, True)),
        check("a package seen later gets that day", later[("nvidia/simready-assets", "batch_x")], "2026-11-15"),
        check("new within 14 days", history.is_new("2026-11-02T10:00:00Z", today), True),
        check("not new after 14 days", history.is_new("2026-10-01T10:00:00Z", today), False),
        check("no date, never new", history.is_new(None, today), False),
        check("paging reads every page", [c["id"] for c in paged], ["p0", "p1", "p2", "p3"]),
        check("paging stops at the known head", [c["id"] for c in stopped], ["p0"]),
    ]
    print(all(results))
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
