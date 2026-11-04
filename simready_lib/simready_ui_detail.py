"""Right panel: asset details and the bottom bar with Dependencies and Download."""
import os

import c4d

import simready_catalog as cat
import simready_client
import simready_layout as layout
import simready_library as library
import simready_ui as ui
import simready_ui_results as results
import simready_video_window as video_window

ACTION_BAR_H = 68
ACTION_BAR_TALL_H = 114  # a second row holds Re-Download once the asset is on disk
LOCAL_TEXT = {library.CURRENT: "Downloaded", library.OUTDATED: "Downloaded (older revision)"}
SIMILAR_GAP = 8
SIMILAR_CAPTION_H = 22
MORE_W = 64
PREVIEW_RATIO = 0.625  # posters are 1280x800


def _text_rows(card):
    """Rows from the vision-model description (colours, materials, setting, ...); only the ones the service sent."""
    vlm = card.get("vlm") or {}
    return [(label, ", ".join(vlm.get(name, []))) for name, label in cat.VLM_TEXT_FIELDS]


def _fact_rows(card):
    """Rows from the full record: polygons, mass, bodies, physics engines, robot type (empty until it is loaded)."""
    extras = card.get("extras") or {}
    return [("Polygons", cat.format_count(extras["polygons"]) if extras.get("polygons") else ""),
            ("Mass", cat.format_mass(card["mass"])), ("Bodies", extras.get("bodies")),
            ("Physics", ", ".join(extras.get("engines") or [])), ("Robot", extras.get("robot"))]


def _author_row(card):
    """Author only when it adds something to the provider (NVIDIA assets made for a partner, for example)."""
    author = (card.get("extras") or {}).get("author")
    return ("Author", author if author and author != card.get("provider") else "")


def detail_rows(card, local_state=None):
    """(label, value) pairs of the details table; empty values are skipped."""
    match = card.get("match")
    rows = [("Match", "%d%% for the search" % match if match is not None else ""), ("Provider", card.get("provider")), _author_row(card), ("Source", card["source_name"]), ("File", card["filename"]),
            ("Category", card["category"]), ("Type", card["asset_type"]), ("License", card["license"]),
            ("Size", cat.format_bytes(card["bytes"])), ("Date", cat.format_modified(card["modified"])), ("Q-code", card["qcode"])]
    rows += _fact_rows(card) + _text_rows(card) + [("Local copy", LOCAL_TEXT.get(local_state))]
    return [(label, str(value)) for label, value in rows if value]


def about_blocks(card):
    """[(heading, text)] of the free-text parts: the caption and the tags, when the service sent them."""
    vlm = card.get("vlm") or {}
    caption = " ".join(vlm.get("caption", []))
    tags = ", ".join(vlm.get("tags", [])[:cat.TAG_LIMIT])
    return [(heading, text) for heading, text in (("DESCRIPTION", caption[:1].upper() + caption[1:]), ("TAGS", tags)) if text]


def nav_text(model):
    """'12 of 240' for a result; 'Similar asset' for a card opened from the Similar strip."""
    if model.detour is not None or model.selected is None:
        return "Similar asset"
    return "%d of %d" % (model.selected + 1, len(model.cards))


def joints_text(card):
    """'6 joints', or 'Static' for assets without moving parts."""
    count = card["joints"]
    return "%d joint%s" % (count, "" if count == 1 else "s") if count else "Static"


def license_is_allowed(card):
    """True when the licence spelling is on the plugin's allow list."""
    return card["license"] in simready_client.ALLOWED_LICENSES


