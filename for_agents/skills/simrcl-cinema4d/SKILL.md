---
name: simrcl-cinema4d
description: Find, download and import NVIDIA SimReady assets into a Cinema 4D scene through the SimRCL plugin with few tokens. Use when the user asks to add, find or download SimReady models (props, furniture, robots, grippers, food) in Cinema 4D and a Cinema 4D MCP with exec_python is connected.
---

# SimRCL in Cinema 4D, token-cheap

SimRCL's `simready_agent` module answers every call with a few short lines, so an agent never has to read raw search JSON, file lists or scene dumps. Use it through the Cinema 4D MCP's `exec_python` (it runs on Cinema 4D's main thread; `c4d` is already imported there).

## 1. Load once per session

```python
import sys, os, glob, c4d
if "simready_agent" not in sys.modules and not any(os.path.isfile(os.path.join(p, "simready_agent.py")) for p in sys.path):
    prefs = c4d.storage.GeGetC4DPath(c4d.C4D_PATH_PREFS)  # the plugin normally put its folder on sys.path already
    found = sorted(glob.glob(os.path.join(prefs, "plugins", "*", "simready_lib"))
                   + glob.glob(os.path.join(prefs, "library", "scripts", "*", "simready_lib")))
    assert found, "SimRCL is not installed (plugins/SimRCL/simready_lib)"
    sys.path.insert(0, found[0])
import simready_agent as sr
print("ok")
```

Later calls only need `import simready_agent as sr`. Module state (results, downloads) lives until Cinema 4D restarts or the module is reloaded.

## 2. The loop

```python
print(sr.find("white lily", limit=5))   # numbered lines: name (file) | size | download size | joints | on disk
print(sr.info(1))                        # licence, mass, author, polygons, caption; only for a candidate you may pick
print(sr.fetch(1))                       # background download, returns at once ("already on disk" when cached)
print(sr.status())                       # poll; "name: ready" when done
print(sr.add(1, at=(0, 0, 0)))           # import into the active document; returns group, size in cm, unit, bottom y
```

Results are numbered from 1 and replaced by the next `find`.

## Rules that keep it cheap

- Print only what these functions return. Never print hits, cards, manifests, settings or object trees.
- `limit` 5-8. If nothing fits, change the words or the mode instead of asking for more results.
- Modes: `Hybrid` (default), `Keyword` for file names and ids (`"D00305"`, `"Robotiq_2F_85"`), `Text` for vague descriptions ("something to sit on").
- Size filter in metres on the catalog's USD axes, where z is the height: `sr.find("box", sizes={"z": (None, 0.3)})`.
- Choose from captions and sizes. Do not render previews to choose; render once at the end, small (for example 480 x 270), if the user wants to see the result.
- Downloads: start every needed `fetch` first, then poll `status()` every 10-20 s. Never wait in a loop inside `exec_python`: Cinema 4D's UI is frozen while it runs.
- When the user wants small downloads, compare the MB column before `fetch`.
- Licences: only CC-BY / Apache / BSD assets are searched by default. Pass `licensed=False` only when the user asks; CC-BY needs attribution, so tell the user which author `info` named.

## Placing models

- Catalog sizes are USD X x Y x Z (Z up). `add` reports Cinema 4D X x Y x Z (Y up) in cm, the scene unit, and the bottom height in scene units.
- To stand a model on a surface at height `h` (scene units): add it, then move the group by `h - bottom` on Y.
- `at=(x, y, z)` is in scene units. Check the unit in the `add` line: scenes made by artists often use 1 unit = 10 cm.
- The import uses the switches of the SimRCL window's Settings menu (materials for the scene's renderer, tidy hierarchy, controls for moving parts, layers). Each import is one undo step.
- Moving parts (wheels, doors, gripper fingers, robot joints) hang under an orange controller Null at the joint. At rest every controller is 0. A hinge turns with the controller's H rotation (in degrees, as in USD), a slider moves with its P.Y position. The controller's Protection tag holds the joint's limits. Pose the part through the controller, not the mesh.

## Errors

- `no result N: run find() first`: the numbers belong to the last `find`.
- `... is not downloaded: fetch(N) first`.
- `failed (...)` in `status()`: network or Hugging Face; retry `fetch(N)` once, then tell the user.
- `add` mentions "Materials were skipped": the USD runtime (system Python 3 + usd-core) is missing; tell the user to run SimRCL's `INSTALL.bat` again.
- The first `add` of a session can take up to a minute (it checks the USD runtime); later ones take seconds.

## Do not

- Do not change the user's other objects, materials or render settings unless asked.
- Do not delete downloaded packages or the user's files.
- Do not import into a document the user did not mean: check `c4d.documents.GetActiveDocument().GetDocumentName()` when several are open.
