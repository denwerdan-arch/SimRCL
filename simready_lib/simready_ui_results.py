"""Toolbar and results grid/list of asset cards."""
import c4d

import simready_catalog as cat
import simready_layout as layout
import simready_library
import simready_media
import simready_ui as ui

SIZE_ICONS = (("S", 6), ("M", 9), ("L", 12))
VIDEO_TIP = "Видео превью при наведении (медленно)"
EMPTY_HEIGHT = 280  # room for the empty-state message and its button
BMP_FLAGS = c4d.BMP_NORMALSCALED | c4d.BMP_ALLOWALPHA


def draw_cover(canvas, bitmap, rect):
    """Draw bitmap scaled to cover rect, cropping the longer side so the picture is never stretched."""
    rw, rh = rect[2] - rect[0] + 1, rect[3] - rect[1] + 1
    sx, sy, sw, sh = layout.cover_crop(bitmap.GetBw(), bitmap.GetBh(), rw, rh)
    canvas.DrawBitmap(bitmap, rect[0], rect[1], rw, rh, sx, sy, sw, sh, BMP_FLAGS)


def match_color(percent):
    """Badge colour of a match percentage."""
    return ui.MATCH_HIGH if percent >= 80 else ui.MATCH_MID if percent >= 50 else ui.MATCH_LOW


