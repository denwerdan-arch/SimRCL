"""Sandbox checks of the agent entry points: result lines, filters, facts, find/fetch/status with a fake service."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_agent as agent  # noqa: E402
import simready_catalog as cat  # noqa: E402
import simready_client as client  # noqa: E402

LILY = "hf://huggingface.co/datasets/PalatialSim/palatial-nv-asset-library/resolve/69a87329/D00305/simready_usd/D00305.usd"


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def fake_hit(path, caption):
    return {"source": {"path": path, "name": os.path.basename(path), "base_key": "k",
                       "usd_dimensions": {"bbox_dimension_x": 0.1157, "bbox_dimension_y": 0.1107, "bbox_dimension_z": 0.1919},
                       "plugin_thumbnail_to_vision_metadata_metadata_vlm_generated": [
                           {"name": "caption", "value_text": [caption]}]}}


def main():
    card = {"title": None, "filename": "D00305.usd", "vlm": {"caption": ["White lily flower with leafy green stem"]},
            "dims": (0.1157, 0.1107, 0.1919), "bytes": 2202009, "joints": 0}
    long_card = dict(card, vlm={"caption": ["x" * 120]})
    filters = agent.search_filters({"z": (None, 0.3)})
    saved = (client.search_page, agent._catalog, agent._download_dir, client.is_cached)
    client.search_page = lambda *a, **k: ([fake_hit(LILY, "White lily flower")], 1, None)
    agent._catalog = lambda: cat.Catalog(tree=None, nodes={}, hierarchy={}, sizes={"k": 2202009}, media={},
                                         stats={}, featured=[], titles={}, makers={})
    agent._download_dir = lambda: "/nowhere"
    client.is_cached = lambda asset, folder: True
    try:
        found = agent.find("lily", limit=3)
        fetched = agent.fetch(1)
        status = agent.status()
        missing = _raises(lambda: agent.fetch(5))
    finally:
        client.search_page, agent._catalog, agent._download_dir, client.is_cached = saved
    results = [
        check("caption from the vision model", agent.caption(card), "White lily flower with leafy green stem"),
        check("long caption is cut", len(agent.caption(long_card)), agent.CAPTION_CHARS),
        check("curated title wins", agent.caption(dict(card, title="Lily")), "Lily"),
        check("result line", agent.result_line(2, card, cached=True),
              "2. White lily flower with leafy green stem (D00305) | 11.6 x 11.1 x 19.2 cm | 2.1 MB | on disk"),
        check("joints shown", "3 joints" in agent.result_line(1, dict(card, joints=3)), True),
        check("one joint", "| 1 joint" in agent.result_line(1, dict(card, joints=1)), True),
        check("metres above a metre", agent.size_label((1.8, 0.912, 0.84)), "1.8 x 0.91 x 0.84 m"),
        check("licence filter by default", "filter_by_properties_include_any" in filters, True),
        check("size limit to service field", filters.get("max_bbox_z"), 0.3),
        check("open side sends nothing", "min_bbox_z" in filters, False),
        check("no licence filter on request", agent.search_filters(licensed=False), {}),
        check("facts", agent.fact_lines(dict(card, mass=0.019, extras={"author": "Palatial Platforms"}),
                                        {client.LICENSE_PROPERTY: "CC-BY-4.0"}),
              ["caption: White lily flower with leafy green stem", "license: CC-BY-4.0", "mass: 0.019 kg",
               "author: Palatial Platforms", "file: D00305.usd"]),
        check("job line", agent.job_text("a.usd", ("downloading", "3/9 files")), "a.usd: downloading (3/9 files)"),
        check("find output", found, "1 of 1 results\n1. White lily flower (D00305) | 11.6 x 11.1 x 19.2 cm | 2.1 MB | on disk"),
        check("fetch of a cached asset", fetched, "D00305.usd: already on disk"),
        check("status after fetch", status, "D00305.usd: ready"),
        check("unknown index explains itself", missing, True),
    ]
    print("%d/%d passed" % (sum(results), len(results)))
    return all(results)


def _raises(call):
    try:
        call()
    except IndexError:
        return True
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
