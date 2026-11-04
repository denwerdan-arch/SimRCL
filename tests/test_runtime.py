"""Sandbox checks of the USD runtime repair logic with a fake subprocess runner."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simready_lib"))

import simready_runtime as rt  # noqa: E402


def check(label, got, want):
    print("%s %s: %r%s" % ("ok " if got == want else "BAD", label, got, "" if got == want else " (want %r)" % (want,)))
    return got == want


def fake_runner(state):
    """_run stand-in: the probe passes only after an install; records the commands it saw."""
    def run(command, timeout):
        state["calls"].append(command)
        if "--version" in command:
            return types.SimpleNamespace(returncode=0, stdout="Python 3.14.0", stderr="")
        if "install" in command:
            state["installed"] = True
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")
        ok = state["installed"]
        return types.SimpleNamespace(returncode=0 if ok else 1, stdout="", stderr="" if ok else "no Usd.Stage")
    return run


def main():
    state = {"calls": [], "installed": False}
    rt._run, rt._WORKING = fake_runner(state), set()
    python = rt.ensure_runtime("base")
    installs = [c for c in state["calls"] if "install" in c]
    probes_before = len([c for c in state["calls"] if rt.PROBE in c])
    rt.ensure_runtime("base")
    probes_after = len([c for c in state["calls"] if rt.PROBE in c])
    results = [
        check("broken copy is reinstalled", len(installs), 1),
        check("reinstall forces over the old files", "--force-reinstall" in installs[0], True),
        check("python found", python, ["py", "-3"]),
        check("working runtime is probed once per session", probes_after - probes_before, 0),
    ]
    print(all(results))


main()
