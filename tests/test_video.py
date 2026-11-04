"""Sandbox checks of the hover-clip data: manifest reduction, clip URLs, cache names, crop maths, setting."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))


class _Constants:
    """Stand-in for the c4d module: any attribute is a unique integer."""

    def __init__(self):
        self._ids = {}

    def __getattr__(self, name):
        if name == "gui":
            return _Constants()
        return self._ids.setdefault(name, len(self._ids) + 1)


sys.modules.setdefault("c4d", _Constants())

import simready_catalog as cat  # noqa: E402
import simready_media as media  # noqa: E402
import simready_settings as settings  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


ENTRY = {"id": "abc", "moving": 4, "still": {"files": {"tile": "still_tile.jpg", "poster": "still_poster.jpg"}},
         "spin": {"files": {"card": "spin_card.mp4", "poster": "spin_start.webp"}},
         "rtxclip": {"files": {"card": "jointsclip_rtx_card.mp4", "textured": "jointsclip_rtx.mp4"}}}
STATIC = {"id": "def", "still": {"files": {"tile": "t.jpg"}}, "spin": {"files": {"card": "spin_card.mp4"}}}


def main():
    moving, static = cat._media_entry(ENTRY), cat._media_entry(STATIC)
    url = media.video_url({"media": moving, "key": "k"}, media.JOINTS)
    results = [
        check("clips kept", (moving["spin"], moving["joints"]), ("spin_card.mp4", "jointsclip_rtx.mp4")),
        check("no moving parts clip", static["joints"], None),
        check("joints url", url.endswith("/library_media/usdsearch-dev/abc/jointsclip_rtx.mp4"), True),
        check("joints falls back to the turn", media.video_url({"media": static, "key": "k"}, media.JOINTS).endswith("/def/spin_card.mp4"), True),
        check("no media, no clip", media.video_url({"media": {}, "key": "k"}, media.SPIN), None),
        check("clip cache suffix", media.image_path(url, "c")[-4:], ".mp4"),
        check("image cache suffix", media.image_path("https://x/y.jpg", "c")[-4:], ".jpg"),
        check("video off by default", settings.video_enabled({}), False),
        check("video switch", settings.video_enabled(settings.with_video({}, True)), True),
    ]
    import simready_layout as layout
    results += [
        check("square from square", layout.cover_crop(640, 640, 100, 100), (0, 0, 640, 640)),
        check("square clip in a wide poster", layout.cover_crop(960, 960, 368, 230), (0, 180, 960, 600)),
        check("wide picture in a square", layout.cover_crop(1280, 800, 100, 100), (240, 0, 800, 800)),
        check("square clip fits a wide window", layout.contain_rect(960, 960, (0, 40, 1000, 840)), (100, 40, 900, 840)),
        check("square clip fits a tall window", layout.contain_rect(960, 960, (0, 0, 600, 900)), (0, 150, 600, 750)),
        check("S, M, L differ in a narrow panel", len({layout.result_rects(1, 380, k, False)[0][2] - layout.result_rects(1, 380, k, False)[0][0] for k in "SML"}), 3),
        check("narrow row is centred", layout.result_rects(1, 380, "S", False)[0][0] > layout.GRID_PAD, True),
    ]
    results += deck_checks()
    print(all(results))


def deck_checks():
    """ClipDeck bookkeeping with a player whose open() pretends to succeed for '.mp4' paths."""
    sys.modules["c4d"].bitmaps = None
    import simready_video as video

    def fake_open(self, path):
        self.loader = object() if path.endswith(".mp4") else None
        return self.loader is not None
    video.ClipPlayer.open = fake_open
    video.ClipPlayer.close = lambda self: setattr(self, "loader", None)
    deck = video.ClipDeck(("results", "detail"))
    first = deck.aim("results", "a", "spin", "u1")
    again = deck.aim("results", "a", "spin", "u1")
    deck.aim("detail", "a", "joints", "u2")
    started = deck.start("u1", "x.mp4")
    playing = deck.playing()
    switched = deck.aim("results", "b", "spin", "u3")
    after_switch = deck.playing()
    failed = (deck.aim("detail", "c", "joints", "u4"), deck.start("u4", "broken.bin"))
    stopped = deck.stop()
    player = video.ClipPlayer()
    player.started = 0.0
    player.toggle_pause(now=2.0)
    player.toggle_pause(now=5.0)
    return [
        check("pause shifts the clock", (player.paused, player.started), (False, 3.0)),
        check("aim new clip", (first, again), (True, False)),
        check("only the waiting area starts", started, (["results"], [])),
        check("playing areas", playing, ["results"]),
        check("hovering another card stops the old clip", (switched, after_switch), (True, [])),
        check("unplayable clip reported", failed, (True, ([], ["detail"]))),
        check("stop all reports busy areas", stopped, ["results"]),
    ]


main()
