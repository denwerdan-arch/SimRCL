"""Texture repeat (UV tiling) of imported materials, adjustable on the model.

SimReady materials often repeat a small texture many times (the office chair's plastic 9x, its fabric 8x),
written as a UsdTransform2d scale. The repeat goes on the texture tag's Tiles U/V for every renderer: checked
by rendering a 2 x 2 colour test with tiles 3 x 3 in Standard, Redshift, Arnold and V-Ray, all repeat it 3 x 3.
Redshift could not take it in its nodes anyway (the sampler scale is a 2D vector Python cannot write), and one
place for all renderers is what lets the override below behave the same everywhere.

The model's group gets user data: "UV mode" Auto (the USD value), Custom (the USD value times the factors) or
Off (1:1), "Uniform UV" and the factors. A Python tag "SimRCL UV scale" applies them to the asset's texture tags
and shows only the fields the mode uses (simready_tagcode). Each texture tag remembers its USD value in its own
container, so changing the mode never loses it.
"""
import c4d

import simready_tagcode as tagcode

# Private container ids on texture tags (outside the tag's own parameter range).
MARK, AUTO_U, AUTO_V = 1063900, 1063901, 1063902
MODES = ("Auto (from USD)", "Custom (USD x factor)", "Off (1:1)")
TAG_NAME = "SimRCL UV scale"
OLD_TAG_NAMES = ("SimRS UV scale",)  # before the rename to SimRCL
ICON_FILE = "simrs_uv_scale.png"
LABELS = {"mode": "UV mode", "uniform": "Uniform UV", "u": "U x", "v": "V x"}
UNIFORM_LABEL = "UV x"  # the U x field while Uniform UV is on (also the first version's uniform slider)


def _texture_tags(root):
    stack = [root]
    while stack:
        obj = stack.pop()
        stack.extend(obj.GetChildren())
        for tag in obj.GetTags():
            if tag.GetType() == c4d.Ttexture:
                yield tag


def set_auto_tiles(root, scales):
    """Remember each material's USD tiling on its texture tags below root and set Tiles U/V to it.

    scales: {material: (s, t)}. Returns how many tags were set.
    """
    count = 0
    for tag in _texture_tags(root):
        scale = scales.get(tag[c4d.TEXTURETAG_MATERIAL])
        if scale is None:
            continue
        data = tag.GetDataInstance()
        data.SetBool(MARK, True)
        data.SetFloat(AUTO_U, scale[0])
        data.SetFloat(AUTO_V, scale[1])
        tag[c4d.TEXTURETAG_TILESX], tag[c4d.TEXTURETAG_TILESY] = scale
        count += 1
    return count


FEATURE_CODE = '''"""SimRCL: applies the model's UV user data to the Tiles U/V of its texture tags.

Fields the mode does not use are hidden: user data cannot be greyed out (only plugin descriptions can,
through GetDEnabling), so hiding is the way to keep them out of reach.
"""
import c4d

MARK, AUTO_U, AUTO_V = __MARK__, __AUTO_U__, __AUTO_V__
MODE, UNIFORM, U, V = __MODE__, __UNIFORM__, __U__, __V__
CUSTOM, OFF = 1, 2


def wanted(mode, auto, factors):
    """Tiles (u, v) for a texture tag whose USD tiling is auto."""
    if mode == CUSTOM:
        return auto[0] * factors[0], auto[1] * factors[1]
    if mode == OFF:
        return 1.0, 1.0
    return auto


def factors(mode, uniform, u, v):
    """(u, v) factors; Uniform UV makes the U x field drive both."""
    return (u, u) if uniform else (u, v)


def settings(root):
    return tuple(root[c4d.ID_USERDATA, index] for index in (MODE, UNIFORM, U, V))


def layout(values):
    """{user data id: (hidden, label)} for the fields that depend on the mode."""
    custom, uniform = values[0] == CUSTOM, values[1]
    return {UNIFORM: (not custom, "Uniform UV"), U: (not custom, "UV x" if uniform else "U x"),
            V: (not custom or uniform, "V x")}


def marked_tags(root):
    stack = [root]
    while stack:
        obj = stack.pop()
        stack.extend(obj.GetChildren())
        for tag in obj.GetTags():
            if tag.GetType() == c4d.Ttexture and tag.GetDataInstance().GetBool(MARK):
                yield tag


def evaluate(root):
    mode, uniform, u, v = settings(root)
    scale = factors(mode, uniform, u, v)
    for tag in marked_tags(root):
        data = tag.GetDataInstance()
        tiles = wanted(mode, (data.GetFloat(AUTO_U), data.GetFloat(AUTO_V)), scale)
        # write only on change: the tag runs on every scene evaluation
        if abs(tag[c4d.TEXTURETAG_TILESX] - tiles[0]) > 1e-6 or abs(tag[c4d.TEXTURETAG_TILESY] - tiles[1]) > 1e-6:
            tag[c4d.TEXTURETAG_TILESX], tag[c4d.TEXTURETAG_TILESY] = tiles


def on_main_thread(root):
    pass


def pending(root):
    return bool(stale_fields(root))
'''


def tag_code(ids):
    """The Python tag source for the user data ids {'mode', 'uniform', 'u', 'v'}."""
    values = dict(MARK=MARK, AUTO_U=AUTO_U, AUTO_V=AUTO_V, **{key.upper(): number for key, number in ids.items()})
    return tagcode.compose(FEATURE_CODE, values)


def _add_fields(root):
    # created as the tag shows them in Auto mode, so they do not flash before its first message
    ids = {"mode": root.AddUserData(tagcode.cycle(LABELS["mode"], MODES)),
           "uniform": root.AddUserData(tagcode.check(LABELS["uniform"], True)),
           "u": root.AddUserData(tagcode.factor(UNIFORM_LABEL, True)),
           "v": root.AddUserData(tagcode.factor(LABELS["v"], True))}
    for key in ("u", "v"):
        root[ids[key]] = 1.0
    root[ids["mode"]], root[ids["uniform"]] = 0, True
    return ids


def add_controls(root):
    """User data (UV mode, Uniform UV, U x, V x) on root and the Python tag that applies them; returns the tag."""
    tagcode.remove(root, set(LABELS.values()) | {UNIFORM_LABEL}, (TAG_NAME,) + OLD_TAG_NAMES)
    ids = _add_fields(root)
    return tagcode.make_tag(root, TAG_NAME, ICON_FILE, tag_code({key: did[1].id for key, did in ids.items()}))
