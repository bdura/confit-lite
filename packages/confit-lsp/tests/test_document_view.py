from confit_lsp.descriptor import ConfigurationView

TOML = """
top-level = 3

[section]
factory = "add"
a = 9

[section.b]
factory = "subtract"
a = 0
b = 42
"""


def test_factories():
    view = ConfigurationView.from_source(TOML)
    assert view.factories == {
        ("section",): "add",
        ("section", "b"): "subtract",
    }
