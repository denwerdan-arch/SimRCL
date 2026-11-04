"""SimReady Central browser for Cinema 4D: the dialog that wires the panels, the model and background tasks."""
import os
import pathlib
import queue
import tempfile
import time
import webbrowser

import c4d
from c4d import bitmaps, documents, gui

import simready_catalog as cat
import simready_client
import simready_dims as dims
import simready_import
import simready_layout as layout
import simready_library
import simready_media
import simready_render_target as render_target
import simready_settings as prefs
import simready_tasks
import simready_update
import simready_ui
import simready_ui_detail as detail
import simready_ui_header as header
import simready_ui_results as results
import simready_ui_sidebar as sidebar
import simready_video
import simready_video_window

CACHE_DIR = os.path.join(tempfile.gettempdir(), "simready_cache")
# Previews live outside Temp (Windows cleans it); packages go to the user's folder, see simready_settings.
DATA_DIR = os.path.join(os.path.expanduser("~"), "Documents", prefs.APP_NAME)
PREVIEW_DIR = os.path.join(DATA_DIR, "Previews")
PREVIEW_LIMIT_BYTES = 200 * 1024 * 1024  # oldest previews are pruned beyond this
BITMAP_LIMIT = 300  # decoded bitmaps kept in memory (about five screens of tiles)
GUIDE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "licensing.html")
DIALOG_PLUGIN_ID = 1073247  # registered plugin ID; keep equal to PLUGIN_ID in simready_browser.pyp
TIMER_MS = 100
FRAME_MS = 40  # timer while a clip plays: 25 redraws a second, the clips run at 24-30 fps
SEARCH_DEBOUNCE_SECONDS = 0.5
MEASURE_DELAY_SECONDS = 3  # batches the folder scans while many previews arrive
NOTICES_URL = simready_client.SERVICE_URL + "/third-party-notices.txt"
MODE_HINTS = {"Hybrid": "Search using natural language...", "Keyword": "Search by words in names and tags...",
              "Text": "Describe what the object looks like..."}
DEPENDENCY_MENU_LIMIT = 40
MENU_BASE = c4d.FIRST_POPUP_ID  # 1000..899999 are built-in Cinema 4D commands; only 900000+ is free for custom items
CHANGE_FOLDER, OPEN_FOLDER, RESET_FOLDER, TOGGLE_TIDY, INFO_ROW = (MENU_BASE + 1, MENU_BASE + 2, MENU_BASE + 3,
                                                                    MENU_BASE + 4, MENU_BASE + 10)
TOGGLE_OPENPBR = MENU_BASE + 5
TOGGLE_RIG = MENU_BASE + 6
TOGGLE_PHONG = MENU_BASE + 7
TOGGLE_SPLIT = MENU_BASE + 8
TOGGLE_LAYERS = MENU_BASE + 9
TOGGLE_ROUND = MENU_BASE + 15  # + 10 .. + 13 are the info rows
CHECK_UPDATES, TOGGLE_UPDATES, OPEN_UPDATE = MENU_BASE + 16, MENU_BASE + 17, MENU_BASE + 18
ROUND_LABEL = "Round corners controls (Redshift, Arnold, V-Ray)"
MODE_INFO_BASE = MENU_BASE + 50  # greyed description rows of the mode menu
TARGET_BASE = MENU_BASE + 20  # TARGET_BASE + index into TARGET_CHOICES
TARGET_CHOICES = (prefs.AUTO_TARGET,) + render_target.TARGETS
PATH_MENU_CHARS = 52
SORT_PAGE_SIZE = 400  # fewer, larger requests while loading everything for a sort
# A sort loads every result first; above this many (an empty query lists the whole catalog, 3 732) it sorts only
# what is loaded instead of downloading the catalog page by page.
SORT_ALL_LIMIT = 1000
ASCENDING, DESCENDING = MENU_BASE + 100, MENU_BASE + 101

(ID_QUERY, ID_BRAND, ID_MODE, ID_ACTIONS, ID_BODY, ID_SIDEBAR_GROUP, ID_SIDEBAR, ID_TOOLBAR, ID_RESULTS,
 ID_DETAIL_GROUP, ID_DETAIL, ID_ACTIONBAR, ID_ROOT, ID_HEADER) = range(1001, 1015)
CLIP_AREAS = {"results": ID_RESULTS, "detail": ID_DETAIL}  # panels that play hover clips
TITLE = simready_ui.PRODUCT_NAME
SEARCH_H = 30


def checked(flag):
    """Menu marker: Cinema 4D reads '&c&' only at the END of an item text and shows a check mark for it."""
    return "&c&" if flag else ""


def import_summary(group, counts, choice=None, warning=""):
    """Status text after an import: object counts, the material renderer and any warning (never replaced by it)."""
    before, after = counts
    removed = "" if before == after else " (%d objects, %d removed)" % (after, before - after)
    renderer = "" if choice is None else ", %s materials" % render_target.label(choice)
    return "Imported %s%s%s%s" % (group.GetName(), removed, renderer, ". " + warning if warning else "")


def target_label(target):
    """Menu text of a material target."""
    return "Auto (renderer of the scene)" if target == prefs.AUTO_TARGET else render_target.LABELS[target]


def load_bitmap(path):
    """Load an image file into a BaseBitmap, or return None when it cannot be read."""
    bitmap = bitmaps.BaseBitmap()
    return bitmap if bitmap.InitWith(path)[0] == c4d.IMAGERESULT_OK else None


