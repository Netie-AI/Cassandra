import pathlib

EM_DASH = "\u2014"
TARGETS = list(pathlib.Path("web/static").glob("*.html")) + list(pathlib.Path("web/static").glob("*.js"))


def test_no_em_dash_in_static():
    violations = []
    for f in TARGETS:
        text = f.read_text(encoding="utf-8", errors="ignore")
        if EM_DASH in text:
            violations.append(f.name)
    assert not violations, f"Em-dash found in: {violations}"
