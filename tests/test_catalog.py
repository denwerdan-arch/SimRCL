"""Sandbox checks of simready_catalog against saved service answers (no network)."""
import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib")
# Saved service answers (about 22 MB, not in the repository); point SIMRCL_FIXTURES at a folder of them.
FIXTURES = os.environ.get("SIMRCL_FIXTURES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures"))
sys.path.insert(0, ROOT)

import simready_catalog as cat  # noqa: E402
import simready_client  # noqa: E402

FILES = {"/wikidata_hierarchy.json": "hierarchy", "/search/stats/usd_properties": "stats",
         "/package_sizes.json": "sizes", "/library_media/usdsearch-dev/manifest.json": "media",
         "/featured.json": "featured"}


def fake_get_json(path):
    with open(os.path.join(FIXTURES, FILES[path] + ".json"), encoding="utf-8") as handle:
        return json.load(handle)


def check(label, got, want):
    status = "ok " if got == want else "BAD"
    print("%s %s: %r%s" % (status, label, got, "" if got == want else "  (want %r)" % (want,)))
    return got == want


def main():
    simready_client.get_json = fake_get_json
    catalog = cat.load_catalog(tempfile.mkdtemp())
    top = {n.label: n.count for n in catalog.tree.children}
    results = [check("top-level", top, {"Industrial": 1214, "OEM": 1063, "Residential": 1019, "Hospital": 256, "Lighting": 47})]
    results.append(check("mass", [o.count for o in cat.mass_options(catalog.stats)], [2027, 837, 479, 248]))
    results.append(check("rigid", [o.count for o in cat.rigid_options(catalog.stats)], [2363, 1214]))
    results.append(check("format_count", cat.format_count(3599), "3 599"))
    results.append(check("format_bytes", cat.format_bytes(47384571), "45.19 MB"))
    hits = fake_get_json.__globals__ and json.load(open(os.path.join(FIXTURES, "search_default.json")))["hits"]
    cards = [c for c in (cat.card_from_hit(h, catalog) for h in hits) if c]
    print([(c["title"], c["filename"], cat.format_bytes(c["bytes"])) for c in cards[:10]])
    selection = cat.toggle_member(cat.empty_selection(), "nodes", next(iter(catalog.nodes)))
    print(cat.search_fields(selection, catalog))
    results.append(check("date iso", cat.format_modified("2026-10-15T22:19:52.055621"), "15.10.2026, 22:19:52"))
    results.append(check("date property", cat.format_modified("2026-04-28 12:04:51"), "28.04.2026, 12:04:51"))
    results.append(check("date missing", cat.format_modified(None), ""))
    plain = {"filename": "a.usd", "title": None, "bytes": 1, "dims": None, "joints": 0}
    undated = [dict(plain, modified=None) for _ in range(4)]
    dated = [dict(plain, modified="2026-10-15T22:19:52") for _ in range(3)] + undated[:1]
    results.append(check("no date sort without data", "modified" in [k for k, _ in cat.available_sort_options(undated)], False))
    results.append(check("date sort with data", "modified" in [k for k, _ in cat.available_sort_options(dated)], True))
    results.append(check("relevance always", cat.available_sort_options([])[0][0], "relevance"))
    results += provider_checks(catalog)
    print(all(results))


def provider_checks(catalog):
    import simready_layout as layout
    raw = {"makers": [{"code": "oem:PalatialSim", "name": "Palatial", "group": ["isv"], "url": "https://palatial.example"},
                      {"code": "oem:Vertiv", "name": "Vertiv", "group": ["dsx"]},
                      {"code": "oem:LGElectronics", "name": "LG Electronics", "group": ["oem"]},
                      {"code": "oem:Old", "name": "Old", "kind": "isv", "segment": ""}]}
    makers = cat.reduce_makers(raw)
    withmakers = catalog._replace(makers=makers)
    providers = cat.provider_list(withmakers)
    names = {p.key: p for p in providers}
    branches = cat.provider_branch_keys(catalog.tree)
    shown = [row[0].label for row in cat.visible_rows(catalog.tree, set(), 1, branches)]
    groups = cat.provider_groups(providers)
    isv_only = cat.provider_groups(providers, "isv")
    hit = {"source": {"x_vlm_generated": [{"name": "caption", "value_text": ["white mug"]}, {"name": "tags", "value_text": ["mug", "cup"]},
                                           {"name": "colors", "value_text": []}]}}
    props = {"__polygon_count": "52649", "simready_metadata_Variants__Physics__PhysX__variantSetName": "x",
             "simready_metadata_Variants__Physics__MuJoCo__variantSetName": "x", "simready_metadata_author": "ForgeCAD"}
    chip = cat.selection_chips(dict(cat.empty_selection(), nodes=("oem:PalatialSim",)), withmakers)
    return [
        check("provider branch hidden from hierarchy", ("OEM" in shown, len(branches)), (False, 1)),
        check("provider count rolls up", sum(p.count for p in providers), 1063),
        check("groups from makers", (names["oem:PalatialSim"].groups, names["oem:Vertiv"].groups), (("isv",), ("dsx",))),
        check("older makers.json fields still read", makers["oem:Old"]["groups"], ["isv"]),
        check("isv site kept", makers["oem:PalatialSim"]["url"], "https://palatial.example"),
        check("kinds in landing order", cat.provider_kinds(providers)[:4], ("all", "oem", "isv", "dsx")),
        check("group headings in landing order", [h for h, _, _ in groups][:3], ["OEMs", "ISVs", "DSX"]),
        check("group count sums its makers", groups[1][1], sum(p.count for p in groups[1][2])),
        check("single group has no heading", [h for h, _, _ in isv_only], [""]),
        check("maker in two groups listed in both", [h for h, _, m in cat.provider_groups(
            [cat.Provider("a", "A", ("oem", "dsx"), 3, "")]) if m], ["OEMs", "DSX"]),
        check("tag", cat.provider_tag(cat.Provider("a", "A", ("oem", "dsx"), 3, "")), "OEM / DSX"),
        check("provider chip", chip[0][0], "Provider: Palatial"),
        check("provider name from makers", cat.provider_name(withmakers, "PalatialSim"), "Palatial"),
        check("provider name fallbacks", (cat.provider_name(withmakers, "nvidia"), cat.provider_name(withmakers, "someone")), ("NVIDIA", "someone")),
        check("vlm fields", cat._vlm_fields(hit["source"]), {"caption": ["white mug"], "tags": ["mug", "cup"]}),
        check("extras", cat._extras(props), {"polygons": 52649, "author": "ForgeCAD", "robot": None, "bodies": None, "engines": ["MuJoCo", "PhysX"]}),
        check("mass text", (cat.format_mass(26.949758), cat.format_mass(0.3203), cat.format_mass(None)), ("26.9 kg", "0.32 kg", "")),
        check("wrap", layout.wrap_lines("one two three four five six", 70, 7.0), ["one two", "three four", "five six"]),
        check("wrap limit", layout.wrap_lines("word " * 200, 200, 7.0, 3)[-1].endswith("..."), True),
        check("wrap fits", all(len(l) <= 28 for l in layout.wrap_lines("word " * 200, 200, 7.0, 3)), True),
    ]


if os.path.isdir(FIXTURES):
    main()
else:
    print("skipped: no fixtures in %s" % FIXTURES)