class Model:
    """Everything the panels draw: catalog, filters, current page of cards and the open card."""

    def __init__(self, on_evict=None):
        self.catalog = None
        self.selection = cat.empty_selection()
        self.expanded, self.depth = set(), 3
        self.closed_sections, self.open_facets = set(), set()
        self.provider_kind = "all"
        self.loaded, self.cards, self.total, self.next_cursor = [], [], 0, None
        self.sort_key, self.sort_desc = "relevance", False
        self.loading, self.empty_text = False, "No results"
        self.selected = None
        self.detour = None  # a card opened from the Similar strip that is not in the results
        self.similar = {}  # card key -> [card] of the Similar strip
        self.size_key, self.as_list, self.sidebar_visible = "M", False, True
        self.query, self.mode, self.field_text = "", "Hybrid", ""
        self.only_downloaded, self.library = False, {}  # library: {(repo, package): {commit}} of the local packages
        self.bitmaps = simready_media.BitmapCache(BITMAP_LIMIT, on_evict)
        self.preview_bytes = None  # None until the cache folder has been measured
        self.dependencies, self.dependency_files = None, []
        self.busy, self.busy_text = False, ""
        self.video_on = False  # clips play on hover and in the open card (settings switch)
        self.match_requested = set()  # card keys sent for a match percentage in the current search
        self.clips = simready_video.ClipDeck(CLIP_AREAS)
        self.update = None  # release_info of a newer SimRCL, shown as a button next to the brand

    @property
    def has_more(self):
        """True while the service has another page for the current search."""
        return self.next_cursor is not None

    def custom_sort(self):
        """True for a sort that needs every result (not Relevance, not Match %)."""
        return self.sort_key not in ("relevance", "match")

    def sorting_all(self):
        """True while remaining pages are being fetched so that a sort covers every result.

        Match % sorts only what is loaded: every further page would have to be judged by the vision model
        (a Text search ranks the whole catalog), which is far too slow for a sort. Result sets larger than
        SORT_ALL_LIMIT are sorted as loaded too (see sorting_loaded).
        """
        return self.custom_sort() and self.has_more and self.total <= SORT_ALL_LIMIT

    def sorting_loaded(self):
        """True when a custom sort covers only the loaded cards because the result set is too large."""
        return self.custom_sort() and self.has_more and self.total > SORT_ALL_LIMIT

    def resort(self):
        """Rebuild the displayed order from the loaded cards, keeping the open card open."""
        open_card = self.listed_card()
        self.cards = cat.sort_cards(self.loaded, self.sort_key, self.sort_desc)
        if open_card is not None:
            self.selected = next((i for i, card in enumerate(self.cards) if card["key"] == open_card["key"]), None)

    def chips(self):
        """(label, field, key) of everything that narrows the results: the query and the active filters."""
        chips = cat.selection_chips(self.selection, self.catalog) if self.catalog else []
        own = ([("Downloaded", "downloaded", None)] if self.only_downloaded else []) + ([('"%s"' % self.query, "query", None)] if self.query else [])
        return own + chips

    def download_state(self, card):
        """None, simready_library.CURRENT or simready_library.OUTDATED for the local copy of a card."""
        return simready_library.state(card, self.library)

    def sidebar_state(self):
        """The part of the model the sidebar layout depends on."""
        return {"depth": self.depth, "expanded": self.expanded, "closed_sections": self.closed_sections,
                "open_facets": self.open_facets, "selection": self.selection, "provider_kind": self.provider_kind,
                "only_downloaded": self.only_downloaded, "library_count": len(self.library)}

    def listed_card(self):
        """The selected card of the results, or None."""
        if self.selected is None or self.selected >= len(self.cards):
            return None
        return self.cards[self.selected]

    def open_card(self):
        """The card shown in the detail panel: a card opened from Similar, else the selected result, else None."""
        return self.detour or self.listed_card()

    def neighbour(self, direction):
        """Index the previous (-1) or next (1) arrow opens, or None at the ends of the results.

        From a Similar card both arrows lead back to the result it was opened from.
        """
        if self.selected is None:
            return None
        target = self.selected + (0 if self.detour else direction)
        return target if 0 <= target < len(self.cards) else None

    def index_of(self, card):
        """Position of card in the displayed results, or None."""
        return next((i for i, other in enumerate(self.cards) if other["key"] == card["key"]), None)

    def tile(self, card):
        """Loaded tile bitmap of a card, or None."""
        return self.bitmaps.get(simready_media.media_url(card, simready_media.TILE))

    def poster(self, card):
        """Loaded poster bitmap of a card, or None."""
        return self.bitmaps.get(simready_media.media_url(card, simready_media.POSTER))

    def clip_frame(self, area, card):
        """Current frame of the clip playing for card in area ('results' or 'detail'), else None."""
        return self.clips.frame(area, card["key"])

    def similar_to(self, card):
        """[card] of the Similar strip of card; empty until the search came back."""
        return self.similar.get(card["key"], [])


