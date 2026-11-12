"""Which renderer the imported materials are built for, and what that renderer offers.

A target is chosen in the settings menu or follows the render engine of the active document ("auto").
A renderer that is not installed falls back to the Standard material, which every Cinema 4D has.
"""
import collections

import c4d

REDSHIFT, STANDARD, ARNOLD, VRAY, OCTANE = "redshift", "standard", "arnold", "vray", "octane"
AUTO = "auto"
TARGETS = (REDSHIFT, STANDARD, ARNOLD, VRAY, OCTANE)
LABELS = {REDSHIFT: "Redshift", STANDARD: "Standard", ARNOLD: "Arnold", VRAY: "V-Ray", OCTANE: "Octane"}
# Render engine id (RDATA_RENDERENGINE) -> target. Physical and the viewport renderer read the same material as Standard.
ENGINE_TARGETS = {1036219: REDSHIFT, 0: STANDARD, 1023342: STANDARD, 300001061: STANDARD, 1029988: ARNOLD, 1053272: VRAY,
                  1029525: OCTANE}
# The video post plugin that proves a renderer is installed (Standard is built in).
ENGINE_PLUGINS = {REDSHIFT: 1036219, ARNOLD: 1029988, VRAY: 1053272, OCTANE: 1029525}
OPENPBR_TARGETS = (REDSHIFT, ARNOLD, VRAY)  # the renderers that ship an OpenPBR shader or mode (not Octane's classic material)

# round_corners: build the round corners nodes the model's controls drive (simready_roundcorners).
Choice = collections.namedtuple("Choice", "target openpbr note round_corners", defaults=(False,))


def is_installed(target):
    """True when the renderer of target is registered in this Cinema 4D."""
    plugin_id = ENGINE_PLUGINS.get(target)
    return plugin_id is None or c4d.plugins.FindPlugin(plugin_id, c4d.PLUGINTYPE_VIDEOPOST) is not None


def document_target(doc):
    """The target that matches the render engine of the document's active render settings."""
    render_data = doc.GetActiveRenderData()
    engine = render_data[c4d.RDATA_RENDERENGINE] if render_data else 0
    return ENGINE_TARGETS.get(engine, REDSHIFT)


def requested_target(setting, doc):
    """The target asked for: the setting, or the document's renderer for AUTO (and for an unknown value)."""
    return setting if setting in TARGETS else document_target(doc)


def openpbr_available(target):
    """True when the renderer of target offers OpenPBR in this installation (older V-Ray builds have no such mode)."""
    if target not in OPENPBR_TARGETS or not is_installed(target):
        return False
    if target != VRAY:
        return True
    import simready_mat_vray  # imported late: only V-Ray needs the probe
    return simready_mat_vray.has_openpbr()


def resolve(setting, prefer_openpbr, doc):
    """Choice(target, openpbr, note): the renderer to build for, whether to use its OpenPBR shader, and why it changed."""
    wanted = requested_target(setting, doc)
    if not is_installed(wanted):
        return Choice(STANDARD, False, "%s is not installed, built Standard materials" % LABELS[wanted])
    return Choice(wanted, bool(prefer_openpbr) and openpbr_available(wanted), "")


def label(choice):
    """Short text such as 'Redshift OpenPBR' for status messages."""
    return LABELS[choice.target] + (" OpenPBR" if choice.openpbr else "")
