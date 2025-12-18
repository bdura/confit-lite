from confit_lsp.descriptor import ConfigurationView

TOML = """
top-level = 3

[section]
factory = "add"
a = 9

[section.b]
factory = "add"
a = 0
b = 42
"""


def test_factories():
    view = ConfigurationView.from_source(TOML)
    assert {e.path for e in view.factories} == {
        ("section", "factory"),
        ("section", "b", "factory"),
    }
