import subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {"LICENSE", "build_corpus.py", "tests/test_stranger.py"}
DASHES = ("—", "–")


def test_no_em_or_en_dash_in_tracked_text():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    bad = []
    for f in files:
        if f in SKIP or f.startswith("corpus/"):
            continue
        text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
        if any(d in text for d in DASHES):
            bad.append(f)
    assert not bad, bad


def test_pytest_has_no_deprecation_warnings():
    r = subprocess.run([__import__("sys").executable, "-m", "pytest", "-q", "-W", "error", "--ignore=tests/test_stranger.py", "tests"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-800:]


def test_readme_says_cobc_is_optional_and_skips():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Without `cobc`" in text and "skipped" in text


def test_suite_passes_with_cobc_absent(tmp_path):
    import os, sys
    py = os.path.realpath(sys.executable)
    (tmp_path / "python3").symlink_to(py)
    env = dict(os.environ, PATH=str(tmp_path))
    r = subprocess.run([str(tmp_path / "python3"), "-m", "pytest", "-q", "-k", "cobol or cobc or agree",
                        "tests/test_redteam.py", "tests/test_pic_truncation.py"],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "skipped" in r.stdout, r.stdout[-800:]
