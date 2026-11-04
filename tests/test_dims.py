"""Sandbox checks of the size filter: slider scale, typed values, clamping, dragging, service fields, chips."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_catalog as cat  # noqa: E402
import simready_dims as dims  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def main():
    track = (100, 300)
    selection = cat.set_dimension(cat.empty_selection(), 0, (0.5, 2.0))
    selection = cat.set_dimension(selection, 2, (None, 1.2))
    results = [
        check("cubic scale ends", (dims.value_at(0), dims.value_at(200)), (0.0, 100.0)),
        check("1 m sits near step 43", round(dims.step_of(1.0)), 43),
        check("scale round trip", round(dims.value_at(dims.step_of(3.7)), 6), 3.7),
        check("site rounding", (dims.rounded(0.12345), dims.rounded(3.456), dims.rounded(42.6)), (0.12, 3.5, 43)),
        check("typed values", (dims.parse(" 1,5 m"), dims.parse(""), dims.parse("0")), (1.5, None, None)),
        check("negative refused", _raises(lambda: dims.parse("-1")), True),
        check("edited min gives way", dims.clamp(5.0, 2.0, "min"), (2.0, 2.0)),
        check("edited max gives way", dims.clamp(5.0, 2.0, "max"), (5.0, 5.0)),
        check("untouched slider is open", dims.thumb_steps(dims.NO_LIMIT), (0, 200)),
        check("ends mean no limit", dims.from_steps(0, 200), (None, None)),
        check("press picks the nearer thumb", (dims.nearer_thumb(10, dims.NO_LIMIT), dims.nearer_thumb(190, dims.NO_LIMIT)), ("min", "max")),
        check("thumbs never cross", dims.drag((None, 1.0), "min", 200), (1.0, 1.0)),
        check("drag max to the left (whole metres above 10)", dims.drag(dims.NO_LIMIT, "max", 100), (None, 12.0)),
        check("pixel to step", (dims.step_at(100, track), dims.step_at(200, track), dims.step_at(400, track)), (0, 100, 200)),
        check("row parts", [dims.part_at(x, dims.row_parts(20, 300)) for x in (30, 50, 150, 280)], [None, "min", "track", "max"]),
        check("service fields", cat.search_fields(selection, _catalog()), {"min_bbox_x": 0.5, "max_bbox_x": 2.0, "max_bbox_z": 1.2}),
        check("chips", [dims.chip(a, l) for a, l in enumerate(selection["dims"])], ["X 0.5–2 m", None, "Z ≤ 1.2 m"]),
        check("min only chip", dims.chip(1, (3.0, None)), "Y ≥ 3 m"),
        check("filtering when set", (cat.is_filtering(selection), cat.is_filtering(cat.clear_dimensions(selection))), (True, False)),
    ]
    print(all(results))


def _raises(call):
    try:
        call()
    except ValueError:
        return True
    return False


def _catalog():
    return cat.Catalog(**{field: {} for field in cat.Catalog._fields})


main()
