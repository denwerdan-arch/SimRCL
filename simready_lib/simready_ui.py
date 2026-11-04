"""Drawing toolkit for the browser panels: colour tokens, vector icons, text fitting and the Panel base class.

Colours and sizes were sampled from the SimReady Central web UI. Icons are drawn from lines so that the
interface needs no image files and no emoji.
"""
import c4d
from c4d import gui

import simready_layout as layout


def rgb(red, green, blue):
    """Cinema 4D colour from 0..255 channels."""
    return c4d.Vector(red / 255.0, green / 255.0, blue / 255.0)


BG = rgb(0, 0, 0)
LINE = rgb(49, 49, 49)
LINE_STRONG = rgb(99, 99, 99)
CARD = rgb(22, 22, 22)
OVERLAY = rgb(12, 12, 12)
HOVER = rgb(28, 28, 28)
TEXT = rgb(255, 255, 255)
MUTED = rgb(167, 167, 167)
DIM = rgb(137, 137, 137)
ACCENT = rgb(255, 162, 0)
ACCENT_FILL = rgb(255, 149, 0)
ACCENT_DARK = rgb(36, 19, 3)
ON_ACCENT = rgb(0, 0, 0)
PLACEHOLDER = rgb(34, 34, 34)
MATCH_HIGH = rgb(118, 185, 0)  # match percentage badge: >= 80
MATCH_MID = rgb(230, 180, 0)  # 50..79
MATCH_LOW = rgb(230, 70, 55)  # below 50
BRAND_DIM = rgb(96, 96, 96)

BRAND_NAME, BRAND_BY = "SimRCL", "by Dead_wall"  # SimReady Central Library (was "SimRS" until 1.0.5)
VERSION = "1.2.0"
PRODUCT_NAME = BRAND_NAME + " " + BRAND_BY
AUTHOR_URL = "https://trycad.online/?lang=en"  # the brand in the header links here
DRAW_ERRORS = []  # last tracebacks of failed repaints, readable from a debugging console

LEFT, RIGHT, UP, DOWN = "left", "right", "up", "down"
ELLIPSIS = "…"


def fit_end(measure, text, max_width):
    """Cut text and append an ellipsis until measure(text) fits max_width."""
    if measure(text) <= max_width:
        return text
    while len(text) > 1 and measure(text + ELLIPSIS) > max_width:
        text = text[:-1]
    return text + ELLIPSIS


def fit_middle(measure, text, max_width):
    """Like fit_end but keeps the start and the end, so file names stay recognisable by their suffix."""
    if measure(text) <= max_width or len(text) < 6:
        return text
    head, tail = len(text) // 2, len(text) // 2
    while head + tail > 2:
        shown = text[:head] + ELLIPSIS + text[len(text) - tail:]
        if measure(shown) <= max_width:
            return shown
        head, tail = (head - 1, tail) if head > tail else (head, tail - 1)
    return text[:1] + ELLIPSIS


def report_error(error):
    """Keep the traceback in DRAW_ERRORS, print it, and tell the user in the status bar."""
    import traceback
    DRAW_ERRORS.append(traceback.format_exc())
    del DRAW_ERRORS[:-5]
    traceback.print_exc()
    gui.StatusSetText("%s error: %s" % (BRAND_NAME, error))


