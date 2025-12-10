# confit-lsp

Minimal LSP for [Confit].

You can find a pre-compiled version [here][vsix].

Note that you need to install the LSP itself separately:

```shell
pip install git+https://github.com/bdura/confit-lite[lsp]
```

See the [`confit-lite`] docs for more information.

## Manual installation

You'll need to install Node and [`vsce`] to compile the extension using:

```shell
cd clients/vscode
npm i
vsce package
```

Then, install the extension from the `VSIX` artifact. From the VSCode
Extensions panel: Settings > Install from VSIX.

Open `config.toml`, you should get diagnostics as long as you have `confit-lsp`
installed on your Python environment.

Note that the LSP requires `confit-lsp` to be installed:

```shell
uv sync --all-extras
```

[Confit]: https://aphp.github.io/confit/latest/
[`vsce`]: https://code.visualstudio.com/api/working-with-extensions/publishing-extension
[`confit-lite`]: https://github.com/bdura/confit-lite
[vsix]: https://github.com/bdura/confit-lite/tree/artifacts
