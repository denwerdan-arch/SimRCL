"""Header strips around the native search field: brand, search mode and the action buttons."""
import c4d

import simready_client
import simready_layout as layout
import simready_ui as ui


class StripPanel(ui.Panel):
    """Fixed-height header piece; subclasses supply the items and how each kind is drawn."""

    def build(self, width):
        """Items for the strip and its fixed height."""
        return self.strip_items(width), layout.HEADER_H

    def paint(self, x1, y1, x2, y2):
        """Draw every item and the bottom border."""
        for item in self.items:
            getattr(self, "draw_" + item.kind)(item.rect, item.data)
        self.fill((0, layout.HEADER_H - 1, self.GetWidth(), layout.HEADER_H - 1), ui.LINE)

    def open_menu(self, name, rect):
        """Show the controller's menu below rect and report the choice back."""
        entries = self.act("menu_entries", name)
        if not entries:
            return
        choice = self.popup(entries, rect[0], rect[3])
        if choice:
            self.act("menu_choice", name, choice)


class BrandPanel(StripPanel):
    """Product name at the left edge, a link to the author's site; an "Update x.y.z" button when one is out."""

    BASE_WIDTH = 190
    UPDATE_WIDTH = 104  # room for the update button right of the name
    LINK_LEFT = 32

    def __init__(self, act, model):
        super().__init__(act)
        self.model = model
        self.min_width = self.BASE_WIDTH

    def wanted_width(self):
        """Width the strip needs: wider while an update is announced."""
        return self.BASE_WIDTH + (self.UPDATE_WIDTH if self.model.update else 0)

    def strip_items(self, width):
        # only the label is the link, so a click on the empty strip next to it does nothing
        items = [layout.Item("brand", (0, 0, min(width, self.BASE_WIDTH), layout.HEADER_H), None)]
        if self.model.update:
            top = layout.HEADER_H // 2 - 12
            items.append(layout.Item("update", (self.BASE_WIDTH - 4, top, self.BASE_WIDTH + self.UPDATE_WIDTH - 12, top + 24),
                                     self.model.update))
        return items

    def draw_brand(self, rect, data):
        cy = layout.HEADER_H // 2
        self.fill((18, cy - 11, 22, cy + 11), ui.ACCENT)
        name_width = self.text_width(ui.BRAND_NAME, c4d.FONT_BOLD)
        self.text(ui.BRAND_NAME, self.LINK_LEFT, cy, ui.TEXT, ui.BG, c4d.FONT_BOLD)
        self.text(" " + ui.BRAND_BY, self.LINK_LEFT + name_width, cy, ui.BRAND_DIM, ui.BG, c4d.FONT_BOLD)
        if self.hovered and self.hovered[0] == "brand":  # hovered is (kind, repr(data))
            right = self.LINK_LEFT + name_width + self.text_width(" " + ui.BRAND_BY, c4d.FONT_BOLD)
            self.fill((self.LINK_LEFT, cy + 9, right, cy + 9), ui.ACCENT)

    def draw_update(self, rect, data):
        hovered = bool(self.hovered) and self.hovered[0] == "update"
        self.pill(rect, "Update " + data["version"], ui.ON_ACCENT if hovered else ui.ACCENT, ui.ACCENT,
                  ui.ACCENT if hovered else None)

    def on_hover(self, item):
        self.Redraw()

    def tooltip(self, item):
        if item is None:
            return None
        if item.kind == "update":
            return "SimRCL %s is out: open the release page (install it with INSTALL.bat)" % item.data["version"]
        return ui.AUTHOR_URL

    def on_click(self, item, x, y, msg):
        if item is not None:
            self.act("open_update" if item.kind == "update" else "open_author")


class ModePanel(StripPanel):
    """Clear button (while a query is typed), magnifier and the search mode that opens a menu."""

    min_width = 150

    def __init__(self, act, model):
        super().__init__(act)
        self.model = model

    def strip_items(self, width):
        return [layout.Item("clear", (0, 14, 30, 44), None), layout.Item("mode", (32, 14, width - 4, 44), None)]

    def draw_clear(self, rect, data):
        if self.model.field_text:
            self.cross((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2, ui.MUTED, 4)

    def draw_mode(self, rect, data):
        cy = (rect[1] + rect[3]) // 2
        self.frame((rect[0] + 6, cy - 6, rect[0] + 12, cy), ui.MUTED)
        self.thick_line(rect[0] + 12, cy, rect[0] + 16, cy + 4, ui.MUTED)
        self.text(self.model.mode, rect[0] + 26, cy, ui.ACCENT, ui.BG, c4d.FONT_BOLD)
        self.chevron(rect[2] - 14, cy, ui.DOWN, ui.ACCENT)

    def tooltip(self, item):
        """The current mode's description on the mode button."""
        return simready_client.MODE_DESCRIPTIONS.get(self.model.mode) if item is not None and item.kind == "mode" else None

    def on_click(self, item, x, y, msg):
        if item is None:
            return
        if item.kind == "clear":
            self.act("clear_query")
        else:
            self.open_menu("mode", item.rect)


class ActionsPanel(StripPanel):
    """Downloads button (opens the download folder) and the settings button next to it."""

    min_width = 190
    ICON_W = 32

    def strip_items(self, width):
        split = width - 16 - self.ICON_W
        return [layout.Item("downloads", (16, 15, split - 6, 43), None),
                layout.Item("settings", (split, 15, width - 16, 43), None)]

    def draw_downloads(self, rect, data):
        self.pill(rect, "Downloads", ui.TEXT, ui.LINE_STRONG)

    def draw_settings(self, rect, data):
        """Three sliders drawn from lines; stands for 'settings' without an icon font or emoji."""
        self.fill(rect, ui.BG)
        self.frame(rect, ui.LINE_STRONG)
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        for row, knob in ((-6, -4), (0, 3), (6, -1)):
            self.thick_line(cx - 7, cy + row, cx + 7, cy + row, ui.MUTED)
            self.fill((cx + knob - 2, cy + row - 3, cx + knob + 2, cy + row + 3), ui.ACCENT)

    def on_click(self, item, x, y, msg):
        if item is None:
            return
        if item.kind == "downloads":
            self.act("open_downloads")
            return
        self.open_menu("settings", item.rect)