class DetailPanel(ui.Panel):
    """Scrollable detail view of the open card."""

    min_width = layout.DETAIL_W

    def __init__(self, act, model):
        super().__init__(act)
        self.model = model

    def build(self, width):
        """Flow the blocks of the open card from top to bottom."""
        card = self.model.open_card()
        if card is None:
            return [], 10
        pad, items = 16, []
        add = items.append
        add(layout.Item("title", (pad, 12, width - pad, 44), card))
        add(layout.Item("close", (width - 44, 12, width - 16, 44), None))
        copy_left = pad + min(len(self.stem(card)) * 8 + 8, width - 150)  # estimate: text can only be measured while drawing
        add(layout.Item("copy", (copy_left, 20, copy_left + 20, 38), None))
        add(layout.Item("nav", (pad, 50, width - pad, 78), None))
        add(layout.Item("prev", (width - 70, 50, width - 44, 78), None))
        add(layout.Item("next", (width - 44, 50, width - 16, 78), None))
        y = self.add_preview(items, width, 92)
        y = self.add_stats(items, width, y + 14, card)
        y = self.add_about(items, width, y + 6, card)
        y = self.add_details(items, width, y + 18, card)
        y = self.add_similar(items, width, y + 18, card)
        return items, y + 24

    @staticmethod
    def stem(card):
        """File name without extension, the title of the panel."""
        return os.path.splitext(card["filename"])[0]

    @staticmethod
    def add_preview(items, width, y):
        """Poster block; returns the y below it."""
        height = int((width - 32) * PREVIEW_RATIO)
        items.append(layout.Item("preview", (16, y, width - 16, y + height), None))
        return y + height

    @staticmethod
    def add_stats(items, width, y, card):
        """Boxed grid: dimensions and moving parts on the first row, profile on the second."""
        half = width // 2
        items.append(layout.Item("stats_box", (16, y, width - 16, y + 118), None))
        items.append(layout.Item("stat", (28, y + 10, half - 4, y + 54), ("DIMENSIONS", cat.format_dimensions(card["dims"]) or "-")))
        items.append(layout.Item("stat", (half + 8, y + 10, width - 28, y + 54), ("MOVING PARTS", joints_text(card))))
        items.append(layout.Item("stat", (28, y + 64, width - 28, y + 108), ("SIMREADY PROFILE", card["profile"] or "-")))
        return y + 118

    @staticmethod
    def add_about(items, width, y, card):
        """Caption and tags as wrapped paragraphs; the lines are cut with the same estimate that sizes them."""
        for heading, text in about_blocks(card):
            items.append(layout.Item("heading", (16, y + 12, width - 16, y + 32), heading))
            y += 40
            for line in layout.wrap_lines(text, width - 32):
                items.append(layout.Item("para", (16, y, width - 16, y + 20), line))
                y += 20
        return y

    def add_details(self, items, width, y, card):
        """DETAILS heading and one row per property."""
        items.append(layout.Item("heading", (16, y, width - 16, y + 20), "DETAILS"))
        y += 28
        for label, value in detail_rows(card, self.model.download_state(card)):
            items.append(layout.Item("kv", (16, y, width - 16, y + 26), (label, value)))
            y += 26
        return y

    def add_similar(self, items, width, y, card):
        """SIMILAR heading and up to three square tiles of assets of the same kind, found across the whole catalog."""
        others = self.model.similar_to(card)
        items.append(layout.Item("heading", (16, y, width - 16, y + 20), "SIMILAR"))
        items.append(layout.Item("search_more", (width - 16 - MORE_W, y - 4, width - 16, y + 24), cat.search_name(card)))
        y += 28
        if not others:
            return y
        side = (width - 32 - SIMILAR_GAP * (cat.SIMILAR_LIMIT - 1)) // cat.SIMILAR_LIMIT
        for column, other in enumerate(others):
            left = 16 + column * (side + SIMILAR_GAP)
            items.append(layout.Item("similar", (left, y, left + side, y + side + SIMILAR_CAPTION_H), other))
        return y + side + SIMILAR_CAPTION_H

    def paint(self, x1, y1, x2, y2):
        """Draw the blocks that intersect the clip region."""
        if self.model.open_card() is None:
            return
        self.fill((0, y1, 0, y2), ui.LINE)
        for item in self.items:
            if item.rect[3] >= y1 and item.rect[1] <= y2:
                getattr(self, "draw_" + item.kind)(item.rect, item.data)

    def draw_title(self, rect, card):
        self.text(self.stem(card), rect[0], 28, ui.TEXT, ui.BG, c4d.FONT_BOLD, rect[2] - rect[0] - 90)

    def draw_copy(self, rect, data):
        self.frame((rect[0], rect[1], rect[0] + 9, rect[1] + 11), ui.DIM)
        self.frame((rect[0] + 4, rect[1] + 5, rect[0] + 13, rect[1] + 16), ui.DIM)

    def draw_close(self, rect, data):
        self.cross((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2, ui.TEXT, 5)

    def draw_nav(self, rect, data):
        self.text(nav_text(self.model), rect[0] + 22, (rect[1] + rect[3]) // 2, ui.MUTED, ui.BG)

    def draw_prev(self, rect, data):
        self.draw_arrow(rect, ui.LEFT, -1)

    def draw_next(self, rect, data):
        self.draw_arrow(rect, ui.RIGHT, 1)

    def draw_arrow(self, rect, side, direction):
        color = ui.MUTED if self.model.neighbour(direction) is not None else ui.LINE_STRONG
        self.chevron((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2, side, color)

    def draw_preview(self, rect, data):
        """Poster picture of the asset, or its clip while video preview is on (moving parts, else the turn)."""
        card = self.model.open_card()
        frame = self.model.clip_frame("detail", card)
        if frame is not None:
            results.draw_cover(self, frame, rect)
            self.draw_expand(rect, card)
            return
        bitmap = self.model.poster(card)
        if bitmap is None:
            self.fill(rect, ui.PLACEHOLDER)
            self.text_center("Loading preview...", rect, ui.DIM, ui.PLACEHOLDER)
            return
        self.DrawBitmap(bitmap, rect[0], rect[1], rect[2] - rect[0] + 1, rect[3] - rect[1] + 1,
                        0, 0, bitmap.GetBw(), bitmap.GetBh(), c4d.BMP_NORMALSCALED | c4d.BMP_ALLOWALPHA)
        self.draw_expand(rect, card)

    def draw_expand(self, rect, card):
        """Corner badge with four brackets: the preview opens the clip full size when the asset has one."""
        if not video_window.available_clips(card):
            return
        x2, y1 = rect[2] - 10, rect[1] + 10
        box = (x2 - 26, y1, x2, y1 + 26)
        self.fill(box, ui.OVERLAY)
        left, top, right, bottom = box[0] + 6, box[1] + 6, box[2] - 6, box[3] - 6
        for cx, cy, dx, dy in ((left, top, 1, 1), (right, top, -1, 1), (left, bottom, 1, -1), (right, bottom, -1, -1)):
            self.thick_line(cx, cy, cx + 4 * dx, cy, ui.TEXT)
            self.thick_line(cx, cy, cx, cy + 4 * dy, ui.TEXT)

    def draw_stats_box(self, rect, data):
        self.fill(rect, ui.CARD)
        self.frame(rect, ui.LINE)

    def draw_stat(self, rect, data):
        label, value = data
        self.text(label, rect[0], rect[1] + 8, ui.ACCENT, ui.CARD, c4d.FONT_BOLD)
        self.text(value, rect[0], rect[1] + 30, ui.TEXT, ui.CARD, c4d.FONT_BOLD, rect[2] - rect[0])

    def draw_heading(self, rect, text):
        self.text(text, rect[0], (rect[1] + rect[3]) // 2, ui.ACCENT, ui.BG, c4d.FONT_BOLD)

    def draw_para(self, rect, line):
        self.text(line, rect[0], (rect[1] + rect[3]) // 2, ui.MUTED, ui.BG, max_width=rect[2] - rect[0])

    def draw_kv(self, rect, data):
        label, value = data
        cy = (rect[1] + rect[3]) // 2
        self.text(label, rect[0], cy, ui.DIM, ui.BG)
        color = ui.ACCENT if label == "License" and not license_is_allowed(self.model.open_card()) else ui.TEXT
        self.text(value, rect[0] + 90, cy, color, ui.BG, max_width=rect[2] - rect[0] - 90, middle=label == "File")

    def draw_search_more(self, rect, name):
        """Outlined 'More' button: searches the whole catalog for the asset's name."""
        self.frame(rect, ui.LINE_STRONG)
        self.text("More", rect[0] + 12, (rect[1] + rect[3]) // 2, ui.TEXT, ui.BG)
        self.chevron(rect[2] - 12, (rect[1] + rect[3]) // 2, ui.RIGHT, ui.MUTED)

    def draw_similar(self, rect, other):
        """Tile picture (placeholder while it downloads) with the name below."""
        picture = (rect[0], rect[1], rect[2], rect[3] - SIMILAR_CAPTION_H)
        bitmap = self.model.tile(other)
        if bitmap is None:
            self.fill(picture, ui.PLACEHOLDER)
        else:
            results.draw_cover(self, bitmap, picture)
        caption_y = rect[3] - SIMILAR_CAPTION_H // 2 + 2
        self.text(other["title"] or self.stem(other), rect[0], caption_y, ui.MUTED, ui.BG, max_width=rect[2] - rect[0])

    def on_click(self, item, x, y, msg):
        """Navigation and shortcuts."""
        if item is None:
            return
        kind = item.kind
        if kind in ("close", "prev", "next", "copy"):
            self.act(kind + "_card" if kind != "copy" else "copy_name")
        elif kind == "preview":
            self.act("open_video_window")
        elif kind == "search_more":
            self.act("search_text", item.data)
        elif kind == "similar":
            self.act("open_similar", item.data)


class ActionBar(ui.Panel):
    """Dependencies and the accent Import / Download button; Re-Download below once the asset is on disk."""

    min_width = layout.DETAIL_W

    def __init__(self, act, model):
        super().__init__(act)
        self.model = model

    def build(self, width):
        """Two buttons side by side, and a full-width Re-Download row for assets that are already downloaded."""
        split = width * 2 // 5
        items = [layout.Item("deps", (16, 14, split - 6, 54), None),
                 layout.Item("download", (split + 2, 14, width - 16, 54), None)]
        if not self.is_downloaded():
            return items, ACTION_BAR_H
        items.append(layout.Item("redownload", (16, 62, width - 16, 100), None))
        return items, ACTION_BAR_TALL_H

    def is_downloaded(self):
        """True when the open card has a local copy."""
        card = self.model.open_card()
        return card is not None and self.model.download_state(card) is not None

    def paint(self, x1, y1, x2, y2):
        """Border and the buttons."""
        if self.model.open_card() is None:
            return
        self.fill((0, 0, self.GetWidth(), 0), ui.LINE)
        self.fill((0, 0, 0, self.content_height), ui.LINE)
        for item in self.items:
            getattr(self, "draw_" + item.kind)(item.rect, item.data)

    def draw_deps(self, rect, data):
        count = self.model.dependencies
        label = "Dependencies" + (" " + str(count) if count is not None else "")
        self.fill(rect, ui.BG)
        self.frame(rect, ui.LINE_STRONG)
        self.text_center(label, rect, ui.TEXT, ui.BG, c4d.FONT_BOLD)

    def draw_download(self, rect, data):
        card = self.model.open_card()
        busy = self.model.busy
        if busy:
            label = self.model.busy_text
        elif self.is_downloaded():
            label = "Import"
        else:
            label = "Download " + cat.format_bytes(card["bytes"], 1)
        fill = ui.PLACEHOLDER if busy else ui.ACCENT_FILL
        self.fill(rect, fill)
        self.text_center(label.strip(), rect, ui.DIM if busy else ui.ON_ACCENT, fill, c4d.FONT_BOLD)

    def draw_redownload(self, rect, data):
        """Outlined button; says so when a newer revision than the local one exists."""
        card = self.model.open_card()
        outdated = self.model.download_state(card) == library.OUTDATED
        label = "Re-Download  (newer version available)" if outdated else "Re-Download"
        busy = self.model.busy
        self.fill(rect, ui.BG)
        self.frame(rect, ui.LINE if busy else (ui.ACCENT if outdated else ui.LINE_STRONG))
        self.text_center(label, rect, ui.DIM if busy else ui.TEXT, ui.BG, c4d.FONT_BOLD)

    def on_click(self, item, x, y, msg):
        """Import / Download and Re-Download start jobs; Dependencies lists the package files in a menu."""
        if item is None:
            return
        if item.kind in ("download", "redownload"):
            self.act(item.kind)
            return
        entries = self.act("dependency_entries")
        if entries:
            self.popup(entries, item.rect[0], item.rect[3])