class ToolbarPanel(ui.Panel):
    """Sidebar toggle, result counter, view switches and the row of active filter chips."""

    min_width = 300
    CHIP_H, CHIP_ROW = 26, 34
    CHAR_W = 7  # average glyph width; text cannot be measured outside drawing, so chip boxes are estimated

    def __init__(self, act, model):
        super().__init__(act)
        self.model = model

    def build(self, width):
        """Controls on the first row, chips wrapped below it."""
        right, items = width - layout.GRID_PAD, [layout.Item("sidebar", (16, 8, 44, 38), None)]
        for key, _ in reversed(SIZE_ICONS):
            items.append(layout.Item("size", (right - 28, 8, right, 38), key))
            right -= 28
        items.append(layout.Item("video", (right - 34, 8, right - 6, 38), None))
        right -= 46
        for mode in ("list", "grid"):
            items.append(layout.Item("view", (right - 30, 8, right, 38), mode))
            right -= 30
        items.append(layout.Item("sort", (right - 230, 8, right - 12, 38), None))
        height = self.add_chips(items, width)
        return items, height

    def add_chips(self, items, width):
        """Chip items wrapped into rows; returns the toolbar height."""
        chips = self.model.chips()
        if not chips:
            return layout.TOOLBAR_H
        x, y = 16, layout.TOOLBAR_H - 4
        for label, field, key in chips + [("Clear all", "clear_all", None)]:
            chip_w = min(len(label) * self.CHAR_W + 38, width - 32)
            if x + chip_w > width - 16 and x > 16:
                x, y = 16, y + self.CHIP_ROW
            items.append(layout.Item("chip", (x, y, x + chip_w, y + self.CHIP_H), (label, field, key)))
            x += chip_w + 8
        return y + self.CHIP_H + 10

    def paint(self, x1, y1, x2, y2):
        """Draw the controls, chips and the bottom border."""
        for item in self.items:
            getattr(self, "draw_" + item.kind)(item.rect, item.data)
        self.draw_counter(self.model)
        self.fill((0, self.content_height - 1, self.GetWidth(), self.content_height - 1), ui.LINE)

    def draw_counter(self, model):
        """'58 of 3 599 results' with the numbers in the accent colour."""
        cy, x = layout.TOOLBAR_H // 2, 60
        if model.loading and not model.cards:
            self.text("Searching...", x, cy, ui.MUTED, ui.BG)
            return
        if model.sorting_all():
            note = "Loading %s of %s to sort them all..." % (cat.format_count(len(model.cards)), cat.format_count(model.total))
            self.text(note, x, cy, ui.ACCENT, ui.BG)
            return
        suffix = " results, loaded ones sorted" if model.sorting_loaded() else " results"
        for part, color in ((str(len(model.cards)), ui.ACCENT), (" of ", ui.MUTED),
                            (cat.format_count(model.total), ui.ACCENT), (suffix, ui.MUTED)):
            self.text(part, x, cy, color, ui.BG)
            x += self.text_width(part)

    def draw_sidebar(self, rect, data):
        """Panel icon: a frame with a bar on the left."""
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        color = ui.ACCENT if self.model.sidebar_visible else ui.MUTED
        self.frame((cx - 7, cy - 6, cx + 7, cy + 6), color)
        self.thick_line(cx - 3, cy - 5, cx - 3, cy + 5, color)

    def draw_view(self, rect, mode):
        """Grid or list switch; the active one is filled."""
        active = self.model.as_list == (mode == "list")
        self.fill(rect, ui.ACCENT if active else ui.BG)
        self.frame(rect, ui.ACCENT if active else ui.LINE)
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        color = ui.ON_ACCENT if active else ui.MUTED
        if mode == "list":
            for dy in (-4, 0, 4):
                self.fill((cx - 6, cy + dy, cx + 6, cy + dy + 1), color)
            return
        for dx in (-5, 1):
            for dy in (-5, 1):
                self.fill((cx + dx, cy + dy, cx + dx + 4, cy + dy + 4), color)

    def draw_size(self, rect, key):
        """Thumbnail size switch drawn as a square of growing size."""
        active = self.model.size_key == key
        self.fill(rect, ui.ACCENT if active else ui.BG)
        self.frame(rect, ui.ACCENT if active else ui.LINE)
        edge = dict(SIZE_ICONS)[key]
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        self.frame((cx - edge // 2, cy - edge // 2, cx + edge // 2, cy + edge // 2), ui.ON_ACCENT if active else ui.MUTED)

    def draw_video(self, rect, data):
        """Video-preview switch drawn as a clapperboard; filled while hover clips are on."""
        active = self.model.video_on
        self.fill(rect, ui.ACCENT if active else ui.BG)
        self.frame(rect, ui.ACCENT if active else ui.LINE)
        self.clapperboard((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2, ui.ON_ACCENT if active else ui.MUTED)

    def clapperboard(self, cx, cy, color):
        """Slate body, its hinged clapper tilted open, stripes on both."""
        self.frame((cx - 7, cy - 2, cx + 7, cy + 6), color)
        self.thick_line(cx - 7, cy - 3, cx + 6, cy - 7, color)  # the open clapper
        self.DrawSetPen(color)
        for x in (-4, 0, 4):
            self.DrawLine(cx + x, cy - 2, cx + x + 2, cy + 1)  # stripes on the body's top band
        self.DrawLine(cx - 7, cy + 1, cx + 7, cy + 1)

    def tooltip(self, item):
        """Bubble help for the controls without a text label."""
        return VIDEO_TIP if item is not None and item.kind == "video" else None

    def draw_sort(self, rect, data):
        """'Sort: Name' button with the direction arrow; accent colour while a sort is active."""
        model = self.model
        active = model.sort_key != "relevance"
        color = ui.ACCENT if active else ui.MUTED
        self.fill(rect, ui.ACCENT_DARK if active else ui.BG)
        self.frame(rect, ui.ACCENT_FILL if active else ui.LINE)
        cy = (rect[1] + rect[3]) // 2
        label = dict(cat.SORT_OPTIONS)[model.sort_key]
        self.text("Sort: " + label, rect[0] + 12, cy, color, ui.ACCENT_DARK if active else ui.BG, max_width=rect[2] - rect[0] - 52)
        arrow = ui.UP if active and not model.sort_desc else ui.DOWN
        self.chevron(rect[2] - 16, cy, arrow, color)

    def draw_chip(self, rect, data):
        """Removable filter label; 'Clear all' is plain accent text."""
        label, field, _ = data
        cy = (rect[1] + rect[3]) // 2
        if field == "clear_all":
            self.text_center(label, rect, ui.ACCENT, ui.BG, c4d.FONT_BOLD)
            return
        self.fill(rect, ui.ACCENT_DARK)
        self.frame(rect, ui.ACCENT_FILL)
        self.text(label, rect[0] + 10, cy, ui.ACCENT, ui.ACCENT_DARK, max_width=rect[2] - rect[0] - 36)
        self.cross(rect[2] - 14, cy, ui.ACCENT, 3)

    def on_click(self, item, x, y, msg):
        """Forward toolbar commands."""
        if item is None:
            return
        if item.kind == "chip":
            _, field, key = item.data
            self.act("clear_all" if field == "clear_all" else "remove_chip", *(() if field == "clear_all" else (field, key)))
            return
        if item.kind == "sort":
            self.open_sort_menu(item.rect)
            return
        self.act({"sidebar": "toggle_sidebar", "view": "set_view", "size": "set_size", "video": "toggle_video"}[item.kind],
                 *(() if item.data is None else (item.data,)))

    def open_sort_menu(self, rect):
        """Menu of sort keys and directions; the controller applies the choice."""
        choice = self.popup(self.act("sort_entries"), rect[0], rect[3])
        if choice:
            self.act("sort_choice", choice)


class ResultsPanel(ui.Panel):
    """The cards of the current search; reports clicks and asks for the next page near the end."""

    min_width = 300

    def __init__(self, act, model):
        super().__init__(act)
        self.model = model
        self.wanted = []  # cards painted without a picture since the last request

    def build(self, width):
        """One item per card plus the content height."""
        model = self.model
        rects = layout.result_rects(len(model.cards), width, model.size_key, model.as_list)
        items = [layout.Item("card", rect, index) for index, rect in enumerate(rects)]
        footer = 40 if model.has_more or model.loading else 0
        if not model.cards and not model.loading and model.chips():
            items.append(layout.Item("reset", ((width - 240) // 2, 190, (width + 240) // 2, 226), None))
        height = layout.results_height(width, len(model.cards), model.size_key, model.as_list, footer)
        return items, height if model.cards else max(height, EMPTY_HEIGHT)

    def paint(self, x1, y1, x2, y2):
        """Draw the visible cards, an empty-state message and the loading note."""
        model = self.model
        draw = self.draw_row if model.as_list else self.draw_card
        for item in self.items:
            if item.rect[3] < y1 or item.rect[1] > y2:
                continue
            if item.kind == "reset":
                self.pill(item.rect, "Clear filters and search", ui.ACCENT, ui.ACCENT_FILL)
            elif item.data < len(model.cards):  # items can be one rebuild behind the model while a search resets it
                draw(item.rect, item.data)
        self.draw_status(model)
        self.request_missing_tiles()
        if model.has_more and y2 > self.content_height - layout.END_MARGIN:
            self.act("need_more")

    def draw_status(self, model):
        """Centered message for empty results, a note while the next page loads."""
        width = self.GetWidth()
        if not model.cards and not model.loading:
            self.text_center(model.empty_text, (0, 110, width, 140), ui.TEXT, ui.BG, c4d.FONT_BOLD)
            hint = "Try other words, another search mode or fewer filters." if model.chips() else ""
            self.text_center(hint, (0, 144, width, 170), ui.MUTED, ui.BG)
        elif model.loading:
            self.text_center("Loading...", (0, self.content_height - 40, width, self.content_height - 10), ui.DIM, ui.BG)

    def request_missing_tiles(self):
        """Ask the controller for the tiles of the cards that were just painted without a picture."""
        if self.wanted:
            wanted, self.wanted = self.wanted, []
            self.act("request_tiles", wanted)

    def draw_image(self, card, rect):
        """Tile image (or the hover clip's current frame), a flat placeholder while the tile downloads."""
        frame = self.model.clip_frame("results", card)
        if frame is not None:
            draw_cover(self, frame, rect)
            return
        bitmap = self.model.tile(card)
        if bitmap is None:
            self.fill(rect, ui.PLACEHOLDER)
            self.wanted.append(card)
            return
        draw_cover(self, bitmap, rect)

    def draw_card(self, rect, index):
        """Grid card: picture with a caption strip at the bottom."""
        card, model = self.model.cards[index], self.model
        self.draw_image(card, rect)
        top = rect[3] - layout.OVERLAY_H + 1
        self.fill((rect[0], top, rect[2], rect[3]), ui.OVERLAY)
        room = rect[2] - rect[0] - 24
        self.text(card["title"] or card["filename"], rect[0] + 12, top + 15, ui.TEXT, ui.OVERLAY, c4d.FONT_BOLD, room)
        self.text(self.caption(card), rect[0] + 12, top + 34, ui.MUTED, ui.OVERLAY, c4d.FONT_MONOSPACED, room, middle=True)
        self.draw_badge(card, rect[0] + 8, rect[1] + 8)
        self.draw_match(card, rect[2] - 8, rect[1] + 8)
        if index == self.model.selected:
            self.frame(rect, ui.TEXT)
            self.frame((rect[0] + 1, rect[1] + 1, rect[2] - 1, rect[3] - 1), ui.TEXT)

    def draw_badge(self, card, x, y):
        """Accent square with a tick on assets that are already on disk (white frame when a newer revision exists)."""
        state = self.model.download_state(card)
        if state is None:
            return
        box = (x, y, x + 17, y + 17)
        self.fill(box, ui.ACCENT_FILL)
        self.checkmark(box, ui.ON_ACCENT)
        if state == simready_library.OUTDATED:
            self.frame((x - 1, y - 1, x + 18, y + 18), ui.TEXT)

    def draw_match(self, card, right, top, width=44):
        """'87%' badge ending at right: how well the preview matches the query, coloured green / amber / red."""
        match = card.get("match")
        if match is None:
            return
        color = match_color(match)
        box = (right - width, top, right, top + 18)
        self.fill(box, ui.OVERLAY)
        self.frame(box, color)
        self.text_center("%d%%" % match, box, color, ui.OVERLAY, c4d.FONT_MONOSPACED)

    def caption(self, card):
        """'filename . size' second line; the file name keeps both ends when it has to be shortened."""
        size = cat.format_bytes(card["bytes"])
        return "%s · %s" % (card["filename"], size) if size else card["filename"]

    def draw_row(self, rect, index):
        """List row: small picture, title and file name, size and licence on the right."""
        card = self.model.cards[index]
        self.fill(rect, ui.CARD)
        pic = (rect[0] + 8, rect[1] + 8, rect[0] + 8 + layout.LIST_THUMB - 1, rect[1] + 8 + layout.LIST_THUMB - 1)
        self.draw_image(card, pic)
        self.draw_badge(card, pic[0] + 4, pic[1] + 4)
        self.draw_match(card, rect[2] - 120, (rect[1] + rect[3]) // 2 - 9)
        cy, left = (rect[1] + rect[3]) // 2, pic[2] + 14
        room = rect[2] - left - 200
        self.text(card["title"] or card["filename"], left, cy - 10, ui.TEXT, ui.CARD, c4d.FONT_BOLD, room)
        self.text(card["filename"], left, cy + 10, ui.MUTED, ui.CARD, c4d.FONT_MONOSPACED, room, middle=True)
        self.text_right(cat.format_bytes(card["bytes"]), rect[2] - 16, cy - 10, ui.MUTED, ui.CARD)
        self.text_right(cat.format_dimensions(card["dims"]), rect[2] - 16, cy + 10, ui.DIM, ui.CARD)
        if index == self.model.selected:
            self.frame(rect, ui.TEXT)

    def on_hover(self, item):
        """Ask for the hovered card's 360 degree clip (the controller ignores it while video preview is off)."""
        index = item.data if item is not None and item.kind == "card" else None
        card = self.model.cards[index] if index is not None and index < len(self.model.cards) else None
        self.act("hover_clip", "results", card, simready_media.SPIN)

    def on_click(self, item, x, y, msg):
        """Open the clicked card, or reset filters from the empty-state button."""
        if item is None:
            return
        self.act("clear_all" if item.kind == "reset" else "select_card", *(() if item.kind == "reset" else (item.data,)))