class BrowserDialog(gui.GeDialog):
    """Browse, search, filter and import SimReady Central assets."""

    def __init__(self):
        super().__init__()
        self.events = queue.Queue()
        self.requested_images = set()
        self.model = Model(on_evict=self.requested_images.discard)  # an evicted tile must be requestable again
        self.token = 0
        self.search_due = None
        self.measure_due = None
        self.settings = prefs.load()
        self.model.video_on = prefs.video_enabled(self.settings)
        self.video_window = None  # created on first use, then reused
        self.panels = {
            ID_BRAND: header.BrandPanel(self.act, self.model), ID_MODE: header.ModePanel(self.act, self.model),
            ID_ACTIONS: header.ActionsPanel(self.act), ID_SIDEBAR: sidebar.SidebarPanel(self.act, self.model),
            ID_TOOLBAR: results.ToolbarPanel(self.act, self.model), ID_RESULTS: results.ResultsPanel(self.act, self.model),
            ID_DETAIL: detail.DetailPanel(self.act, self.model), ID_ACTIONBAR: detail.ActionBar(self.act, self.model),
        }

    # layout

    def CreateLayout(self):
        """Header row, then sidebar | results | details."""
        self.SetTitle(TITLE)
        self.GroupBegin(ID_ROOT, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)
        self.GroupSpace(0, 0)
        self.GroupBorderSpace(0, 0, 0, 0)
        self.add_header()
        self.add_body()
        self.GroupEnd()
        self.attach_panels()
        return True

    def add_header(self):
        """Brand, native search field, mode and actions."""
        self.GroupBegin(ID_HEADER, c4d.BFH_SCALEFIT, 4, 1)
        self.GroupSpace(0, 0)
        self.GroupBorderSpace(0, 0, 0, 0)
        self.AddUserArea(ID_BRAND, c4d.BFH_LEFT)
        self.AddEditText(ID_QUERY, c4d.BFH_SCALEFIT | c4d.BFV_CENTER, 0, SEARCH_H)
        self.AddUserArea(ID_MODE, c4d.BFH_FIT)
        self.AddUserArea(ID_ACTIONS, c4d.BFH_RIGHT)
        self.GroupEnd()

    def add_body(self):
        """Three columns; the outer ones can be hidden."""
        self.GroupBegin(ID_BODY, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 3, 1)
        self.GroupSpace(0, 0)
        self.GroupBegin(ID_SIDEBAR_GROUP, c4d.BFV_SCALEFIT, 1, 0)
        self.add_scrolled(ID_SIDEBAR, c4d.BFH_FIT | c4d.BFV_SCALEFIT, layout.SIDEBAR_W)
        self.GroupEnd()
        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)
        self.GroupSpace(0, 0)
        self.AddUserArea(ID_TOOLBAR, c4d.BFH_SCALEFIT)
        self.add_scrolled(ID_RESULTS, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 0)
        self.GroupEnd()
        self.GroupBegin(ID_DETAIL_GROUP, c4d.BFV_SCALEFIT, 1, 0)
        self.GroupSpace(0, 0)
        self.add_scrolled(ID_DETAIL, c4d.BFH_FIT | c4d.BFV_SCALEFIT, layout.DETAIL_W)
        self.AddUserArea(ID_ACTIONBAR, c4d.BFH_FIT)
        self.GroupEnd()
        self.GroupEnd()

    def add_scrolled(self, area_id, flags, width):
        """A vertically scrolling group that holds one user area."""
        self.ScrollGroupBegin(0, flags, c4d.SCROLLGROUP_VERT, width, 0)
        self.AddUserArea(area_id, (c4d.BFH_SCALEFIT if not width else c4d.BFH_FIT) | c4d.BFV_SCALEFIT)
        self.GroupEnd()

    def attach_panels(self):
        """Bind every Panel to its area id."""
        for area_id, panel in self.panels.items():
            self.AttachUserArea(panel, area_id)

    def InitValues(self):
        """Empty search box with a hint, details hidden, catalog loading."""
        self.apply_theme()
        self.set_field("")
        self.apply_mode_hint()
        self.HideElement(ID_DETAIL_GROUP, True)
        self.SetTimer(TIMER_MS)
        self.model.loading = True
        self.rescan_library()
        simready_tasks.catalog_async(self.events, CACHE_DIR)
        simready_tasks.previews_async(self.events, PREVIEW_DIR, PREVIEW_LIMIT_BYTES)
        if prefs.updates_enabled(self.settings):
            self.check_updates(force=False)
        self.refresh_all()
        return True

    def apply_theme(self):
        """Paint the dialog background and the native search field in the panel colours (grey would show through gaps)."""
        for group in (ID_ROOT, ID_HEADER, ID_BODY, ID_SIDEBAR_GROUP, ID_DETAIL_GROUP):
            self.SetDefaultColor(group, c4d.COLOR_BG, simready_ui.BG)
        field_colors = (("COLOR_BGEDIT", simready_ui.CARD), ("COLOR_BGFOCUS", simready_ui.CARD),
                        ("COLOR_TEXT_EDIT", simready_ui.TEXT), ("COLOR_TEXT_EDIT_HELP", simready_ui.DIM),
                        ("COLOR_BG", simready_ui.BG))
        for name, color in field_colors:
            self.SetDefaultColor(ID_QUERY, getattr(c4d, name), color)

    def DestroyWindow(self):
        """Stop polling and release an open clip when the window closes."""
        self.SetTimer(0)
        self.model.clips.stop()
        if self.video_window is not None and self.video_window.IsOpen():
            self.video_window.Close()

    # dispatch

    def act(self, name, *args):
        """Entry point of all panel callbacks; returns the handler's result (used by menus)."""
        return getattr(self, "act_" + name)(*args)

    def Command(self, cid, msg):
        """Typing is picked up by the timer; Command only makes it react sooner."""
        if cid == ID_QUERY:
            self.poll_field()
        return True

    def poll_field(self):
        """Notice a changed search text (whatever event the field fires) and schedule a search after a pause."""
        text = self.GetString(ID_QUERY)
        if text == self.model.field_text:
            return
        self.model.field_text = text
        self.search_due = time.monotonic() + SEARCH_DEBOUNCE_SECONDS
        self.refresh(ID_MODE)

    def Timer(self, msg):
        """Run the debounced search and drain worker events on the main thread."""
        self.poll_field()
        if self.search_due is not None and time.monotonic() >= self.search_due:
            self.search_due = None
            self.apply_query(self.model.field_text.strip())
        self.measure_previews_when_due()
        self.redraw_clips()
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                return
            self.handle_event(event)

    def measure_previews_when_due(self):
        """Re-measure the preview folder once new images have settled, so the button shows the real size."""
        if self.measure_due is None or time.monotonic() < self.measure_due:
            return
        self.measure_due = None
        simready_tasks.previews_async(self.events, PREVIEW_DIR, PREVIEW_LIMIT_BYTES)

    def apply_query(self, query):
        """Search again only when the trimmed text really changed."""
        if query != self.model.query:
            self.model.query = query
            self.new_search()

    def set_field(self, text):
        """Put text into the search box without waiting for the debounce."""
        self.SetString(ID_QUERY, text)
        self.model.field_text = text
        self.search_due = None
        self.refresh(ID_MODE)

    def apply_mode_hint(self):
        """Placeholder that explains the current search mode."""
        self.SetString(ID_QUERY, MODE_HINTS[self.model.mode], False, c4d.EDITTEXT_HELPTEXT)

    # refresh helpers

    def refresh_all(self):
        """Repaint every panel."""
        for panel in self.panels.values():
            panel.refresh()

    def refresh(self, *area_ids):
        """Repaint some panels."""
        for area_id in area_ids:
            self.panels[area_id].refresh()

    def show_group(self, group_id, visible):
        """Show or hide a column and re-flow the window."""
        self.HideElement(group_id, not visible)
        self.LayoutChanged(ID_BODY)

    def status(self, text):
        """Message in the Cinema 4D status bar."""
        gui.StatusSetText(text)

    # search

    def new_search(self):
        """Start from the first page with the current query, mode and filters."""
        model = self.model
        if model.catalog is None:
            return
        self.token += 1
        self.stop_clips()
        model.match_requested = set()
        model.loaded, model.cards, model.total, model.next_cursor = [], [], 0, None
        model.selected, model.detour, model.similar, model.loading = None, None, {}, True
        model.empty_text = "Nothing found"
        self.show_group(ID_DETAIL_GROUP, False)
        self.refresh(ID_TOOLBAR, ID_RESULTS, ID_SIDEBAR)
        if model.only_downloaded:
            simready_tasks.downloaded_async(self.events, self.token, model.catalog, model.query, model.mode,
                                            model.selection, model.library)
            return
        simready_tasks.search_async(self.events, self.token, model.catalog, model.query, model.mode, model.selection, None)

    def rescan_library(self):
        """Re-read which packages are on disk (two folder levels, cheap enough for the main thread)."""
        self.model.library = simready_library.index(simready_library.scan(self.download_dir))

    def act_toggle_downloaded(self):
        """Show only the assets that are already downloaded, still narrowed by category, filters and query."""
        self.model.only_downloaded = not self.model.only_downloaded
        self.rescan_library()
        self.new_search()

    def act_clear_query(self):
        """Empty the search box and search again at once."""
        self.set_field("")
        self.apply_query("")

    def act_clear_all(self):
        """Remove the query, every filter and the sort: back to the landing page as it opens."""
        self.model.only_downloaded = False
        self.model.sort_key, self.model.sort_desc = "relevance", False
        self.model.selection = cat.empty_selection()
        self.set_field("")
        self.model.query = ""
        self.new_search()

    def act_remove_chip(self, field, key):
        """Remove one active filter or the query."""
        model = self.model
        if field == "query":
            self.act_clear_query()
            return
        if field == "downloaded":
            self.act_toggle_downloaded()
            return
        if field == "dims":
            model.selection = cat.set_dimension(model.selection, key, dims.NO_LIMIT)
        elif field in ("rigid", "mass"):
            model.selection = cat.toggle_choice(model.selection, field, key)
        else:
            model.selection = cat.toggle_member(model.selection, field, key)
        self.new_search()

    def act_request_tiles(self, cards):
        """Fetch tiles of the cards on screen only; sorting may load thousands of cards nobody looks at."""
        self.request_images([simready_media.media_url(card, simready_media.TILE) for card in cards])

    def act_need_more(self):
        """Fetch the next page when the user scrolled close to the end."""
        model = self.model
        if model.loading or not model.has_more:
            return
        model.loading = True
        limit = SORT_PAGE_SIZE if model.sorting_all() else simready_client.PAGE_SIZE
        simready_tasks.search_async(self.events, self.token, model.catalog, model.query, model.mode,
                                    model.selection, model.next_cursor, limit)

    # sidebar actions

    def act_toggle_section(self, key):
        self.toggle(self.model.closed_sections, key)
        self.refresh(ID_SIDEBAR)

    def act_set_depth(self, depth):
        self.model.depth = depth
        self.refresh(ID_SIDEBAR)

    def act_toggle_expand(self, key):
        self.toggle(self.model.expanded, key)
        self.refresh(ID_SIDEBAR)

    def act_select_node(self, key, extend):
        model = self.model
        if extend:
            model.selection = cat.toggle_member(model.selection, "nodes", key)
        else:
            model.selection = dict(model.selection, nodes=() if model.selection["nodes"] == (key,) else (key,))
        self.new_search()

    def act_toggle_provider(self, key):
        """Add or remove a company from the filter."""
        self.model.selection = cat.toggle_member(self.model.selection, "nodes", key)
        self.new_search()

    def act_set_provider_kind(self, kind):
        """Show all companies, only OEMs or only ISVs; a view setting, the search is not repeated."""
        self.model.provider_kind = kind
        self.refresh(ID_SIDEBAR)

    def act_toggle_facet(self, facet):
        self.toggle(self.model.open_facets, facet)
        self.refresh(ID_SIDEBAR)

    def act_toggle_option(self, facet, key):
        model = self.model
        if facet in ("rigid", "mass"):
            model.selection = cat.toggle_choice(model.selection, facet, key)
        else:
            model.selection = cat.toggle_member(model.selection, facet, key)
        self.new_search()

    def act_edit_dimension(self, axis, side):
        """Type the minimum or maximum size along axis; empty or 0 removes that limit."""
        limits = self.model.selection["dims"][axis]
        current = limits[0] if side == "min" else limits[1]
        prompt = "%s size along %s, metres (empty = no %s)" % (
            "Minimum" if side == "min" else "Maximum", dims.AXES[axis].upper(), "minimum" if side == "min" else "maximum")
        answer = gui.InputDialog(prompt, dims.text(current))
        if answer is None:
            return
        try:
            value = dims.parse(answer)
        except ValueError:
            self.status("Not a size in metres: " + answer)
            return
        low, high = (value, limits[1]) if side == "min" else (limits[0], value)
        self.act_set_dimension_range(axis, dims.clamp(low, high, side))

    def act_set_dimension_range(self, axis, limits):
        """Apply a (min, max) size range along axis and search again."""
        self.model.selection = cat.set_dimension(self.model.selection, axis, limits)
        self.new_search()

    def act_reset_dimensions(self):
        """Remove the size limits of all three axes."""
        self.model.selection = cat.clear_dimensions(self.model.selection)
        self.new_search()

    @staticmethod
    def toggle(values, member):
        """Add member to the set or remove it."""
        values.symmetric_difference_update({member})

    # toolbar and cards

    def act_sort_entries(self):
        """Menu: one entry per sort key (checked when active), then the direction."""
        model = self.model
        options = cat.available_sort_options(model.loaded)
        entries = [(MENU_BASE + i, label + checked(key == model.sort_key)) for i, (key, label) in enumerate(options)]
        return entries + [(0, ""), (ASCENDING, "Ascending" + checked(not model.sort_desc)),
                          (DESCENDING, "Descending" + checked(model.sort_desc))]

    def act_sort_choice(self, choice):
        """Apply a sort key or direction; a real sort first loads all remaining pages."""
        model = self.model
        if choice == ASCENDING or choice == DESCENDING:
            model.sort_desc = choice == DESCENDING
        else:
            model.sort_key = cat.available_sort_options(model.loaded)[choice - MENU_BASE][0]
        model.resort()
        self.refresh(ID_TOOLBAR, ID_RESULTS, ID_DETAIL)
        if model.sorting_all():
            self.act_need_more()

    def act_toggle_sidebar(self):
        self.model.sidebar_visible = not self.model.sidebar_visible
        self.show_group(ID_SIDEBAR_GROUP, self.model.sidebar_visible)
        self.refresh(ID_TOOLBAR)

    def act_set_view(self, mode):
        self.model.as_list = mode == "list"
        self.refresh(ID_TOOLBAR, ID_RESULTS)

    def act_toggle_video(self):
        """Switch the clips on or off and remember it; the open card starts or stops its clip right away."""
        enabled = not self.model.video_on
        self.model.video_on = enabled
        if enabled:
            self.play_open_card_clip()
        else:
            self.stop_clips()
        updated = prefs.with_video(self.settings, enabled)
        self.save_settings(updated, "Video preview: " + ("on" if enabled else "off"))
        self.refresh(ID_TOOLBAR)

    def act_open_video_window(self):
        """Show the open card's clip at full size in its own window on top of the browser."""
        card = self.model.open_card()
        if card is None:
            return
        if self.video_window is None:
            self.video_window = simready_video_window.VideoWindow(PREVIEW_DIR)
        if not self.video_window.show(card):
            self.status("No video for this asset")

    def act_hover_clip(self, area, card, kind):
        """The cursor entered card in area (card None: it left); play that card's clip of kind when switched on."""
        self.play_clip(area, card, kind)

    def play_open_card_clip(self):
        """The open card plays its moving parts (or its turn) in the large preview while video preview is on."""
        self.play_clip("detail", self.model.open_card(), simready_media.JOINTS)

    def play_clip(self, area, card, kind):
        """Point area at card's clip of kind; download it first when it is not cached yet."""
        deck = self.model.clips
        url = simready_media.video_url(card, kind) if card is not None and self.model.video_on else None
        if url is None:
            self.stop_clips(area)
            return
        if not deck.aim(area, card["key"], kind, url):
            return
        self.redraw_area(area)  # back to the still while the new clip loads
        path = simready_media.image_path(url, PREVIEW_DIR)
        if os.path.isfile(path):
            self.clip_ready(url, path)
            return
        self.status("Loading video preview...")
        simready_tasks.video_async(self.events, url, PREVIEW_DIR)

    def clip_ready(self, url, path):
        """A clip is on disk: start it where it is still wanted and run the timer at the frame rate."""
        started, failed = self.model.clips.start(url, path)
        if failed:
            self.status("This video preview cannot be played here")
        elif started:
            self.status("")
        self.update_clip_timer()

    def stop_clips(self, area=None):
        """Stop one area's clip (or all) and show the still pictures again."""
        for stopped in self.model.clips.stop(area):
            self.redraw_area(stopped)
        self.update_clip_timer()

    def update_clip_timer(self):
        """Fast timer only while something plays: it also drains the worker queue, which needs no hurry."""
        self.SetTimer(FRAME_MS if self.model.clips.playing() else TIMER_MS)

    def redraw_area(self, area):
        self.panels[CLIP_AREAS[area]].Redraw()

    def on_video(self, url, path):
        """A clip finished downloading."""
        if path:
            self.clip_ready(url, path)

    def redraw_clips(self):
        """Repaint the panels that show a running clip (called by the timer)."""
        for area in self.model.clips.playing():
            self.redraw_area(area)

    def act_set_size(self, key):
        self.model.size_key = key
        self.refresh(ID_TOOLBAR, ID_RESULTS)

    def act_select_card(self, index):
        """Open the details of card index of the results."""
        self.model.selected, self.model.detour = index, None
        self.open_details(self.model.cards[index])

    def act_open_similar(self, card):
        """Open a card of the Similar strip: as the result it is when it is listed, otherwise on its own."""
        index = self.model.index_of(card)
        if index is not None:
            self.act_select_card(index)
            return
        self.model.detour = card
        self.open_details(card)

    def open_details(self, card):
        """Show the detail panel of card and request what it needs: poster, file list, full record, similar assets."""
        model = self.model
        model.dependencies, model.dependency_files = None, []
        self.request_images([simready_media.media_url(card, simready_media.POSTER)])
        simready_tasks.dependencies_async(self.events, self.token, card)
        if not card["detailed"]:
            simready_tasks.details_async(self.events, self.token, card, model.catalog)
        if card["key"] not in model.similar:
            simready_tasks.similar_async(self.events, self.token, card, model.catalog)
        self.show_group(ID_DETAIL_GROUP, True)
        self.refresh(ID_RESULTS, ID_DETAIL, ID_ACTIONBAR)
        self.play_open_card_clip()

    def act_search_text(self, text):
        """Put text into the search box and search right away (the 'More' button of the details)."""
        if not text:
            return
        self.set_field(text)
        self.apply_query(text)

    def act_close_card(self):
        self.stop_clips("detail")
        self.model.selected, self.model.detour = None, None
        self.show_group(ID_DETAIL_GROUP, False)
        self.refresh(ID_RESULTS)

    def act_prev_card(self):
        self.go_to(self.model.neighbour(-1))

    def act_next_card(self):
        self.go_to(self.model.neighbour(1))

    def go_to(self, index):
        if index is not None:
            self.act_select_card(index)

    def act_copy_name(self):
        card = self.model.open_card()
        copy = getattr(c4d, "CopyStringToClipboard", None)
        if card and copy:
            copy(os.path.splitext(card["filename"])[0])
            self.status("Copied " + card["filename"])

    # header menus

    @property
    def download_dir(self):
        """Folder that receives downloaded packages."""
        return prefs.download_dir(self.settings)

    def act_open_downloads(self):
        """Open the folder that holds downloaded packages in the file manager."""
        folder = self.download_dir
        if prefs.check_folder(folder):
            self.status("Download folder is not available: " + folder)
            return
        c4d.storage.ShowInFinder(folder, False)

    def act_open_author(self):
        """Open the author's site (the brand in the header is its link)."""
        webbrowser.open(simready_ui.AUTHOR_URL)

    def act_open_update(self):
        """Release page of the newer version (the button next to the brand)."""
        webbrowser.open(self.model.update["url"] if self.model.update else simready_update.RELEASES_PAGE)

    def check_updates(self, force):
        """Ask for a newer release in the background; a forced check ignores the once-a-day rule."""
        simready_tasks.update_async(self.events, simready_ui.VERSION, prefs.update_state(self.settings), time.time(), force)

    def on_update(self, newer, state, error, forced):
        """Remember the answer, show or hide the Update button and, after a manual check, say how it went."""
        if state != prefs.update_state(self.settings):
            prefs.save(dict(self.settings, **{prefs.UPDATE_STATE_KEY: state}))  # a failed save only means asking again
            self.settings = dict(self.settings, **{prefs.UPDATE_STATE_KEY: state})
        self.model.update = newer
        brand = self.panels[ID_BRAND]
        if brand.min_width != brand.wanted_width():
            brand.min_width = brand.wanted_width()
            self.LayoutChanged(ID_HEADER)
        brand.refresh()
        if newer:
            self.status("%s %s is available: click Update in the header" % (simready_ui.BRAND_NAME, newer["version"]))
        elif forced:
            self.status("Could not check for updates: " + error if error else
                        "%s %s is up to date" % (simready_ui.BRAND_NAME, simready_ui.VERSION))

    def act_open_notices(self):
        webbrowser.open(NOTICES_URL)

    def act_open_guide(self):
        """Licensing guide (English / Russian) in the default browser."""
        webbrowser.open(pathlib.Path(GUIDE_PATH).as_uri())  # as_uri escapes spaces and non-ASCII user names

    def act_clear_previews(self):
        """Delete cached preview images; the worker reports back, then the visible ones are fetched again."""
        self.status("Clearing previews...")
        self.stop_clips()  # an open clip would keep its file from being deleted
        simready_tasks.cancel_pending_images()  # otherwise queued downloads would refill the folder right after it is emptied
        simready_tasks.previews_async(self.events, PREVIEW_DIR, PREVIEW_LIMIT_BYTES, clear=True)

    def act_menu_entries(self, name):
        """Items of a header menu; ids start at MENU_BASE so 0 means 'dismissed'."""
        return self.settings_entries() if name == "settings" else self.mode_entries()

    def act_menu_choice(self, name, choice):
        """Apply the item picked in a header menu."""
        if name == "settings":
            self.apply_settings_choice(choice)
        else:
            self.apply_mode_choice(choice)

    def mode_entries(self):
        """Each mode with its one-line description as a greyed row below it."""
        entries = []
        for index, mode in enumerate(simready_client.TEXT_MODES):
            entries.append((MENU_BASE + index, mode + checked(mode == self.model.mode)))
            entries.append((MODE_INFO_BASE + index, "    " + simready_client.MODE_DESCRIPTIONS[mode] + "&d&"))
        return entries

    def apply_mode_choice(self, choice):
        if not MENU_BASE <= choice < MENU_BASE + len(simready_client.TEXT_MODES):
            return
        self.model.mode = simready_client.TEXT_MODES[choice - MENU_BASE]
        self.apply_mode_hint()
        self.refresh(ID_MODE)
        self.new_search()

    def settings_entries(self):
        """Settings menu: where packages go, how much room is left there, and the actions."""
        folder = self.download_dir
        free = prefs.free_bytes(folder)
        shown = folder if len(folder) <= PATH_MENU_CHARS else "..." + folder[-(PATH_MENU_CHARS - 3):]
        return [(INFO_ROW + 3, "%s v%s&d&" % (simready_ui.PRODUCT_NAME, simready_ui.VERSION))] + self.update_entries() + [
                (0, ""),
                (INFO_ROW, "Download folder: %s&d&" % shown),
                (INFO_ROW + 1, "Free space on that drive: %s&d&" % (cat.format_bytes(free, 1) or "unknown")),
                (0, ""),
                (CHANGE_FOLDER, "Change download folder..."),
                (OPEN_FOLDER, "Open download folder"),
                (RESET_FOLDER, "Use default folder" + ("&d&" if prefs.is_default(self.settings) else "")),
                (0, ""),
                (TOGGLE_TIDY, "Tidy hierarchy on import" + checked(prefs.tidy_enabled(self.settings))),
                self.rig_entry(),
                (TOGGLE_PHONG, "Area Weighted Phong normals" + checked(prefs.phong_enabled(self.settings))),
                (TOGGLE_SPLIT, "Split one-mesh models by material" + checked(prefs.split_enabled(self.settings))),
                (TOGGLE_LAYERS, "Layer per imported asset" + checked(prefs.layers_enabled(self.settings))),
                (TOGGLE_ROUND, ROUND_LABEL + checked(prefs.round_enabled(self.settings))),
                (0, ""),
                (INFO_ROW + 2, "Materials for:&d&")] + self.target_entries() + [
                (TOGGLE_OPENPBR, "Prefer OpenPBR (Redshift, Arnold, V-Ray)" + checked(prefs.prefer_openpbr(self.settings)))]

    def update_entries(self):
        """Update items under the version row: the newer release when known, a manual check, the switch."""
        newer = self.model.update
        entries = [(OPEN_UPDATE, "Download %s %s..." % (simready_ui.BRAND_NAME, newer["version"]))] if newer else []
        return entries + [(CHECK_UPDATES, "Check for updates now"),
                          (TOGGLE_UPDATES, "Check for updates on start" + checked(prefs.updates_enabled(self.settings)))]

    def rig_entry(self):
        """Menu item of the rig switch; greyed out without the tidy-up, which resolves the joints it needs."""
        tidy = prefs.tidy_enabled(self.settings)
        label = "Controls for moving parts" + checked(tidy and prefs.rig_enabled(self.settings))
        return TOGGLE_RIG, label + ("" if tidy else "&d&")

    def target_entries(self):
        """One check item per material target; the current one is marked."""
        current = prefs.material_target(self.settings, render_target.TARGETS)
        return [(TARGET_BASE + index, "  " + target_label(target) + checked(target == current))
                for index, target in enumerate(TARGET_CHOICES)]

    def apply_settings_choice(self, choice):
        """Run the settings action for a menu id."""
        actions = {CHANGE_FOLDER: self.choose_download_dir, OPEN_FOLDER: self.act_open_downloads,
                   RESET_FOLDER: lambda: self.set_download_dir(prefs.DEFAULT_DOWNLOAD_DIR),
                   TOGGLE_TIDY: self.toggle_tidy, TOGGLE_OPENPBR: self.toggle_openpbr, TOGGLE_RIG: self.toggle_rig,
                   TOGGLE_PHONG: lambda: self.toggle_flag(prefs.PHONG_KEY, prefs.phong_enabled, "Area Weighted Phong normals"),
                   TOGGLE_SPLIT: lambda: self.toggle_flag(prefs.SPLIT_KEY, prefs.split_enabled, "Split one-mesh models by material"),
                   TOGGLE_LAYERS: lambda: self.toggle_flag(prefs.LAYERS_KEY, prefs.layers_enabled, "Layer per imported asset"),
                   TOGGLE_ROUND: lambda: self.toggle_flag(prefs.ROUND_KEY, prefs.round_enabled, ROUND_LABEL),
                   CHECK_UPDATES: self.check_updates_now, OPEN_UPDATE: self.act_open_update,
                   TOGGLE_UPDATES: lambda: self.toggle_flag(prefs.UPDATES_KEY, prefs.updates_enabled, "Check for updates on start")}
        if TARGET_BASE <= choice < TARGET_BASE + len(TARGET_CHOICES):
            self.set_material_target(TARGET_CHOICES[choice - TARGET_BASE])
            return
        action = actions.get(choice)
        if action:
            action()

    def check_updates_now(self):
        """Settings > Check for updates now."""
        self.status("Checking for updates...")
        self.check_updates(force=True)

    def save_settings(self, updated, message):
        """Persist updated settings and show message; keep the old settings when the file cannot be written."""
        error = prefs.save(updated)
        if error:
            self.status("Could not save settings: " + error)
            return
        self.settings = updated
        self.status(message)

    def toggle_tidy(self):
        """Flip the tidy-on-import switch and persist it; affects the next import only."""
        updated = prefs.with_tidy(self.settings, not prefs.tidy_enabled(self.settings))
        self.save_settings(updated, "Tidy hierarchy on import: " + ("on" if prefs.tidy_enabled(updated) else "off"))

    def toggle_flag(self, key, read, label):
        """Flip an on/off import option and persist it; affects the next import only."""
        updated = prefs.with_flag(self.settings, key, not read(self.settings))
        self.save_settings(updated, "%s: %s" % (label, "on" if read(updated) else "off"))

    def toggle_rig(self):
        """Flip the controls-for-moving-parts switch and persist it; affects the next import only."""
        updated = prefs.with_rig(self.settings, not prefs.rig_enabled(self.settings))
        self.save_settings(updated, "Controls for moving parts: " + ("on" if prefs.rig_enabled(updated) else "off"))

    def toggle_openpbr(self):
        """Flip the OpenPBR preference and persist it; affects the next import only."""
        updated = prefs.with_openpbr(self.settings, not prefs.prefer_openpbr(self.settings))
        self.save_settings(updated, "Prefer OpenPBR: " + ("on" if prefs.prefer_openpbr(updated) else "off"))

    def set_material_target(self, target):
        """Choose the renderer the next imports build materials for."""
        self.save_settings(prefs.with_material_target(self.settings, target), "Materials for: " + target_label(target))

    def material_choice(self):
        """The renderer choice for the next import (target setting, OpenPBR preference, installed renderers)."""
        setting = prefs.material_target(self.settings, render_target.TARGETS)
        return render_target.resolve(setting, prefs.prefer_openpbr(self.settings), documents.GetActiveDocument())

    def choose_download_dir(self):
        """Ask for a folder with the native dialog and switch to it."""
        picked = c4d.storage.LoadDialog(c4d.FILESELECTTYPE_ANYTHING, "Choose the folder for downloaded assets",
                                        c4d.FILESELECT_DIRECTORY, "", self.download_dir)
        if picked:
            self.set_download_dir(picked)

    def set_download_dir(self, path):
        """Validate and store the download folder. Packages already downloaded stay where they are:
        imported scenes reference their textures by path, so moving them would break those scenes."""
        error = prefs.check_folder(path)
        if error:
            self.status(error)
            gui.MessageDialog(error)
            return
        updated = prefs.with_download_dir(self.settings, path)
        error = prefs.save(updated)
        if error:
            self.status("Could not save settings: " + error)
            return
        self.settings = updated
        self.rescan_library()
        self.status("Download folder: " + self.download_dir)
        self.refresh(ID_SIDEBAR, ID_RESULTS, ID_DETAIL, ID_ACTIONBAR)
        if self.model.only_downloaded:
            self.new_search()

    # download and import

    def act_download(self):
        """Import the open asset; a package that is already on disk is not downloaded again."""
        card = self.model.open_card()
        if card is None or self.model.busy:
            return
        self.set_busy(True, "Preparing...")
        simready_tasks.install_async(self.events, self.token, card["asset"], self.download_dir, simready_import.inspect_safely)

    def act_redownload(self):
        """Fetch every file of the open asset again (also the newest revision) without touching the scene."""
        card = self.model.open_card()
        if card is None or self.model.busy:
            return
        self.set_busy(True, "Preparing...")
        simready_tasks.install_async(self.events, self.token, card["asset"], self.download_dir,
                                     simready_import.inspect_safely, force=True, then_import=False)

    def set_busy(self, busy, text=""):
        self.model.busy, self.model.busy_text = busy, text
        self.refresh(ID_ACTIONBAR)

    def act_dependency_entries(self):
        """Menu listing the files of the package (an informational list, entries do nothing)."""
        files = self.model.dependency_files
        if not files:
            return [(MENU_BASE, "Loading file list...&d&")]
        entries = [(MENU_BASE + i, "%s   %s&d&" % (name, cat.format_bytes(size))) for i, (name, size) in enumerate(files[:DEPENDENCY_MENU_LIMIT])]
        if len(files) > DEPENDENCY_MENU_LIMIT:
            entries.append((MENU_BASE + DEPENDENCY_MENU_LIMIT, "... and %d more&d&" % (len(files) - DEPENDENCY_MENU_LIMIT)))
        return entries

    # worker events

    def handle_event(self, event):
        """Dispatch one worker event; pages of a superseded search are ignored."""
        kind, token = event[0], event[1]
        if kind in ("page", "deps", "details", "similar", "match") and token != self.token:
            return
        getattr(self, "on_" + kind)(*event[2:])

    def on_catalog(self, catalog):
        """Catalog ready: build the sidebar and run the default search."""
        self.model.catalog = catalog
        self.refresh(ID_SIDEBAR)
        self.new_search()

    def on_page(self, cards, total, next_cursor, appended):
        """Add a page of cards and fetch their tiles."""
        model = self.model
        known = {card["key"] for card in model.loaded} if appended else set()
        cards = [card for card in cards if card["key"] not in known]  # featured assets can reappear in later pages
        model.loaded = model.loaded + cards if appended else cards
        model.resort()
        model.total, model.next_cursor, model.loading = total, next_cursor, False
        model.empty_text = "" if model.cards else self.empty_message()
        self.refresh(ID_TOOLBAR, ID_RESULTS, ID_DETAIL)
        self.request_matches(cards)
        if model.sorting_all():
            self.act_need_more()  # a sort only makes sense over everything, so keep fetching

    def request_matches(self, cards):
        """Ask how well the new cards match the typed query (no query, nothing to judge)."""
        model = self.model
        keys = [card["key"] for card in cards if card["key"] not in model.match_requested]
        if not model.query or not keys:
            return
        model.match_requested.update(keys)
        simready_tasks.match_async(self.events, self.token, model.query, keys)

    def on_match(self, query, scores):
        """Store a batch of match percentages on the cards; a Match % sort is redone with them."""
        model = self.model
        if query != model.query:
            return
        for card in model.loaded + ([model.detour] if model.detour else []):
            if card["key"] in scores:
                card["match"] = scores[card["key"]]
        if model.sort_key == "match":
            model.resort()
        self.refresh(ID_TOOLBAR, ID_RESULTS, ID_DETAIL)

    def empty_message(self):
        """What to say when a search came back empty."""
        model = self.model
        if model.only_downloaded and not model.library:
            return "Nothing is downloaded yet"
        if model.only_downloaded:
            return "No downloaded assets match"
        return 'Nothing found for "%s"' % model.query if model.query else "No assets match these filters"

    def request_images(self, urls):
        """Download images that are neither loaded nor requested."""
        fresh = [url for url in urls if url not in self.requested_images]
        self.requested_images.update(fresh)
        if fresh:
            simready_tasks.images_async(self.events, fresh, PREVIEW_DIR)

    def on_image(self, url, path):
        """Decode a downloaded image on the main thread (BaseBitmap is not thread safe) and repaint."""
        bitmap = load_bitmap(path) if path else None
        if bitmap is None:
            return
        self.model.bitmaps.put(url, bitmap)
        if self.measure_due is None:
            self.measure_due = time.monotonic() + MEASURE_DELAY_SECONDS
        self.refresh_images()

    def refresh_images(self):
        """Repaint the picture panels; throttled by redraw coalescing in Cinema 4D."""
        self.panels[ID_RESULTS].Redraw()
        self.panels[ID_DETAIL].Redraw()

    def on_details(self, full):
        """Swap in the complete record of a card whose licence and other properties were missing."""
        model = self.model
        previous = next((card for card in model.loaded if card["key"] == full["key"]), model.detour or {})
        if previous.get("match") is not None:
            full["match"] = previous["match"]  # the full record comes from a plain search and has no percentage
        model.loaded = [full if card["key"] == full["key"] else card for card in model.loaded]
        if model.detour is not None and model.detour["key"] == full["key"]:
            model.detour = full
        model.resort()
        self.refresh(ID_RESULTS, ID_DETAIL, ID_ACTIONBAR)

    def on_previews(self, cleared, size):
        """Cache folder measured (or emptied): update the button and, after a clear, drop the pictures held in memory."""
        self.model.preview_bytes = size
        if cleared:
            self.model.bitmaps.clear()
            self.requested_images.clear()
            self.status("Previews cleared")
            self.refresh(ID_RESULTS, ID_DETAIL)  # visible cards ask for their pictures again
        self.refresh(ID_SIDEBAR)

    def on_similar(self, key, cards):
        """Keep the Similar strip of a card and fetch its tiles."""
        self.model.similar[key] = cards
        self.request_images([simready_media.media_url(card, simready_media.TILE) for card in cards])
        self.refresh(ID_DETAIL)

    def on_deps(self, key, files):
        """Remember the package file list of the open card."""
        card = self.model.open_card()
        if card is None or card["key"] != key:
            return
        self.model.dependency_files = files
        self.model.dependencies = len(files)
        self.refresh(ID_ACTIONBAR)

    def on_progress(self, done, total):
        self.set_busy(True, "Downloading %d/%d" % (done, total))
        gui.StatusSetBar(100.0 * done / total)

    def on_inspecting(self, asset_path):
        gui.StatusClear()
        self.set_busy(True, "Reading materials...")

    def on_installed(self, asset_path, usd_path, inspected):
        """Import the downloaded package into the active document (main thread only)."""
        choice = self.material_choice()
        group, warning, counts = simready_import.import_asset(
            documents.GetActiveDocument(), usd_path, inspected, tidy=prefs.tidy_enabled(self.settings), choice=choice,
            rig=prefs.rig_enabled(self.settings), phong=prefs.phong_enabled(self.settings),
            split=prefs.split_enabled(self.settings), layers=prefs.layers_enabled(self.settings),
            round_corners=prefs.round_enabled(self.settings))
        c4d.EventAdd()
        self.finish_install()
        self.status(import_summary(group, counts, choice, warning) if group else warning or "Could not load " + usd_path)

    def on_refreshed(self, asset_path, usd_path):
        """A forced download finished; the scene is untouched, the user imports when ready."""
        self.finish_install()
        self.status("Updated %s. Press Import to add it to the scene." % os.path.basename(usd_path))

    def finish_install(self):
        """Unlock the buttons and show the new local state (badges, filter count, Import/Re-Download)."""
        gui.StatusClear()
        self.rescan_library()
        self.set_busy(False)
        self.refresh(ID_SIDEBAR, ID_RESULTS, ID_DETAIL)

    def on_error(self, message):
        """Report a failure and unlock the UI."""
        gui.StatusClear()
        self.model.loading = False
        self.set_busy(False)
        self.status("Error: " + message)
        self.refresh(ID_TOOLBAR, ID_RESULTS)


_DIALOG = None


def show():
    """Open the browser window, reusing one instance; an async dialog dies when its last reference is dropped."""
    global _DIALOG
    if _DIALOG is None:
        _DIALOG = BrowserDialog()
    return _DIALOG.Open(c4d.DLG_TYPE_ASYNC, DIALOG_PLUGIN_ID, defaultw=1280, defaulth=800)
