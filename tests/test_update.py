"""Sandbox checks of the update check: versions, release JSON, the once-a-day rule and failures."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_update as up  # noqa: E402

RELEASE = {"tag_name": "v1.2.0", "html_url": "https://github.com/denwerdan-arch/SimRCL/releases/tag/v1.2.0",
           "draft": False, "prerelease": False, "body": "Notes",
           "assets": [{"name": "SimRCL_by_Dead_wall_v1.2.0.zip", "browser_download_url": "https://x/SimRCL.zip"}]}
DAY = up.CHECK_INTERVAL_SECONDS


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def failing():
    raise OSError("offline")


def main():
    info = up.release_info(RELEASE)
    calls = []

    def fetch():
        calls.append(1)
        return info

    first = up.check("1.1.0", {}, 1000.0, fetch=fetch)
    cached = up.check("1.1.0", first[1], 1000.0 + DAY - 1, fetch=fetch)
    offline = up.check("1.1.0", first[1], 1000.0 + DAY + 1, fetch=failing)
    results = [
        check("versions parse", (up.parse_version("v1.2.0"), up.parse_version("1.2"), up.parse_version("nightly")),
              ((1, 2, 0), (1, 2, 0), None)),
        check("1.10 is newer than 1.9", up.is_newer("1.10.0", "1.9.0"), True),
        check("same is not newer", up.is_newer("v1.1.0", "1.1.0"), False),
        check("junk is not newer", up.is_newer("latest", "1.1.0"), False),
        check("release info", info, {"version": "1.2.0", "url": RELEASE["html_url"], "zip": "https://x/SimRCL.zip",
                                     "notes": "Notes"}),
        check("pre-release ignored", up.release_info(dict(RELEASE, prerelease=True)), None),
        check("draft ignored", up.release_info(dict(RELEASE, draft=True)), None),
        check("no zip asset", up.release_info(dict(RELEASE, assets=[]))["zip"], None),
        check("first check fetches", (first[0]["version"], first[2], len(calls)), ("1.2.0", None, 1)),
        check("within a day: cached, no request", (cached[0]["version"], len(calls)), ("1.2.0", 1)),
        check("forced check fetches", (up.check("1.1.0", first[1], 1001.0, True, fetch)[2], len(calls)), (None, 2)),
        check("offline keeps the cached answer", (offline[0]["version"], offline[2]), ("1.2.0", "offline")),
        check("up to date gives nothing", up.check("1.2.0", first[1], 1000.0, fetch=fetch)[0], None),
        check("clock moved back means due", up.due(5000.0, 1000.0), True),
        check("garbage state is fine", up.check("1.1.0", "junk", 1.0, fetch=fetch)[0]["version"], "1.2.0"),
    ]
    print(all(results))
    return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
