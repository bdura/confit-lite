# Confit-lite

A bare-minimum registry implementation, with a built-in LSP!

## Quickstart

### The basics

Install the package:

```shell
pip install git+https://github.com/bdura/confit-lite
```

You probably want to add the LSP to your development dependencies:

```shell
pip install git+https://github.com/bdura/confit-lite[lsp]
```

### Using the LSP

See the README for [`confit-lsp`].

### Adding factories

This is all well and good, but you should be able to add your own factories -
otherwise, what's the point.

To allow this, `confit-lite` leverages [entrypoints]. In your project,
you should add a `project.entry-points.confit` table that points to
a module that imports all registered functions.

See the [example]:

```toml
[project.entry-points.confit]
factories = "confit_factories.factories"
```

You can also declare each factory individually, but... why would you?
Just in case:

```toml
[project.entry-points.confit]
add = "confit_factories.factories:add"
```

## Roadmap

In its current state, this project provides a basic, naive, flaky and inefficient
LSP implementation that only works in simple cases.

The goal is to make it gradually better.

- [x] Inlay hints
- [x] Hover
- [x] Missing key detections
- [x] Value type-checking with Pydantic
- [x] Go to definition
- [x] [VSCode extension]
- [x] Handle references (type-checking & go to definition)
- [x] Basic support for complex objects
      (nested factories - check that factories generate correct type)
- [x] Configurable registry using `[tool.confit.registries]`
- [ ] Handle registered classes
- [ ] Handle compatible types, not just identical types
- [ ] Allow LSP-aware lazy defaults
- [ ] Serialization capabilities
- [ ] Highlight references
- [ ] "Efficient" reading/parsing strategy
- [ ] Serious parser

<!-- Local links -->

[VSCode extension]: ./clients/vscode/
[example]: ./packages/confit-factories/pyproject.toml
[`confit-lsp`]: ./packages/confit-lsp/README.md

<!-- Global links -->

[entrypoints]: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata
