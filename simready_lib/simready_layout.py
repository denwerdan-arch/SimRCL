"""Geometry of the browser panels as pure functions, so drawing and mouse hit-testing share one source.

No Cinema 4D imports: everything here is tuples and numbers, which also makes it testable outside Cinema 4D.
"""
import math
import textwrap
from collections import namedtuple

import simready_catalog as cat
import simready_dims as dims

SIDEBAR_W = 257
DETAIL_W = 400
HEADER_H = 58
TOOLBAR_H = 46

GRID_PAD = 16
GRID_GAP = 16
CARD_SIZES = {"S": 180, "M": 250, "L": 340}
MAX_STRETCH = 1.2  # a card may grow this much to fill a row; more and S, M and L look alike in a narrow panel
LIST_ROW_H = 76
LIST_THUMB = 60
OVERLAY_H = 49
END_MARGIN = 900  # start loading the next page this far before the end of the content

SECTION_H = 36
LIBRARY_H = 38
ROW_H = 30
INDENT = 14
PAD = 20

Item = namedtuple("Item", "kind rect data")


def rect_contains(rect, x, y):
    """True when pixel (x, y) lies inside rect = (x1, y1, x2, y2), borders included."""
    return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


def item_at(items, x, y):
    """Topmost item under (x, y), or None; later items are drawn later and therefore win."""
    for item in reversed(items):
        if rect_contains(item.rect, x, y):
            return item
    return None


# ---------------------------------------------------------------- results grid

