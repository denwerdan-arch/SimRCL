"""Run every tests/test_*.py as its own process; exit 1 if any of them fails.

The tests are plain scripts (no pytest): each prints "ok"/"BAD" lines and ends with a summary. A test fails
when it exits non-zero, prints a BAD line or ends with "False".
"""
import glob
import os
import subprocess
import sys

TESTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests")


def failed(output, code):
    """True when a test's output or exit code reports a failure."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return code != 0 or any(line.startswith("BAD") for line in lines) or (lines and lines[-1] == "False")


def run(path):
    """(name, ok, last line) for one test script."""
    result = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr
    last = (output.strip().splitlines() or [""])[-1]
    if failed(output, result.returncode):
        print(output)
    return os.path.basename(path), not failed(output, result.returncode), last


def main():
    results = [run(path) for path in sorted(glob.glob(os.path.join(TESTS, "test_*.py")))]
    for name, ok, last in results:
        print("%s %s: %s" % ("ok " if ok else "BAD", name, last))
    return all(ok for _, ok, _ in results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
