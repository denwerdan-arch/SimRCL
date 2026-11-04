"""Correct transforms that Cinema 4D's USD importer gets wrong.

Some assets give a part several transform ops (ForgeCAD writes jointFrame matrix, a named rotateX for the
joint angle and a jointRest matrix). The native importer mis-composes such stacks: the parts come in at wrong
places. The inspector (real USD, outside Cinema 4D) reports every prim's local matrix; here each object that
was loaded for a prim is compared with it and corrected when it differs. Objects that already match, which is
the normal case, are left alone.
"""
import c4d

TOLERANCE = 1e-4  # relative to the matrix scale; the importer's own float noise is far below


def to_c4d(vector, up_axis):
    """Stage coordinates -> Cinema 4D coordinates: Z-up swaps y and z, Y-up mirrors z (both are reflections)."""
    x, y, z = vector
    return c4d.Vector(x, z, y) if up_axis == "Z" else c4d.Vector(x, y, -z)


def _linear(rows, vector):
    """Image of a direction under a USD matrix (row-vector convention: v * M)."""
    return [sum(vector[i] * rows[i][k] for i in range(3)) for k in range(3)]


def matrix_from_usd(rows, up_axis):
    """Cinema 4D local matrix of a USD local matrix given as 4 rows: the same map seen through the reflection."""
    axes = [to_c4d(unit, up_axis) for unit in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]  # C4D x, y, z in stage terms
    images = [to_c4d(_linear(rows, (axis.x, axis.y, axis.z)), up_axis) for axis in axes]
    return c4d.Matrix(to_c4d(rows[3][:3], up_axis), images[0], images[1], images[2])


def object_paths(doc):
    """{USD-style path: object} of every object in doc, built from the names (the importer keeps prim names)."""
    found, stack = {}, [(obj, "") for obj in _siblings(doc.GetFirstObject())]
    while stack:
        obj, parent_path = stack.pop()
        path = parent_path + "/" + obj.GetName()
        found.setdefault(path, obj)  # a repeated name is ambiguous; the first one keeps its match
        stack.extend((child, path) for child in obj.GetChildren())
    return found


def _siblings(obj):
    while obj:
        yield obj
        obj = obj.GetNext()


def differs(a, b):
    """True when two matrices differ by more than the tolerance in any axis or the offset."""
    scale = max(1.0, a.v1.GetLength(), a.v2.GetLength(), a.v3.GetLength(), a.off.GetLength())
    return any((p - q).GetLength() > TOLERANCE * scale for p, q in ((a.off, b.off), (a.v1, b.v1), (a.v2, b.v2), (a.v3, b.v3)))


def repair_transforms(doc, xforms, up_axis):
    """Give every loaded object whose local matrix disagrees with USD the USD one; returns the names fixed.

    Parents and children are both corrected from their own local matrices, so the order does not matter.
    """
    fixed = []
    for path, obj in object_paths(doc).items():
        rows = xforms.get(path)
        if rows is None:
            continue
        wanted = matrix_from_usd(rows, up_axis)
        if differs(obj.GetMl(), wanted):
            obj.SetMl(wanted)
            fixed.append(obj.GetName())
    return fixed
