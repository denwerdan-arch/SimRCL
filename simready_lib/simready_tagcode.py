"""Shared parts of the SimRCL Python tags that drive a model through user data on its group.

Each tag is generated from a feature part (what the settings do) and the common part below (which fields show,
when to ask Cinema 4D for another cycle). The feature part defines:
    settings(root) -> tuple of the user data values
    layout(values) -> {user data id: (hidden, label)} for the fields that depend on the others
    evaluate(root)  -> per-evaluation work that is allowed in evaluation threads (may do nothing)
    on_main_thread(root) -> work that must run on the main thread, such as editing materials (may do nothing)
    pending(root)   -> True while on_main_thread or the fields still have something to do
"""
import os

import c4d

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

COMMON_CODE = '''

def stale_fields(root):
    """[(id, container, (hidden, label))] of the fields that do not yet match the settings."""
    target = layout(settings(root))
    stale = []
    for did, bc in root.GetUserDataContainer():
        state = target.get(did[1].id)
        if state is not None and (bool(bc[c4d.DESC_HIDE]), bc[c4d.DESC_NAME]) != state:
            stale.append((did, bc, state))
    return stale


def sync_interface(root):
    """Hide and relabel the dependent fields; True when something changed."""
    stale = stale_fields(root)
    for did, bc, (hidden, label) in stale:
        bc[c4d.DESC_HIDE] = hidden
        bc[c4d.DESC_NAME] = bc[c4d.DESC_SHORT_NAME] = label
        root.SetUserDataContainer(did, bc)
    return bool(stale)


def main():
    root = op.GetObject()
    if root is None:
        return
    evaluate(root)
    # a change made after this cycle's messages were handled waits for the next message: ask for one more
    # cycle (EventAdd only posts an event, which is allowed from this thread); render clones of the document
    # never get messages, so only the open document asks
    if pending(root) and op.GetDocument() == c4d.documents.GetActiveDocument():
        c4d.EventAdd()


def message(msg_id, data):
    # main() runs in evaluation threads, where descriptions and materials must not change; messages arrive
    # on the main thread after scene changes, so that work is done from here
    root = op.GetObject()
    if root is None or not c4d.threading.GeIsMainThreadAndNoDrawThread():
        return True
    if sync_interface(root):
        # the Attribute Manager rebuilds a description only when it is marked changed and an event follows
        root.SetDirty(c4d.DIRTYFLAGS_DESCRIPTION)
        c4d.EventAdd()
    on_main_thread(root)
    return True
'''


def compose(feature_code, values):
    """Full tag source: feature part plus common part, with every __KEY__ replaced by values[KEY]."""
    code = feature_code + COMMON_CODE
    for key, value in values.items():
        code = code.replace("__%s__" % key, str(value))
    return code


def _named(dtype, name, hidden):
    bc = c4d.GetCustomDataTypeDefault(dtype)
    bc[c4d.DESC_NAME] = bc[c4d.DESC_SHORT_NAME] = name
    bc[c4d.DESC_HIDE] = hidden
    return bc


def cycle(name, labels, hidden=False):
    """User data description of a drop-down list."""
    bc = _named(c4d.DTYPE_LONG, name, hidden)
    bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
    entries = c4d.BaseContainer()
    for index, label in enumerate(labels):
        entries.SetString(index, label)
    bc.SetContainer(c4d.DESC_CYCLE, entries)
    return bc


def check(name, hidden=False):
    """User data description of a check box."""
    return _named(c4d.DTYPE_BOOL, name, hidden)


def factor(name, hidden=False):
    """User data description of a plain number slider for multipliers (0.01 .. 1000, slider to 10)."""
    bc = _named(c4d.DTYPE_REAL, name, hidden)
    bc[c4d.DESC_UNIT] = c4d.DESC_UNIT_REAL
    bc[c4d.DESC_MIN], bc[c4d.DESC_MINSLIDER] = 0.01, 0.1
    bc[c4d.DESC_MAX], bc[c4d.DESC_MAXSLIDER] = 1000.0, 10.0
    bc[c4d.DESC_STEP] = 0.1
    bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    return bc


def length(name, slider_max, hidden=False):
    """User data description of a distance in scene units (shown in the document's unit)."""
    bc = _named(c4d.DTYPE_REAL, name, hidden)
    bc[c4d.DESC_UNIT] = c4d.DESC_UNIT_METER
    bc[c4d.DESC_MIN], bc[c4d.DESC_MINSLIDER] = 0.0, 0.0
    bc[c4d.DESC_MAXSLIDER] = slider_max
    bc[c4d.DESC_STEP] = slider_max / 100.0
    bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    return bc


def remove(root, names, tag_names):
    """Delete root's user data named in names and its Python tags named in tag_names (so re-adding never stacks).

    tag_names lists the current tag name and earlier ones, so models imported under the old brand are cleaned too.
    """
    for did, bc in root.GetUserDataContainer():
        if bc[c4d.DESC_NAME] in names:
            root.RemoveUserData(did)
    for tag in [tag for tag in root.GetTags() if tag.GetType() == c4d.Tpython and tag.GetName() in tag_names]:
        tag.Remove()


def make_tag(root, name, icon_file, code):
    """Add the Python tag name with code to root, with its icon when the icon file is present."""
    tag = root.MakeTag(c4d.Tpython)
    tag.SetName(name)
    icon = os.path.join(ICONS, icon_file)
    if os.path.isfile(icon):
        tag[c4d.ID_BASELIST_ICON_FILE] = icon
    tag[c4d.TPYTHON_CODE] = code
    return tag
