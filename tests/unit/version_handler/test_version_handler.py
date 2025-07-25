import pytest
from frameworks.VersionHandler import VersionHandler

class TestVersionHandler:
    def test_valid_version_parsing(self):
        """Test correct parsing of a valid version string."""
        v = VersionHandler("1.2.3.4")
        assert v.major == "1.2"
        assert v.minor == 3
        assert v.build == 4
        assert v.without_build == "1.2.3"
        assert str(v) == "1.2.3.4"
        assert repr(v) == "VersionHandler(version='1.2.3.4')"

    def test_invalid_version_raises(self):
        """Test that invalid version string raises ValueError."""
        with pytest.raises(ValueError):
            VersionHandler("1.2.3")
        with pytest.raises(ValueError):
            VersionHandler("a.b.c.d")
        with pytest.raises(ValueError):
            VersionHandler("")

    def test_comparisons(self):
        """Test comparison operators between VersionHandler instances."""
        v1 = VersionHandler("1.2.3.4")
        v2 = VersionHandler("1.2.3.5")
        v3 = VersionHandler("1.2.4.0")
        v4 = VersionHandler("2.0.0.0")
        assert v1 < v2
        assert v2 < v3
        assert v3 < v4
        assert v1 <= v2
        assert v2 <= v2
        assert v4 > v3
        assert v4 >= v3
        assert v1 == VersionHandler("1.2.3.4")
        assert v1 != v2

    def test_hash(self):
        """Test that VersionHandler is hashable and can be used in sets/dicts."""
        v1 = VersionHandler("1.2.3.4")
        v2 = VersionHandler("1.2.3.4")
        v3 = VersionHandler("1.2.3.5")
        s = {v1, v2, v3}
        assert len(s) == 2
        d = {v1: "foo", v3: "bar"}
        assert d[v2] == "foo"
        assert d[v3] == "bar"
