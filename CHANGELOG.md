# Changelog

## 1.2.1

- Octane materials (OctaneRender for Cinema 4D 2027.1): Universal material with Image Texture shaders for albedo, metallic, roughness, normal, opacity and emission; packed ORM maps are read per channel through Channel picker shaders, colour maps in sRGB, data maps linear. Chosen automatically when the scene renders with Octane, or in Settings > Materials. Texture repeat follows the texture tag, and Round corners on the model drive the material's Round edges shader. With "Prefer OpenPBR" on, Octane gets its OpenPBR surface material instead (same maps; emission through weight and luminance); an Octane without it gets the Universal material.
- Meshes that arrive as loose triangles are welded on import. Some assets were converted from STL, where every triangle has its own three points (Menlo's Asimov humanoid: 2 877 108 points for 473 913 positions), so nothing was connected: cylinders rendered faceted and selections stopped at each triangle. Coincident points are now joined with a tolerance far below the model's detail; polygons, UVs, vertex colours, selections and materials stay as they were. Only meshes where at least 30 % of the points are duplicates are touched. Off by default; switch it on in Settings: "Weld loose triangles (STL-style meshes)". Models imported before keep their loose triangles; import them again with the switch on (or select the meshes and run Mesh > Commands > Optimize with points only).
- Fixed: models with faces of five or more corners came in without materials (the NVIDIA warehouse office chair: 13 083 USD faces became 13 089 polygons, so the material subsets no longer matched and were skipped). Face indices are now mapped onto the polygons Cinema 4D made from each n-gon; the same mapping lets such meshes take part in the hierarchy from joints.

## 1.2.0

- Update check: when the window opens (at most once a day) SimRCL asks GitHub whether a newer release is out and shows an "Update x.y.z" button next to its name; a click opens the release page (install it with its INSTALL.bat). Settings: "Check for updates now", "Check for updates on start" (on by default). The request goes to api.github.com and carries nothing about you or your scenes; without internet nothing changes.

## 1.1.0

The project is now called SimRCL by Dead_wall (SimReady Central Library; was SimRS). Settings and downloads of earlier versions are kept.

- A real plugin now (registered ID 1073247): Extensions > SimRCL by Dead_wall, the window docks and comes back with a saved layout.
- Installer: double-click INSTALL.bat; it copies the plugin into every Cinema 4D 2026, backs up earlier copies (including the old script versions) and installs the USD runtime.
- Controls for moving parts: wheels, doors, drawers and robot joints get a controller that rotates or slides the part within its joint limits (Settings: "Controls for moving parts").
- Texture repeat from USD on every renderer, adjustable on the model: UV mode Auto / Custom / Off, Uniform UV or separate U and V factors.
- Round corners on the model for Redshift, Arnold and V-Ray: off until switched on in the group's user data; radius (default 0.1 cm), same object only, corners (V-Ray).
- Area Weighted Phong normals, one-mesh models split by material (only when the parts share no points), one layer per imported asset (switches in Settings).
- Search: match percentages from the catalog's vision model with a "Match %" sort; mode descriptions.
- Size filter as on the site: min / max per axis with a two-thumb slider.
- Providers grouped as on the site: OEMs, ISVs, DSX, with asset counts.
- Video previews: 360 degree turn and moving parts on hover (off by default) and in a full-size window from the details.
- The author's name in the header links to https://trycad.online/?lang=en.
- `simready_agent.py`: short-answer functions for AI agents (find, info, fetch, status, add); see `AGENTS.md`.
- Fixed: "Clear all" with a non-default sort loaded the whole catalog; the USD runtime could break after a Windows temp clean-up (it now lives in `%LOCALAPPDATA%` and repairs itself); an office chair got controls on only some of its casters.

## 1.0.5

- Moving parts get their axis on their physics joint (hinge pin, wheel hub, robot joint), and parts held by a joint are parented under their carrier even when the joint links groups rather than meshes. Fixes the scissors-type case where the moving half kept its axis at the model origin.

## 1.0.4

- "More" button next to SIMILAR in the details: searches the whole catalog for the asset's name.
- Fixed: imported parts had their axis at the model origin (the assets store parts that way). Parts without an authored pivot now get the axis at the centre of their bounding box; nothing moves in the scene. Re-import older groups to get it.

## 1.0.3

- "More from ..." in the asset details is replaced by SIMILAR: up to three tiles of assets of the same kind, searched across the whole catalog by the asset's object type. A similar asset that is not in the results opens on its own; the arrows lead back to the results.
- Colliders are hidden on import: groups and meshes named Colliders, Collider_N and the like get viewport and render visibility Off. They stay in the scene for simulation and export.

## 1.0.2

- New PROVIDER section in the sidebar: the companies of the catalog as check boxes with asset counts, an OEM / ISV tag, groups (Robotics, Equipment, DSX, ISVs, Other) and an All / OEMs / ISVs switch. A selected company shows as a "Provider: ..." chip. The OEM branch is no longer duplicated in the hierarchy.
- Richer asset details: Provider, Author, Polygons, Mass, Bodies, Physics, Robot, Colors, Materials, Setting, Style, Scale, State, Features, Text on it, plus DESCRIPTION and TAGS. Rows appear only when the service sends the data; polygons, mass, author, robot type and physics variants come with the full record that loads when a card opens.

## 1.0.1

- Adjusted to the November 2026 update of the catalog service: it no longer sends file dates in lists. The details panel shows the asset date from its USD data (row "Date"), and the date sort is offered only when the data is there.

## 1.0.0

First public release.

- Catalog search (natural language, keywords or both), categories, filters, sorting, grid and list views.
- Package downloads with progress, local library with "Downloaded" filter, Re-Download, custom download folder.
- Licensing guide in English and Russian.
- Import with tidy hierarchy, parenting from physics joints, scale baked into the geometry, UDIM textures.
- Materials for Redshift, Standard, Arnold and V-Ray; OpenPBR for Redshift, Arnold and V-Ray.
- Settings: download folder, tidy hierarchy, material renderer, prefer OpenPBR.
