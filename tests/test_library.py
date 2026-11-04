"""Sandbox checks of simready_library (temporary folders only)."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_client  # noqa: E402
import simready_library as library  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def make_package(root, repo_dir, commit, package, complete=True):
    folder = os.path.join(root, repo_dir, commit, package)
    os.makedirs(folder)
    if complete:
        open(os.path.join(folder, simready_client.COMPLETE_MARKER), "w").close()


def card(repo, commit, package):
    return {"key": "%s/%s/%s" % (repo, commit, package),
            "asset": {"ref": {"repo": repo, "commit": commit, "package": package}}}


def main():
    root = tempfile.mkdtemp()
    make_package(root, "nvidia__simready-assets", "653d91e18201", "equipment_trash_trolley_a01")
    make_package(root, "nvidia__simready-assets", "111111111111", "box_cube_a10")
    make_package(root, "nvidia__simready-assets", "653d91e18201", "unfinished_a01", complete=False)
    entries = library.scan(root)
    keys = library.index(entries)
    results = [check("scan finds complete packages only", sorted(e["package"] for e in entries), ["box_cube_a10", "equipment_trash_trolley_a01"])]
    results.append(check("repo name restored", {e["repo"] for e in entries}, {"nvidia/simready-assets"}))
    trolley = card("nvidia/simready-assets", "653d91e18201aabbccddeeff00112233445566", "equipment_trash_trolley_a01")
    newer = card("nvidia/simready-assets", "999999999999aabbccddeeff00112233445566", "box_cube_a10")
    other = card("nvidia/simready-assets", "653d91e18201aabbccddeeff00112233445566", "never_downloaded")
    results.append(check("state", [library.state(c, keys) for c in (trolley, newer, other)], [library.CURRENT, library.OUTDATED, None]))
    results.append(check("keep_downloaded", [c["key"] for c in library.keep_downloaded([trolley, newer, other, trolley], keys)], [trolley["key"], newer["key"]]))
    results.append(check("missing folder", library.scan(os.path.join(root, "nope")), []))
    many = {("nvidia/simready-assets", "package_number_%03d_with_a_long_name" % i): {"x"} for i in range(80)}
    chunks = library.regexp_chunks(many)
    results.append(check("chunks are short", all(len(c) <= 1000 for c in chunks) and len(chunks) > 1, True))
    results.append(check("every package is matched once", sum(c.count("package_number_") for c in chunks), 80))
    pattern = re.compile(library.regexp_chunks(keys)[0])
    url = "hf://huggingface.co/datasets/nvidia/simready-assets/resolve/653d91e18201aabb/equipment_trash_trolley_a01/simready_usd/x.usd"
    results.append(check("regexp matches a package file", bool(pattern.fullmatch(url)), True))
    results.append(check("regexp rejects another package", bool(pattern.fullmatch(url.replace("equipment_trash_trolley_a01", "other_a01"))), False))
    results.append(check("no packages, no chunks", library.regexp_chunks({}), []))
    print(all(results))


main()
