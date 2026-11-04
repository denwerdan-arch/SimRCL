"""Left panel: category hierarchy with counts, SimReady facets and filters."""
import c4d

import simready_catalog as cat
import simready_dims as dims
import simready_layout as layout
import simready_ui as ui

DEPTH_RANGE = (1, 6)
CHEVRON_X = layout.PAD + 8


def depth_buttons(rect):
    """Hit rectangles of the minus and plus buttons of the depth row."""
    cy = (rect[1] + rect[3]) // 2
    minus = (layout.PAD + 70, cy - 10, layout.PAD + 90, cy + 10)
    plus = (layout.PAD + 120, cy - 10, layout.PAD + 140, cy + 10)
    return minus, plus


class SidebarPanel(ui.Panel):
    """Hierarchy / SimReady / Filters; every state change goes through the act callback."""

    min_width = layout.SIDEBAR_W

    def __init__(self, act, model):
        super().__init__(act)
        self.model = model
        self.dim_preview = None  # (axis, (min, max)) while a dimension thumb is dragged

    def build(self, width):
        """Rows for the current model state."""
        return layout.sidebar_items(self.model.sidebar_state(), self.model.catalog, width)

    def paint(self, x1, y1, x2, y2):
        """Draw rows in the clip region, the right border and the footer."""
        for item in self.items:
            if item.rect[3] >= y1 and item.rect[1] <= y2:
                getattr(self, "draw_" + item.kind)(item.rect, item.data)
        if self.model.catalog is None:
            self.text("Loading catalog...", layout.PAD, 130, ui.DIM, ui.BG)
        self.fill((self.GetWidth() - 1, y1, self.GetWidth() - 1, y2), ui.LINE)

    def draw_footer(self, rect, data):
        """Cache button, help links and the product line below the last row."""
        rows = layout.footer_rows(rect)
        size = self.model.preview_bytes
        label = "Clear previews" + ("" if size is None else "   " + cat.format_bytes(size))
        self.pill(rows["clear"], label, ui.TEXT, ui.LINE_STRONG)
        self.text("Licensing guide", rows["guide"][0], (rows["guide"][1] + rows["guide"][3]) // 2, ui.MUTED, ui.BG)
        self.text("Third-party notices", rows["notices"][0], (rows["notices"][1] + rows["notices"][3]) // 2, ui.MUTED, ui.BG)
        self.text(ui.PRODUCT_NAME + " for Cinema 4D", rows["brand"][0], rows["brand"][1], ui.DIM, ui.BG, max_width=rows["brand"][2] - rows["brand"][0])

    def draw_library(self, rect, data):
        """'Downloaded' switch with the number of local packages: shows only what is already on disk."""
        active, count = data
        cy = (rect[1] + rect[3]) // 2
        self.checkbox((layout.PAD + 4, cy - 7, layout.PAD + 18, cy + 7), active)
        self.text("Downloaded", layout.PAD + 28, cy, ui.ACCENT if active else ui.TEXT, ui.BG, c4d.FONT_BOLD)
        self.text_right(cat.format_count(count), rect[2] - layout.PAD, cy, ui.DIM, ui.BG)

    def draw_section(self, rect, data):
        """Section title with a collapse arrow."""
        key, title = data
        cy = (rect[1] + rect[3]) // 2
        self.fill((0, rect[1] - 1, rect[2], rect[1] - 1), ui.LINE)
        self.text(title, layout.PAD, cy, ui.TEXT, ui.BG, c4d.FONT_BOLD)
        closed = key in self.model.closed_sections
        self.chevron(rect[2] - layout.PAD, cy, ui.DOWN if closed else ui.UP, ui.MUTED)

    def draw_provider_kind(self, rect, data):
        """All / OEMs / ISVs / DSX switch of the provider list."""
        kinds, current = data
        for kind, button in layout.provider_buttons(rect, kinds):
            active = kind == current
            self.fill(button, ui.CARD if active else ui.BG)
            self.frame(button, ui.ACCENT if active else ui.LINE)
            self.text_center(layout.PROVIDER_KIND_LABELS[kind], button, ui.TEXT if active else ui.MUTED, ui.CARD if active else ui.BG,
                             c4d.FONT_BOLD if active else c4d.FONT_DEFAULT)

    def draw_provider_group(self, rect, data):
        """Small heading of a group of companies (OEMs, ISVs, DSX) with its number of assets."""
        heading, count = data
        cy = (rect[1] + rect[3]) // 2
        self.text(heading.upper(), layout.PAD, cy, ui.DIM, ui.BG, c4d.FONT_BOLD)
        self.text_right(cat.format_count(count), rect[2] - layout.PAD, cy, ui.DIM, ui.BG)

    def draw_provider(self, rect, data):
        """Check box row of a company: name, group tag (OEM, ISV, DSX) and the number of assets."""
        provider, checked = data
        cy = (rect[1] + rect[3]) // 2
        self.checkbox((layout.PAD + 4, cy - 7, layout.PAD + 18, cy + 7), checked)
        count = cat.format_count(provider.count)
        tag = cat.provider_tag(provider)
        right = rect[2] - layout.PAD
        count_left = right - self.text_width(count)
        tag_left = count_left - 12 - self.text_width(tag)
        self.text(provider.name, layout.PAD + 28, cy, ui.TEXT if checked else ui.MUTED, ui.BG, max_width=tag_left - layout.PAD - 36)
        self.text(tag, tag_left, cy, ui.DIM, ui.BG)
        self.text_right(count, right, cy, ui.DIM, ui.BG)

    def draw_depth(self, rect, depth):
        """'Depth - n +' row."""
        cy = (rect[1] + rect[3]) // 2
        minus, plus = depth_buttons(rect)
        self.text("Depth", layout.PAD, cy, ui.DIM, ui.BG)
        self.text_center("-", minus, ui.MUTED, ui.BG)
        self.text_center(str(depth), (minus[2], minus[1], plus[0], minus[3]), ui.TEXT, ui.BG)
        self.text_center("+", plus, ui.MUTED, ui.BG)

    def draw_tree(self, rect, data):
        """One category row: arrow, name, number of assets."""
        node, level, expandable, is_open, active = data
        cy = (rect[1] + rect[3]) // 2
        left = layout.PAD + (level - 1) * layout.INDENT
        if expandable:
            self.chevron(left + 5, cy, ui.DOWN if is_open else ui.RIGHT, ui.MUTED, 3)
        color = ui.ACCENT if active else ui.TEXT
        count = cat.format_count(node.count)
        room = rect[2] - layout.PAD - self.text_width(count) - left - 32
        self.text(node.label, left + 20, cy, color, ui.BG, max_width=room)
        self.text_right(count, rect[2] - layout.PAD, cy, ui.DIM, ui.BG)

    def draw_facet(self, rect, data):
        """Collapsible facet header; a dot marks an active selection inside it, an optional summary sits right."""
        _, title, is_open, active = data[:4]
        cy = (rect[1] + rect[3]) // 2
        self.text(title, layout.PAD, cy, ui.TEXT, ui.BG, c4d.FONT_BOLD)
        if len(data) > 4 and data[4]:
            self.text_right(data[4], rect[2] - layout.PAD - 22, cy, ui.MUTED, ui.BG)
        if active:
            self.fill((layout.PAD + self.text_width(title, c4d.FONT_BOLD) + 8, cy - 2, layout.PAD + self.text_width(title, c4d.FONT_BOLD) + 12, cy + 2), ui.ACCENT)
        self.chevron(rect[2] - layout.PAD, cy, ui.UP if is_open else ui.DOWN, ui.MUTED)

    def draw_option(self, rect, data):
        """Check box row of a facet value with its count."""
        _, option, checked = data
        cy = (rect[1] + rect[3]) // 2
        self.checkbox((layout.PAD + 4, cy - 7, layout.PAD + 18, cy + 7), checked)
        count = cat.format_count(option.count)
        room = rect[2] - 2 * layout.PAD - self.text_width(count) - 40
        self.text(option.label, layout.PAD + 28, cy, ui.TEXT if checked else ui.MUTED, ui.BG, max_width=room)
        self.text_right(count, rect[2] - layout.PAD, cy, ui.DIM, ui.BG)

    def draw_dim(self, rect, data):
        """Axis row as on the site: label, min field, two-thumb slider (cubic scale to 100 m), max field."""
        axis, limits = data
        if self.dim_preview is not None and self.dim_preview[0] == axis:
            limits = self.dim_preview[1]  # live values while a thumb is dragged
        cy = (rect[1] + rect[3]) // 2
        parts = layout.dim_parts(rect)
        self.text(dims.AXES[axis].upper(), parts["label"][0], cy, ui.MUTED, ui.BG, c4d.FONT_BOLD)
        self.draw_dim_field(parts["min"], cy, limits[0], "min")
        self.draw_dim_field(parts["max"], cy, limits[1], "max")
        self.draw_dim_track(parts["track"], cy, limits)

    def draw_dim_field(self, span, cy, value, placeholder):
        box = (span[0], cy - 11, span[1], cy + 11)
        self.fill(box, ui.CARD)
        self.frame(box, ui.ACCENT if value else ui.LINE)
        label = dims.text(value) or placeholder
        self.text(label, box[0] + 6, cy, ui.TEXT if value else ui.DIM, ui.CARD, max_width=box[2] - box[0] - 8)

    def draw_dim_track(self, track, cy, limits):
        low, high = (dims.x_at(step, track) for step in dims.thumb_steps(limits))
        self.fill((track[0], cy - 1, track[1], cy), ui.LINE)
        self.fill((low, cy - 1, high, cy), ui.ACCENT if dims.active((limits,)) else ui.LINE_STRONG)
        for x, value in ((low, limits[0]), (high, limits[1])):
            thumb = (x - 5, cy - 5, x + 5, cy + 5)  # square: user areas have no circle primitive in this UI kit
            self.fill(thumb, ui.ACCENT if value else ui.BG)
            self.frame(thumb, ui.ACCENT if value else ui.LINE_STRONG)

    def draw_dims_reset(self, rect, data):
        """'Reset' link under the axis rows while any limit is set."""
        self.text_right("Reset", rect[2] - layout.PAD, (rect[1] + rect[3]) // 2, ui.ACCENT, ui.BG)

    def on_click(self, item, x, y, msg):
        """Translate a click on a row into a controller action."""
        if item is None:
            return
        if item.kind == "footer":
            self.click_footer(item, x, y)  # several targets in one item: needs the vertical position too
            return
        handler = getattr(self, "click_" + item.kind, None)
        if handler:
            handler(item, x, msg)

    def click_provider(self, item, x, msg):
        self.act("toggle_provider", item.data[0].key)

    def click_provider_kind(self, item, x, msg):
        """The switch is one row: the segment under the pointer is found by x."""
        kinds, _ = item.data
        for kind, button in layout.provider_buttons(item.rect, kinds):
            if button[0] <= x <= button[2]:
                self.act("set_provider_kind", kind)
                return

    def click_library(self, item, x, msg):
        self.act("toggle_downloaded")

    def click_section(self, item, x, msg):
        self.act("toggle_section", item.data[0])

    def click_depth(self, item, x, msg):
        """Minus and plus act on the x position only: the whole row is one item, so its height is irrelevant."""
        minus, plus = depth_buttons(item.rect)
        if minus[0] <= x <= minus[2]:
            self.act("set_depth", max(DEPTH_RANGE[0], item.data - 1))
        elif plus[0] <= x <= plus[2]:
            self.act("set_depth", min(DEPTH_RANGE[1], item.data + 1))

    def click_tree(self, item, x, msg):
        node, level, expandable, _, _ = item.data
        arrow_right = layout.PAD + (level - 1) * layout.INDENT + 18
        if expandable and x < arrow_right:
            self.act("toggle_expand", node.key)
        else:
            self.act("select_node", node.key, ui.shift_down(msg))

    def click_footer(self, item, x, y):
        """Route a click inside the footer to the row under the pointer."""
        for name, action in (("clear", "clear_previews"), ("guide", "open_guide"), ("notices", "open_notices")):
            if layout.rect_contains(layout.footer_rows(item.rect)[name], x, y):
                self.act(action)
                return

    def click_facet(self, item, x, msg):
        self.act("toggle_facet", item.data[0])

    def click_option(self, item, x, msg):
        self.act("toggle_option", item.data[0], item.data[1].key)

    def click_dim(self, item, x, msg):
        """Min / max field: type a value; slider: drag the nearer thumb."""
        axis, limits = item.data
        parts = layout.dim_parts(item.rect)
        part = dims.part_at(x, parts)
        if part in ("min", "max"):
            self.act("edit_dimension", axis, part)
        elif part == "track":
            self.drag_dimension(axis, limits, parts["track"], x)

    def drag_dimension(self, axis, limits, track, x):
        """Follow the mouse until release; the search runs once, with the final range (Esc cancels)."""
        thumb = dims.nearer_thumb(dims.step_at(x, track), limits)
        current = dims.drag(limits, thumb, dims.step_at(x, track))
        self.preview_dimension(axis, current)
        self.MouseDragStart(c4d.KEY_MLEFT, x, 0, c4d.MOUSEDRAGFLAGS_DONTHIDEMOUSE | c4d.MOUSEDRAGFLAGS_NOMOVE)
        while True:
            result, dx, _, _ = self.MouseDrag()
            if result != c4d.MOUSEDRAGRESULT_CONTINUE:
                break
            x += dx
            current = dims.drag(limits, thumb, dims.step_at(x, track))
            self.preview_dimension(axis, current)
        self.MouseDragEnd()
        self.preview_dimension(None, None)
        if result != c4d.MOUSEDRAGRESULT_ESCAPE and current != limits:
            self.act("set_dimension_range", axis, current)

    def preview_dimension(self, axis, limits):
        self.dim_preview = None if axis is None else (axis, limits)
        self.Redraw()

    def click_dims_reset(self, item, x, msg):
        self.act("reset_dimensions")

