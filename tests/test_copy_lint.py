from src.tools.copy_lint import lint_no_em_dash, lint_dict_strings


def test_lint_replaces_em_dash():
    assert lint_no_em_dash("foo — bar") == "foo, bar"
    assert lint_no_em_dash("a – b") == "a, b"