class Panel(gui.GeUserArea):
    """GeUserArea with a rebuildable item list, mouse conversion and the shared drawing helpers."""

    min_width = 100

    def __init__(self, act):
        super().__init__()
        self.act = act
        self.items = []
        self.content_height = 0
        self.built_width = -1

    # layout

    def build(self, width):
        """Return (items, content height) for the given width; subclasses implement it."""
        raise NotImplementedError

    def ensure_built(self):
        """Rebuild the item list when the width changed since the last build."""
        width = max(self.GetWidth(), self.min_width)
        if width != self.built_width:
            self.rebuild(width)

    def rebuild(self, width=None):
        """Recompute items and tell the scroll group about the new content height."""
        width = width or max(self.GetWidth(), self.min_width)
        self.items, height = self.build(width)
        self.built_width = width
        if height != self.content_height:
            self.content_height = height
            self.LayoutChanged()

    def refresh(self):
        """Rebuild and repaint after the model changed."""
        self.rebuild()
        self.Redraw()

    def GetMinSize(self):
        """Width as configured, height of the whole content so a scroll group can scroll it."""
        return self.min_width, max(self.content_height, 10)

    def Sized(self, w, h):
        """A new width can change the layout."""
        self.rebuild(max(w, self.min_width))

    # painting

    def DrawMsg(self, x1, y1, x2, y2, msg):
        """Paint the clipped region; a failure is printed instead of silently aborting the redraw."""
        self.OffScreenOn()
        self.ensure_built()
        self.fill((x1, y1, x2, y2), BG)
        try:
            self.paint(x1, y1, x2, y2)
        except Exception as error:  # noqa: BLE001 - a draw error must not leave a half-painted window
            report_error(error)

    def paint(self, x1, y1, x2, y2):
        """Draw the items intersecting the clip rectangle; subclasses implement it."""
        raise NotImplementedError

    def fill(self, rect, color):
        """Solid rectangle with inclusive corners."""
        self.DrawSetPen(color)
        self.DrawRectangle(rect[0], rect[1], rect[2], rect[3])

    def frame(self, rect, color):
        """One-pixel border."""
        x1, y1, x2, y2 = rect
        self.DrawSetPen(color)
        for ax, ay, bx, by in ((x1, y1, x2, y1), (x1, y2, x2, y2), (x1, y1, x1, y2), (x2, y1, x2, y2)):
            self.DrawLine(ax, ay, bx, by)

    def text_width(self, text, font=c4d.FONT_DEFAULT):
        """Width of text in pixels in the given font."""
        self.DrawSetFont(font)
        return self.DrawGetTextWidth(text)

    def text(self, text, x, cy, fg, bg, font=c4d.FONT_DEFAULT, max_width=None, middle=False):
        """Draw text with its vertical centre at cy; fg/bg must match the pixels underneath."""
        self.DrawSetFont(font)
        if max_width is not None:
            text = (fit_middle if middle else fit_end)(self.DrawGetTextWidth, text, max_width)
        self.DrawSetTextCol(fg, bg)
        self.DrawText(text, x, cy - self.DrawGetFontHeight() // 2)

    def text_right(self, text, right, cy, fg, bg, font=c4d.FONT_DEFAULT):
        """Draw text so that it ends at x = right."""
        self.DrawSetFont(font)
        self.text(text, right - self.DrawGetTextWidth(text), cy, fg, bg, font)

    def text_center(self, text, rect, fg, bg, font=c4d.FONT_DEFAULT):
        """Draw text centred in rect."""
        self.DrawSetFont(font)
        width = self.DrawGetTextWidth(text)
        self.text(text, (rect[0] + rect[2] - width) // 2, (rect[1] + rect[3]) // 2, fg, bg, font)

    def thick_line(self, ax, ay, bx, by, color):
        """Two-pixel line so that icons stay readable on dark backgrounds."""
        self.DrawSetPen(color)
        self.DrawLine(ax, ay, bx, by)
        self.DrawLine(ax + (ay == by), ay + (ax == bx), bx + (ay == by), by + (ax == bx))

    # icons

    def chevron(self, cx, cy, direction, color, size=3):
        """Small arrow head pointing in direction."""
        dx, dy = {LEFT: (-1, 0), RIGHT: (1, 0), UP: (0, -1), DOWN: (0, 1)}[direction]
        tip = (cx + dx * size, cy + dy * size)
        for sign in (-1, 1):
            back = (tip[0] - dx * size + sign * abs(dy) * size, tip[1] - dy * size + sign * abs(dx) * size)
            self.thick_line(tip[0], tip[1], back[0], back[1], color)

    def checkmark(self, rect, color):
        """Tick inside rect."""
        x1, y1, x2, y2 = rect
        mx, my = x1 + (x2 - x1) * 2 // 5, y2 - (y2 - y1) // 4
        self.thick_line(x1 + (x2 - x1) // 5, (y1 + y2) // 2, mx, my, color)
        self.thick_line(mx, my, x2 - (x2 - x1) // 5, y1 + (y2 - y1) // 4, color)

    def cross(self, cx, cy, color, size=4):
        """X mark."""
        self.thick_line(cx - size, cy - size, cx + size, cy + size, color)
        self.thick_line(cx - size, cy + size, cx + size, cy - size, color)

    def checkbox(self, rect, checked, on_dark=BG):
        """Square check box; filled with the accent colour when checked."""
        if checked:
            self.fill(rect, ACCENT)
            self.checkmark(rect, ON_ACCENT)
            return
        self.fill(rect, on_dark)
        self.frame(rect, LINE_STRONG)

    def pill(self, rect, label, fg, border, fill=None, font=c4d.FONT_BOLD):
        """Button-like label; corners stay square because Cinema 4D has no rounded rectangle primitive."""
        background = fill if fill is not None else BG
        self.fill(rect, background)
        self.frame(rect, border)
        self.text_center(label, rect, fg, background, font)

    # mouse

    def mouse_point(self, msg):
        """Click position in the coordinates of the whole (scrolled) area."""
        offset = self.Global2Local()
        return msg.GetInt32(c4d.BFM_INPUT_X) + offset["x"], msg.GetInt32(c4d.BFM_INPUT_Y) + offset["y"]

    def screen_point(self, x, y):
        """Screen position of the area point (x, y), for popup menus."""
        origin = self.Local2Screen()
        return origin["x"] + x, origin["y"] + y

    def popup(self, entries, x, y):
        """Show a menu; entries are (id, text) pairs, text may end with &c& (checked) or &d& (disabled). Returns the id or 0."""
        container = c4d.BaseContainer()
        for entry_id, label in entries:
            container.InsData(entry_id, label)
        sx, sy = self.screen_point(x, y)
        # cd must be a GeDialog or None (a user area raises TypeError); no EXECUTECOMMANDS: ids are ours, never commands
        return gui.ShowPopupDialog(cd=None, bc=container, x=sx, y=sy, flags=c4d.POPUP_RIGHT)

    # hover

    hovered = None  # (kind, data) of the item under the cursor, None outside

    def Message(self, msg, result):
        """Track the item under the cursor (for hover effects and tooltips) and notice when the cursor leaves."""
        msg_id = msg.GetId()
        if msg_id == c4d.BFM_GETCURSORINFO:
            self.cursor_info(msg, result)
            return True
        if msg_id == c4d.BFM_CURSORINFO_REMOVE:
            self.set_hover(None)
        return gui.GeUserArea.Message(self, msg, result)

    def cursor_info(self, msg, result):
        """Hover bookkeeping for a cursor position; answers with the item's tooltip when it has one."""
        try:
            origin = self.Local2Screen()
            x = msg.GetInt32(c4d.BFM_DRAG_SCREENX) - origin["x"]
            y = msg.GetInt32(c4d.BFM_DRAG_SCREENY) - origin["y"]
            item = layout.item_at(self.items, x, y)
            self.set_hover(item)
            tip = self.tooltip(item)
            if tip:
                result.SetId(c4d.BFM_GETCURSORINFO)
                result.SetString(c4d.RESULT_BUBBLEHELP, tip)
        except Exception as error:  # noqa: BLE001 - cursor messages arrive constantly; one failure must not repeat silently
            report_error(error)

    def set_hover(self, item):
        """Remember the hovered item and tell on_hover, only when it changed."""
        key = None if item is None else (item.kind, repr(item.data))
        if key != self.hovered:
            self.hovered = key
            self.on_hover(item)

    def on_hover(self, item):
        """Called when the cursor enters another item (None: empty space or outside); subclasses may react."""

    def tooltip(self, item):
        """Bubble help text for item, or None."""
        return None

    def InputEvent(self, msg):
        """Dispatch left clicks to on_click with the item under the cursor."""
        if msg.GetInt32(c4d.BFM_INPUT_DEVICE) != c4d.BFM_INPUT_MOUSE:
            return False
        if msg.GetInt32(c4d.BFM_INPUT_CHANNEL) != c4d.BFM_INPUT_MOUSELEFT:
            return False
        self.ensure_built()
        x, y = self.mouse_point(msg)
        try:
            self.on_click(layout.item_at(self.items, x, y), x, y, msg)
        except Exception as error:  # noqa: BLE001 - a click handler must not die silently: show it and keep the window alive
            report_error(error)
        return True

    def on_click(self, item, x, y, msg):
        """Handle a left click; item is None over empty space."""
        raise NotImplementedError


def shift_down(msg):
    """True when Shift was held during the mouse event."""
    return bool(msg.GetInt32(c4d.BFM_INPUT_QUALIFIER) & c4d.QSHIFT)


def double_click(msg):
    """True for the second click of a double click."""
    return bool(msg.GetInt32(c4d.BFM_INPUT_DOUBLECLICK))
