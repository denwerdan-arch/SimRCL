"""Play a cached MP4 clip frame by frame for a user area (Cinema 4D's MovieLoader decodes H.264).

Frames are picked by wall clock, so playback keeps its speed when the redraws are slow, and it loops.
Measured: a 72-frame 640 px turn opens and decodes 24 frames in about 0.15 s, so each redraw decodes at most
one frame on the main thread.
"""
import time

import c4d
from c4d import bitmaps

FALLBACK_FPS = 24.0


class ClipPlayer:
    """One open clip; frame() returns the bitmap to show now, or None when nothing plays."""

    def __init__(self):
        self.loader = None
        self.path = None
        self.count, self.fps = 0, FALLBACK_FPS
        self.started = 0.0
        self.paused_at = None
        self.index, self.bitmap = -1, None

    @property
    def playing(self):
        return self.loader is not None

    def open(self, path):
        """Start playing path from its first frame; returns False (and plays nothing) when it cannot be read."""
        self.close()
        loader = bitmaps.MovieLoader()
        if loader.Open(path) != c4d.IMAGERESULT_OK:
            return False
        count, fps = loader.GetInfo()
        if count < 1:
            loader.Close()
            return False
        self.loader, self.path = loader, path
        self.count, self.fps = count, fps or FALLBACK_FPS
        self.started, self.index, self.bitmap, self.paused_at = time.monotonic(), -1, None, None
        return True

    def close(self):
        """Stop and release the file (Windows keeps an open file from being pruned)."""
        if self.loader is not None:
            self.loader.Close()
        self.loader, self.path, self.index, self.bitmap = None, None, -1, None

    @property
    def paused(self):
        return self.paused_at is not None

    def toggle_pause(self, now=None):
        """Freeze on the current frame, or continue from it."""
        now = time.monotonic() if now is None else now
        if self.paused_at is None:
            self.paused_at = now
        else:
            self.started += now - self.paused_at  # shift the clock so playback resumes where it stopped
            self.paused_at = None

    def frame(self, now=None):
        """Bitmap of the frame due at now (looping); decodes only when the frame changed."""
        if self.loader is None:
            return None
        now = time.monotonic() if now is None else now
        elapsed = (self.paused_at if self.paused_at is not None else now) - self.started
        index = int(elapsed * self.fps) % self.count
        if index != self.index:
            result, bitmap = self.loader.Read(index)
            if result == c4d.IMAGERESULT_OK and bitmap is not None:
                # the loader's own bitmap, used as is: GetClone() of it returns an empty bitmap (drawn black);
                # it stays valid until close(), which also drops this reference
                self.bitmap, self.index = bitmap, index
        return self.bitmap


class ClipSlot:
    """What one area plays: the card key and clip kind it was pointed at, the clip's URL and its player."""

    def __init__(self):
        self.player = ClipPlayer()
        self.key = self.kind = self.url = None

    def clear(self):
        """Stop and forget; returns True when something was playing or loading."""
        busy = self.key is not None
        self.player.close()
        self.key = self.kind = self.url = None
        return busy


class ClipDeck:
    """The clips of all areas of the browser (hovered card, open card); each area plays at most one."""

    def __init__(self, areas):
        self.slots = {area: ClipSlot() for area in areas}

    def frame(self, area, key):
        """Bitmap to draw for card key in area, or None when that area is not playing that card."""
        slot = self.slots[area]
        return slot.player.frame() if slot.key == key and slot.player.playing else None

    def aim(self, area, key, kind, url):
        """Point area at a clip; False when it already is (nothing to load), else True and the old clip stops."""
        slot = self.slots[area]
        if (slot.key, slot.kind) == (key, kind):
            return False
        slot.clear()
        slot.key, slot.kind, slot.url = key, kind, url
        return True

    def start(self, url, path):
        """Open path in every area waiting for url; returns (areas started, areas that could not play it)."""
        started, failed = [], []
        for area, slot in self.slots.items():
            if slot.url != url or slot.player.playing:
                continue
            if slot.player.open(path):
                started.append(area)
            else:
                slot.clear()
                failed.append(area)
        return started, failed

    def stop(self, area=None):
        """Stop one area (or all); returns the areas that had a clip, whose still picture must come back."""
        areas = [area] if area is not None else list(self.slots)
        return [name for name in areas if self.slots[name].clear()]

    def playing(self):
        """Areas with a running clip."""
        return [area for area, slot in self.slots.items() if slot.player.playing]
