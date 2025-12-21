# `confit-lsp`, an LSP for `confit-lite`

For the LSP to work, you will need two things:

1. Install this project in your virtual environment
2. Configure your IDE

## Installing the LSP

You just need to add `confit-lsp` to your development dependencies:

```shell
uv add --group dev git+ssh://git@github.com/bdura/confit-lite.git[lsp]
```

## IDE configuration

### VSCode

We provide a [VSCode extension].

Then, install the extension from the `VSIX` artifact.
From the VSCode Extensions panel: Settings > Install from VSIX.

### Neovim

```lua
vim.lsp.config['confit-lsp'] = {
  cmd = { 'confit-lsp' },
  filetypes = { 'toml' },
  root_markers = { { 'pyproject.toml' }, '.git' },
}
```

You will need to run `vim.lsp.enable('confit-lsp')` to start the language server.

### Helix

```toml
[language-server.confit-lsp]
command = "confit-lsp"

[[language]]
name = "confit"
scope = "text.toml"
injection-regex = "toml"
file-types = ["toml"]
comment-tokens = "#"
indent = { tab-width = 2, unit = "  " }
language-servers = ["confit-lsp"]
```

[VSCode extension]: https://marketplace.visualstudio.com/items?itemName=bdura.confit-lsp
