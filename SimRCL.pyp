"""SimRCL by Dead_wall: registers the browser command in Cinema 4D's Extensions menu.

The modules do the work; this file only wires them into the plugin system. It works in two layouts:
the release (plugins/SimRCL/SimRCL.pyp next to simready_lib/) and the development copy
(simready_lib/plugin/simready_browser.pyp, modules one level up).
"""
import os
import sys

import c4d
from c4d import bitmaps, plugins

HERE = os.path.dirname(os.path.abspath(__file__))


def find_lib():
    """Folder that holds simready_browser.py: simready_lib next to this file, else the folder above it."""
    for candidate in (os.path.join(HERE, "simready_lib"), os.path.dirname(HERE)):
        if os.path.isfile(os.path.join(candidate, "simready_browser.py")):
            return candidate
    return None


LIB = find_lib()
if LIB and LIB not in sys.path:
    sys.path.insert(0, LIB)

import simready_browser  # noqa: E402  (needs LIB on sys.path)

PLUGIN_ID = 1073247  # registered for Dead_wall at plugincafe.maxon.net (label SimRCL); also the window's layout slot
PLUGIN_NAME = "SimRCL by Dead_wall"
HELP = "Search, download and import NVIDIA SimReady assets"


def load_icon():
    """Icon bitmap from res/icon.png, or None so registration still works without it."""
    bitmap = bitmaps.BaseBitmap()
    path = os.path.join(HERE, "res", "icon.png")
    return bitmap if os.path.isfile(path) and bitmap.InitWith(path)[0] == c4d.IMAGERESULT_OK else None


class BrowserCommand(plugins.CommandData):
    """Opens the dockable browser window."""

    @staticmethod
    def get_dialog():
        """The one browser window of the session, shared with simready_browser.show()."""
        if simready_browser._DIALOG is None:
            simready_browser._DIALOG = simready_browser.BrowserDialog()
        return simready_browser._DIALOG

    def Execute(self, doc):
        """Show the window (or bring it forward)."""
        return simready_browser.show()

    def RestoreLayout(self, sec_ref):
        """Re-attach the window when Cinema 4D restores a saved layout."""
        return self.get_dialog().Restore(PLUGIN_ID, secret=sec_ref)


def register():
    """Register the command and report the result in the console."""
    ok = plugins.RegisterCommandPlugin(PLUGIN_ID, PLUGIN_NAME, 0, load_icon(), HELP, BrowserCommand())
    print("%s %s: %s" % (PLUGIN_NAME, simready_browser.simready_ui.VERSION if hasattr(simready_browser, "simready_ui")
                         else "", "registered" if ok else "registration failed"))


if __name__ == "__main__":
    register()