def grid_columns(width, size_key):
    """Number of card columns for the thumbnail size."""
    return max(1, (width - 2 * GRID_PAD + GRID_GAP) // (CARD_SIZES[size_key] + GRID_GAP))


def grid_cell(width, columns, size_key):
    """Card edge length: stretched to fill the row, but at most MAX_STRETCH times the chosen size.

    Without the cap a panel too narrow for two cards made every size one full-width card (S looked like L).
    """
    filled = (width - 2 * GRID_PAD - (columns - 1) * GRID_GAP) // columns
    return max(1, min(filled, int(CARD_SIZES[size_key] * MAX_STRETCH)))


def grid_left(width, columns, cell):
    """Left edge of the first column; a row narrower than the panel is centred."""
    row = columns * cell + (columns - 1) * GRID_GAP
    return max(GRID_PAD, (width - row) // 2)


def card_rect(index, columns, cell, left=GRID_PAD):
    """Rectangle of card number index in the grid view."""
    row, col = divmod(index, columns)
    x = left + col * (cell + GRID_GAP)
    top = GRID_PAD + row * (cell + GRID_GAP)
    return x, top, x + cell, top + cell


def list_rect(index, width):
    """Rectangle of row number index in the list view."""
    top = GRID_PAD + index * (LIST_ROW_H + 4)
    return GRID_PAD, top, width - GRID_PAD, top + LIST_ROW_H


def results_height(width, count, size_key, as_list, footer=0):
    """Pixel height of the whole results area; the footer holds the loading note."""
    if as_list:
        body = GRID_PAD + count * (LIST_ROW_H + 4)
    else:
        columns = grid_columns(width, size_key)
        cell = grid_cell(width, columns, size_key)
        rows = math.ceil(count / columns) if count else 0
        body = GRID_PAD + rows * (cell + GRID_GAP)
    return body + footer + GRID_PAD


def result_rects(count, width, size_key, as_list):
    """Rectangles of all cards in display order."""
    if as_list:
        return [list_rect(i, width) for i in range(count)]
    columns = grid_columns(width, size_key)
    cell = grid_cell(width, columns, size_key)
    left = grid_left(width, columns, cell)
    return [card_rect(i, columns, cell, left) for i in range(count)]


def visible_range(rects, top, bottom):
    """Indices of rects that intersect the vertical band top..bottom."""
    return [i for i, r in enumerate(rects) if r[3] >= top and r[1] <= bottom]


# ---------------------------------------------------------------- sidebar

def _row(items, kind, y, height, width, data):
    items.append(Item(kind, (0, y, width, y + height), data))
    return y + height


def _section_items(items, y, width, key, title):
    return _row(items, "section", y, SECTION_H, width, (key, title))


PROVIDER_KIND_LABELS = dict((("all", "All"),) + cat.GROUP_LABELS)
GROUP_H = 24


def provider_buttons(rect, kinds):
    """[(kind, rectangle)] of the All / OEMs / ISVs / DSX switch inside its row: equal segments."""
    left, right = PAD, rect[2] - PAD
    step = (right - left) / max(1, len(kinds))
    return [(kind, (int(left + i * step), rect[1] + 3, int(left + (i + 1) * step) - 2, rect[3] - 3)) for i, kind in enumerate(kinds)]


def _provider_items(items, y, width, state, catalog):
    providers = cat.provider_list(catalog)
    if not providers:
        return y
    kinds = cat.provider_kinds(providers)
    kind = state.get("provider_kind", "all")
    kind = kind if kind in kinds else "all"
    if len(kinds) > 2:
        y = _row(items, "provider_kind", y, ROW_H, width, (kinds, kind))
    for heading, count, members in cat.provider_groups(providers, kind):
        if heading:
            y = _row(items, "provider_group", y, GROUP_H, width, (heading, count))
        for provider in members:
            y = _row(items, "provider", y, ROW_H - 4, width, (provider, provider.key in state["selection"]["nodes"]))
    return y


def _hierarchy_items(items, y, width, state, catalog):
    y = _row(items, "depth", y, ROW_H, width, state["depth"])
    hidden = cat.provider_branch_keys(catalog.tree)
    for node, level, expandable, is_open in cat.visible_rows(catalog.tree, state["expanded"], state["depth"], hidden):
        data = (node, level, expandable, is_open, node.key in state["selection"]["nodes"])
        y = _row(items, "tree", y, ROW_H, width, data)
    return y


def _option_rows(items, y, width, facet, options, chosen):
    for option in options:
        y = _row(items, "option", y, ROW_H - 4, width, (facet, option, option.key in chosen))
    return y


def _facet_items(items, y, width, state, facet, title, options, chosen):
    is_open = facet in state["open_facets"]
    y = _row(items, "facet", y, ROW_H, width, (facet, title, is_open, bool(chosen)))
    return _option_rows(items, y, width, facet, options, chosen) if is_open else y


DIM_ROW_H, RESET_H = 34, 22


def _dimension_items(items, y, width, state):
    """Facet header ('Any' while open on every axis), one min / slider / max row per axis, Reset when set."""
    limits = state["selection"]["dims"]
    is_open, active = "dims" in state["open_facets"], dims.active(limits)
    y = _row(items, "facet", y, ROW_H, width, ("dims", "Dimensions (m)", is_open, active, "" if active else "Any"))
    if not is_open:
        return y
    for axis, axis_limits in enumerate(limits):
        y = _row(items, "dim", y, DIM_ROW_H, width, (axis, axis_limits))
    return _row(items, "dims_reset", y, RESET_H, width, None) if active else y


def dim_parts(rect):
    """x ranges of the label, min field, slider track and max field inside a dimension row."""
    return dims.row_parts(PAD + 4, rect[2] - PAD)


def sidebar_items(state, catalog, width):
    """Rows of the left panel top to bottom, each with its pixel rectangle; also returns the content height."""
    items, y = [], 0
    y = _row(items, "library", y, LIBRARY_H, width, (state["only_downloaded"], state["library_count"]))
    y = _section_items(items, y + 1, width, "provider", "PROVIDER")
    if "provider" not in state["closed_sections"] and catalog:
        y = _provider_items(items, y, width, state, catalog)
    y = _section_items(items, y + 4, width, "hierarchy", "HIERARCHY")
    if "hierarchy" not in state["closed_sections"] and catalog:
        y = _hierarchy_items(items, y, width, state, catalog)
    y = _section_items(items, y + 4, width, "simready", "SIMREADY")
    if "simready" not in state["closed_sections"] and catalog:
        sel = state["selection"]
        y = _facet_items(items, y, width, state, "profiles", "Profile", cat.profile_options(catalog.stats), sel["profiles"])
        y = _facet_items(items, y, width, state, "rigid", "Rigid bodies", cat.rigid_options(catalog.stats), _as_set(sel["rigid"]))
        y = _facet_items(items, y, width, state, "mass", "Mass", cat.mass_options(catalog.stats), _as_set(sel["mass"]))
    y = _section_items(items, y + 4, width, "filters", "FILTERS")
    if "filters" not in state["closed_sections"] and catalog:
        y = _facet_items(items, y, width, state, "licenses", "License", cat.license_options(catalog.stats), state["selection"]["licenses"])
        y = _dimension_items(items, y, width, state)
    items.append(Item("footer", (0, y + 20, width, y + 20 + FOOTER_H), None))
    return items, y + 24 + FOOTER_H


FOOTER_H = 130


def footer_rows(rect):
    """Rectangles inside the sidebar footer: the cache button, two links and the product line."""
    left, top, right = PAD, rect[1], rect[2] - PAD
    return {"clear": (left, top + 6, right, top + 36), "guide": (left, top + 48, right, top + 68),
            "notices": (left, top + 70, right, top + 90), "brand": (left, top + 104, right, top + 124)}


def _as_set(value):
    return () if value is None else (str(value),)


# ---------------------------------------------------------------- detail panel

def cover_crop(bw, bh, rw, rh):
    """(x, y, w, h) of the centred part of a bw x bh picture that has the rw x rh aspect."""
    if bw * rh > bh * rw:
        width = max(1, bh * rw // rh)
        return (bw - width) // 2, 0, width, bh
    height = max(1, bw * rh // rw)
    return 0, (bh - height) // 2, bw, height


def contain_rect(bw, bh, rect):
    """Largest rectangle with the bw x bh aspect centred inside rect (letterbox / pillarbox)."""
    rw, rh = rect[2] - rect[0], rect[3] - rect[1]
    scale = min(rw / float(bw), rh / float(bh))
    width, height = int(bw * scale), int(bh * scale)
    left, top = rect[0] + (rw - width) // 2, rect[1] + (rh - height) // 2
    return left, top, left + width, top + height


def wrap_lines(text, width, char_px=7.0, max_lines=8):
    """Lines of text that fit width pixels, with a character width estimate (text cannot be measured while laying out).

    The same estimate fixes the height and the lines, so the drawing never exceeds the space it was given; the
    last line ends with an ellipsis when the text is longer than max_lines.
    """
    per_line = max(12, int(width / char_px))
    lines = textwrap.wrap(" ".join(str(text).split()), per_line, break_long_words=True)
    if len(lines) <= max_lines:
        return lines
    return lines[:max_lines - 1] + [lines[max_lines - 1][:per_line - 3].rstrip() + "..."]


def detail_blocks(width, has_tabs=True):
    """Fixed vertical positions of the detail panel blocks (the panel scrolls below the tabs)."""
    pad = 16
    return {
        "title": (pad, 14, width - pad, 44), "nav": (pad, 50, width - pad, 76),
        "tabs": (pad, 90, width - pad, 126), "preview_top": 138,
        "preview": (pad, 138, width - pad, 138 + int((width - 2 * pad) * 0.625)),
        "pad": pad,
    }
