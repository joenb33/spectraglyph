from spectraglyph.utils.github_release import compare_versions


def test_compare_versions():
    assert compare_versions("0.2.2", "0.2.3") == -1
    assert compare_versions("0.2.3", "0.2.2") == 1
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("0.10.0", "0.9.0") == 1
