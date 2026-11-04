# SimRCL for agents: how the code works and how to port it

You are an AI agent asked to adapt SimRCL (a Cinema 4D browser/importer for NVIDIA SimReady assets) to another program (Blender, Houdini, 3ds Max, Maya, Unreal, a web tool) or another OS. Read this file first; it saves you reading 8 000 lines.

## Map

Everything lives in `simready_lib/`. `SimRCL.pyp` (the plugin file) only puts that folder on `sys.path` and registers the Extensions menu command that opens the window.

Portable, standard library only, no Cinema 4D (reuse as they are):

| Module | Role |
|---|---|
| `simready_client.py` | HTTP: search, page through results, match scores, package manifest, downloads, thumbnails |
| `simready_catalog.py` | catalog datasets (hierarchy, sizes, media, makers, titles), filters to service fields, cards from hits, sorting, formatting |
| `simready_dims.py` | size filter maths (min/max per axis, the site's cubic slider) |
| `simready_library.py` | which packages are on disk (`.complete` marker per package) |
| `simready_media.py` | preview image and video URLs and their cache |
| `simready_settings.py` | settings JSON in `%APPDATA%\SRC by Deadwall` |
| `simready_tasks.py` | worker threads that push events into a queue for the UI thread |
| `simready_material_spec.py` | renderer-independent reading of an inspected UsdPreviewSurface material |
| `simready_inspect.py` | runs in a separate Python with `usd-core`; prints JSON: meshes, GeomSubsets, materials, joints, xforms, up axis, metersPerUnit |
| `simready_runtime.py` | finds a system Python, installs `usd-core` into a private folder, runs the inspector |
| `simready_update.py` | asks GitHub's releases API (at most once a day) whether a newer SimRCL is out |
| `simready_agent.py` | short text answers for agents (find, info, fetch, status, add); only `add` needs Cinema 4D |
| `simready_layout.py` | pure geometry of the panels (only useful if you rebuild the same UI) |

Cinema 4D specific (rewrite for the target program; keep the order and the reasons below):

`simready_import.py` (pipeline), `simready_xforms.py`, `simready_cleanup.py`, `simready_hierarchy.py`, `simready_axes.py`, `simready_rig.py`, `simready_colliders.py`, `simready_split.py`, `simready_shading.py`, `simready_layers.py`, `simready_materials.py` + `simready_mat_redshift.py` / `_arnold` / `_vray` / `_standard`, `simready_render_target.py`, `simready_uvscale.py`, `simready_roundcorners.py`, `simready_tagcode.py`, all `simready_ui*.py`, `simready_video*.py`, `simready_browser.py`.

## The service

Base URL `https://nvidia-simready-central.hf.space` (a Hugging Face Space; it can sleep, so the first request may take a minute).

- `POST /search_hybrid`: JSON body built by `simready_client.search_body`. Text: `hybrid_text_query` (keywords) and/or `vector_queries` `[{"field_name": "siglip2-embedding.embedding", "query_type": "text", "query": ...}]` (meaning). `file_extension_include: "usd*"`, `limit`, `cursor`, `return_usd_properties` (10-20x larger pages, ask only for one asset), `return_usd_dimensions`, `return_vision_generated_metadata`. Filters: `filter_by_properties_include_any: "prop=value,prop=value"` (one comma string, lists are rejected), `min_bbox_x` / `max_bbox_z` in metres. Answer: `hits`, `total`, `has_more`, `next_cursor`.
- `POST /vlm_validate/batch_stream`: `{"query_text", "items": [{"id", "asset_url"}]}`, one JSON line per asset with `verdict.similarity_score` (the site's match %).
- `GET /download/asset?asset_url=<hf path>&manifest_only=true`: file list of a package.
- Datasets: `/wikidata_hierarchy.json`, `/search/stats/usd_properties`, `/package_sizes.json`, `/makers.json`, `/library_media/usdsearch-dev/manifest.json`, `/featured.json`. `load_catalog` caches them for a day.

Asset paths look like `hf://huggingface.co/datasets/<org>/<repo>/resolve/<commit>/<package>/simready_usd/<file>.usd`. Files download from `https://huggingface.co/datasets/<repo>/resolve/<commit>/<package>/<rel>`. Skip `source_assets/` (duplicates the textures) and `.thumbs/`. Write through `.part` files and check sizes; mark a finished package with `.complete`.

Licences: `ALLOWED_LICENSES` in `simready_client.py` is the policy (CC-BY-4.0 spellings, Apache-2.0, BSD-3-Clause). Do not widen it silently; the user decides.

## Import pipeline and why each step exists

`simready_import.import_asset` runs these in order. Most steps fix a real problem of SimReady files or of the host's USD importer; check whether your host has the same problem before porting a step.

1. Load the USD with the host's importer into a detached scene.
2. Inspect the same file out of process (`simready_inspect.py`). Cinema 4D has no `pxr`, and loading a second USD build into the host can crash it. Blender and Houdini ship USD: there you can inspect in process, but keep the JSON shape so the material code stays shared.
3. Repair transforms (`simready_xforms`): parts with several xformOps (ForgeCAD writes jointFrame, a named rotate and jointRest) come in at wrong places in C4D. The inspector reports every prim's local matrix; correct only objects that differ.
4. Materials (`simready_materials` + backends): the host importer ignores UsdPreviewSurface networks on instanceable prims and their GeomSubsets. Build materials from the inspector JSON; meshes are matched by the importer's traversal order, so bind before any clean-up renames or deletes.
5. UV tiling: SimReady repeats small textures through `UsdTransform2d.scale` (an office chair fabric is 8x). Apply it where the host renders it on every renderer (C4D: the texture tag's tiles).
6. Tidy (`simready_cleanup`): remove empty Scopes, wrapper Xforms, importer tags; keep grouping the model defines.
6a. Axes (`simready_axes`): many assets store parts with identity transforms and points in model space, so every pivot sits at the origin; move those pivots to the part's centre, keep authored ones.
7. Hierarchy from joints (`simready_hierarchy`): physics joints say which part carries which; parent accordingly and put each moving part's pivot on its joint anchor. A joint can point at a mesh, a group or an instance whose mesh name differs from the joint's; `resolve_body` falls back to the parent Xform.
8. Colliders (`simready_colliders`): `Colliders` groups stay, hidden in viewport and render.
8a. Weld (`simready_weld`, off by default): STL conversions store every triangle with its own points; join coincident points (Optimize, points only, tolerance 1e-6 of the bounding diagonal) when at least 30 % are duplicates, before the split, which decides by shared points.

N-gons: C4D splits USD faces with 5+ corners into several polygons, so face indices from the inspector shift. `simready_ngons.matched_spec` remaps them through the polygon translation map (pieces of one n-gon are consecutive and share one entry); materials and joints use it.
9. Split (`simready_split`): a one-mesh model with several materials becomes one object per material, only if the material parts share no points (otherwise it would tear) and never for models with joints.
10. Normals (`simready_shading`): area-weighted smoothing; uniform smoothing shows bands on long thin triangles.
11. Units: SimReady is metres, Z up (`up_axis`, `meters_per_unit` in the JSON). Bake the scale into the geometry so the group keeps scale 1.
12. Controls (`simready_rig`): a controller per moving part, limited by the joint's limits (revolute in degrees, prismatic in stage units).
13. Layers, then commit to the document as one undo step.

## Porting checklist

1. Copy the portable modules unchanged. The release has no tests; with the source repository run `python tests/test_*.py` (plain scripts, no pytest, each prints ok/BAD lines), otherwise check each module with a few calls against the live service.
2. Write a host adapter with the same functions as `simready_import.py` (load, detach, commit) and port steps 3-13 one at a time; test each on: an office chair (`sm_chair_office_fabric_manager_a01`, joints + UV scale), a desk (split by material), a robot (Comau or a Robotiq gripper, joint chain), a door (prismatic/revolute limits).
3. Materials: start from `simready_material_spec.py` (base colour, metallic, roughness, normal, opacity, emission, UV transform) and write one backend for the host's main renderer.
4. UI last. `simready_agent.py` shows the minimum an agent or a simple panel needs: find, info, fetch, status, add.
5. Keep the data folder names (`SRC by Deadwall`) if the user also runs the Cinema 4D version, so downloads are shared.

## Rules of the code base (follow them in changes)

- Functional style, early returns, functions under about 20 lines, docstrings on public functions, comments say why.
- No Cinema 4D imports in the portable modules; worker threads never touch the scene.
- Every change goes into `CHANGELOG.md`; before replacing files, copy them to `_legacy/<reason>_<date>/`.
- Do not change the user's scenes beyond what they asked; imports are one undo step.
