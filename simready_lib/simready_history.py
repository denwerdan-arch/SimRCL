"""When each SimReady package was added to the library, from the commit history of its Hugging Face dataset.

The search service no longer sends file dates, but every dataset behind it is a public Hugging Face repository
and most packages arrive in a commit that names them ("deploy cleaning_dishSoap_a01 from ...", "deploy
box_flat_a16 into ...", "Add SimReady package: tagine", "Add qualified SimReady packages: D00593"). The first such commit is the date the package was added, the last one when it was updated.
Packages that arrived in an unnamed batch get the date the plugin first saw them in the catalog instead; the
packages already there when tracking started have no date at all (never shown as new).

The catalog's package list carries each dataset's current revision, so a dataset's history is fetched again
only when that revision changes, and then only down to the newest commit already known: after the first run
(about 1 MB) a day costs a request or two. Standard library only; the network calls are injectable for tests.
"""
import datetime
import json
import os
import re
import urllib.request

HF_API = "https://huggingface.co/api/datasets/%s/commits/main?limit=%d&p=%d"
PAGE_LIMIT = 1000
CACHE_NAME = "history_v2.json"  # v2: "deploy ... into" and "Add qualified ... packages" titles
NEW_DAYS = 14
TIMEOUT_SECONDS = 30
USER_AGENT = "c4d-simready-importer/history"
TITLE_PATTERNS = (re.compile(r"^deploy (\S+) (?:from|into) "),
                  re.compile(r"^Add (?:qualified )?SimReady packages?: ([\w.-]+(?:\s*,\s*[\w.-]+)*)\s*$"))
_KEY = re.compile(r"/datasets/(?P<repo>[^/]+/[^/]+)/blob/(?P<revision>[0-9a-f]{7,40})/(?P<package>[^/]+)/")


# ---------------------------------------------------------------- pure helpers (tested in the sandbox)

def packages_of(title):
    """Packages a commit title names (one, or a comma separated list); empty for commits that name none."""
    for pattern in TITLE_PATTERNS:
        match = pattern.match(title or "")
        if match:
            return [name.strip() for name in match.group(1).split(",")]
    return []


def merge_dates(packages, commits):
    """packages ({name: [added, updated]}) extended by commits; earliest date wins as added, latest as updated."""
    merged = {name: list(dates) for name, dates in packages.items()}
    for commit in commits:
        date = commit.get("date")
        for name in packages_of(commit.get("title")) if date else ():
            added, updated = merged.get(name, (date, date))
            merged[name] = [min(added, date), max(updated, date)]
    return merged


def catalog_index(keys):
    """({repo: revision}, {(repo, package)}) from the catalog's package keys (blob URLs)."""
    revisions, packages = {}, set()
    for key in keys:
        match = _KEY.search(key)
        if match:
            revisions[match.group("repo")] = match.group("revision")
            packages.add((match.group("repo"), match.group("package")))
    return revisions, packages


def stale_repos(revisions, cache):
    """Repositories whose catalog revision differs from the one their cached history was read at."""
    known = cache.get("repos", {})
    return sorted(repo for repo, revision in revisions.items() if known.get(repo, {}).get("revision") != revision)


def note_first_seen(cache, packages, today):
    """Record today for packages new to the catalog; on the first run every package present is only marked known."""
    seen = dict(cache.get("first_seen", {}))
    baseline = not seen and not cache.get("baseline")
    for repo, package in packages:
        seen.setdefault("%s/%s" % (repo, package), None if baseline else today)
    return dict(cache, first_seen=seen, baseline=cache.get("baseline") or today)


def added_dates(cache, packages):
    """{(repo, package): 'YYYY-MM-DD...'} for packages of the catalog: the history's added date, else first seen.

    Repositories also hold packages the search does not list (staging, retired, failed checks); they are left out
    so the newest packages are ones the window can actually show.
    """
    seen = cache.get("first_seen", {})
    histories = {repo: entry.get("packages", {}) for repo, entry in cache.get("repos", {}).items()}
    dates = {}
    for repo, package in packages:
        dated = histories.get(repo, {}).get(package)
        date = dated[0] if dated else seen.get("%s/%s" % (repo, package))
        if date:
            dates[(repo, package)] = date
    return dates


def is_new(added, today, days=NEW_DAYS):
    """True when added (an ISO date or timestamp) lies within days before today (a datetime.date)."""
    if not added:
        return False
    try:
        day = datetime.date.fromisoformat(added[:10])
    except ValueError:
        return False
    return 0 <= (today - day).days < days


# ---------------------------------------------------------------- network and cache

def _get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def fetch_commits(repo, stop_at=None, get=_get_json):
    """Commits of repo, newest first, down to (not including) stop_at; the whole history without it."""
    commits, page = [], 0
    while True:
        batch = get(HF_API % (repo, PAGE_LIMIT, page))
        for commit in batch:
            if commit.get("id") == stop_at:
                return commits
            commits.append(commit)
        if len(batch) < PAGE_LIMIT:
            return commits
        page += 1


def update_repo(entry, repo, revision, get=_get_json):
    """entry ({'revision', 'head', 'packages'}) brought up to the repository's current history."""
    commits = fetch_commits(repo, entry.get("head"), get)
    head = commits[0]["id"] if commits else entry.get("head")
    return {"revision": revision, "head": head, "packages": merge_dates(entry.get("packages", {}), commits)}


def load_cache(cache_dir):
    try:
        with open(os.path.join(cache_dir, CACHE_NAME), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_cache(cache_dir, cache):
    """Write through a temporary file so a crash never leaves half a cache behind."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, CACHE_NAME)
    with open(path + ".part", "w", encoding="utf-8") as handle:
        json.dump(cache, handle)
    os.replace(path + ".part", path)


def refresh(cache_dir, catalog_keys, today=None, get=_get_json):
    """Bring the cached history up to the catalog and return {(repo, package): added date}; blocking.

    A repository that cannot be read keeps its previous history (and is tried again next time).
    """
    today = today or datetime.date.today().isoformat()
    revisions, packages = catalog_index(catalog_keys)
    cache = note_first_seen(load_cache(cache_dir), packages, today)
    repos = dict(cache.get("repos", {}))
    for repo in stale_repos(revisions, cache):
        try:
            repos[repo] = update_repo(repos.get(repo, {}), repo, revisions[repo], get)
        except (OSError, ValueError, KeyError):
            continue
    cache = dict(cache, repos=repos)
    save_cache(cache_dir, cache)
    return added_dates(cache, packages)
