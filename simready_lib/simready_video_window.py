"""A separate window that plays an asset's clip at full size, on top of the browser.

Opened by clicking the large preview in the details. Shows the moving-parts clip and the 360 degree turn
(tabs when the asset has both), scaled to fit the window with black bars, looping. A click on the picture
pauses or continues. The clips download into the preview cache on first use, like the hover clips.
"""
import os
import queue

import c4d
from c4d import gui

import simready_layout as layout
import simready_media
import simready_tasks
import simready_ui as ui
import simready_video

TAB_H = 40
FRAME_MS = 40
DEFAULT_SIDE = 900  # the moving-parts clips are 960 px square; the turn is 640 px
SCREEN_SHARE = 0.8
AREA_ID = 1000
CLIP_LABELS = ((simready_media.JOINTS, "Moving parts"), (simready_media.SPIN, "360 turn"))


def available_clips(card):
    """[(label, url)] of the clips the asset really has, moving parts first."""
    media = card.get("media") or {}
    return [(label, simready_media.video_url(card, kind)) for kind, label in CLIP_LABELS if media.get(kind)]


def window_side():
    """Square window size that fits the screen the browser is on."""
    screen = gui.GeGetScreenDimensions(0, 0, True)
    height = (screen["sy2"] - screen["sy1"]) if screen else DEFAULT_SIDE
    return int(min(DEFAULT_SIDE, SCREEN_SHARE * height))


class VideoView(ui.Panel):
    """Tabs at the top (only with two clips), the clip below, a status text while it loads."""

    min_width = 320

    def __init__(self, window):
        super().__init__(window.act)
        self.window = window

    def build(self, width):
        clips = self.window.clips
        if len(clips) < 2:
            return [], 240
        tab_w = min(160, (width - 32) // len(clips))
        items = [layout.Item("tab", (16 + i * tab_w, 6, 16 + (i + 1) * tab_w - 4, TAB_H - 6), i) for i in range(len(clips))]
        return items, TAB_H + 240

    def video_rect(self):
        top = TAB_H if len(self.window.clips) > 1 else 0
        return 0, top, self.GetWidth(), self.GetHeight()

    def paint(self, x1, y1, x2, y2):
        for item in self.items:
            self.draw_tab(item.rect, item.data)
        rect = self.video_rect()
        player = self.window.player
        frame = player.frame() if player.playing else None
        if frame is None:
            self.text_center(self.window.status, rect, ui.DIM, ui.BG)
            return
        target = layout.contain_rect(frame.GetBw(), frame.GetBh(), rect)
        self.DrawBitmap(frame, target[0], target[1], target[2] - target[0], target[3] - target[1],
                        0, 0, frame.GetBw(), frame.GetBh(), c4d.BMP_NORMALSCALED)
        if player.paused:
            self.text("Paused - click to continue", rect[0] + 16, rect[3] - 18, ui.MUTED, ui.BG)

    def draw_tab(self, rect, index):
        active = index == self.window.current
        self.pill(rect, self.window.clips[index][0], ui.ON_ACCENT if active else ui.MUTED,
                  ui.ACCENT if active else ui.LINE, ui.ACCENT if active else None)

    def on_click(self, item, x, y, msg):
        """A tab switches the clip, a click on the picture pauses or continues."""
        if item is not None and item.kind == "tab":
            self.act("show_clip", item.data)
            return
        self.act("toggle_pause")


class VideoWindow(gui.GeDialog):
    """Asynchronous dialog with one VideoView; reused for every asset the user opens it for."""

    def __init__(self, cache_dir):
        super().__init__()
        self.cache_dir = cache_dir
        self.events = queue.Queue()
        self.player = simready_video.ClipPlayer()
        self.title, self.clips, self.current = "", [], 0
        self.status = ""
        self.view = VideoView(self)

    def act(self, name, *args):
        return getattr(self, "act_" + name)(*args)

    def show(self, card):
        """Open (or bring back) the window for card and start its first clip; False when it has no clip."""
        clips = available_clips(card)
        if not clips:
            return False
        self.title = card.get("title") or os.path.splitext(card["filename"])[0]
        self.clips, self.current = clips, 0
        if not self.IsOpen():
            side = window_side()
            self.Open(c4d.DLG_TYPE_ASYNC, 0, defaultw=side, defaulth=side + (TAB_H if len(clips) > 1 else 0))
        self.SetTitle("%s - %s" % (ui.PRODUCT_NAME, self.title))
        self.act_show_clip(0)
        return True

    def CreateLayout(self):
        self.SetTitle(ui.PRODUCT_NAME)
        self.AddUserArea(AREA_ID, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT)
        self.AttachUserArea(self.view, AREA_ID)
        return True

    def InitValues(self):
        self.SetDefaultColor(0, c4d.COLOR_BG, ui.BG)
        self.SetTimer(FRAME_MS)
        return True

    def act_show_clip(self, index):
        """Switch to clip index: play it from the cache, or download it first."""
        self.current = index
        self.player.close()
        url = self.clips[index][1]
        path = simready_media.image_path(url, self.cache_dir)
        if os.path.isfile(path):
            self.play(path)
        else:
            self.status = "Loading video..."
            simready_tasks.video_async(self.events, url, self.cache_dir)
        self.view.refresh()

    def act_toggle_pause(self):
        if self.player.playing:
            self.player.toggle_pause()
            self.view.Redraw()

    def play(self, path):
        self.status = "" if self.player.open(path) else "This video cannot be played here"

    def Timer(self, msg):
        """Take finished downloads (only the clip still shown is played) and advance the picture."""
        while True:
            try:
                kind, _, url, path = self.events.get_nowait()
            except queue.Empty:
                break
            if kind != "video" or not self.clips or url != self.clips[self.current][1]:
                continue
            if path:
                self.play(path)
            else:
                self.status = "Could not load the video"
        self.view.Redraw()

    def DestroyWindow(self):
        """Closing the window stops playback and releases the file."""
        self.SetTimer(0)
        self.player.close()
