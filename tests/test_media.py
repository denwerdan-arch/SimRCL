"""Sandbox checks of the preview cache and the bitmap cache (no network, no Cinema 4D)."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_media as media  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def write(folder, name, size, age):
    path = os.path.join(folder, name)
    with open(path, "wb") as handle:
        handle.write(b"x" * size)
    stamp = time.time() - age
    os.utime(path, (stamp, stamp))
    return path


def main():
    folder = tempfile.mkdtemp()
    for index in range(10):
        write(folder, "p%d.jpg" % index, 1000, age=1000 - index * 10)  # p0 oldest
    other = write(folder, "keep.txt", 500, 5000)
    results = [check("usage", media.preview_usage(folder), (10, 10000))]
    removed, freed = media.prune_previews(folder, 6000)
    results.append(check("prune count", (removed, freed), (6, 6000)))  # target 80 % of 6000 = 4800: five removals leave 5000, so six
    results.append(check("oldest removed", sorted(os.listdir(folder))[:2], ["keep.txt", "p6.jpg"]))
    results.append(check("prune under limit", media.prune_previews(folder, 10 ** 6), (0, 0)))
    results.append(check("clear", media.clear_previews(folder), (4, 4000)))
    results.append(check("other files kept", os.path.isfile(other), True))
    results.append(check("empty usage", media.preview_usage(folder), (0, 0)))
    results.append(check("missing folder", media.preview_usage(os.path.join(folder, "nope")), (0, 0)))
    evicted = []
    cache = media.BitmapCache(2, evicted.append)
    cache.put("a", 1), cache.put("b", 2), cache.get("a"), cache.put("c", 3)
    results.append(check("lru evicts least recently used", (evicted, cache.get("a"), cache.get("b")), (["b"], 1, None)))
    print(all(results))


main()
