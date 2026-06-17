# ❤️‍🔥 Contributing to this project

Thank you for your interest in contributing to **pydantic-fixedwidth**!

## 🐛 Reporting issues

Please report issues in our [GitHub repository](https://github.com/lasuillard-s/pydantic-fixedwidth/issues). Before submitting an issue, please search for existing issues to avoid duplicates.

## 🏗️ Project overview

This project provides a small Python library (`pydantic_fixedwidth`) for parsing and serializing fixed-width data with Pydantic models.

### 🛠️ Tech stack

This project uses the following tech stack:

- [Python](https://www.python.org) 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency management, Python installation, and packaging
- [Ruff](https://docs.astral.sh/ruff/) to lint and format Python code, and [Mypy](https://mypy-lang.org) for type checking
- [pytest](https://docs.pytest.org/en/latest) with coverage reporting for testing

### 📂 Key directory structure

- `pydantic_fixedwidth/`: The project's source code
- `tests/`: Project tests
- `flake.nix`: Flake configuration for the development environment
- `Justfile`: Commands for development
- `pyproject.toml`: Project metadata, dependencies, linting, type checking, and test configuration

## 🔧 Set up the development environment

For development, the following tools are required:

### ❄️ Tools managed via Nix Flakes

This repository uses [Nix Flakes](https://nix.dev/concepts/flakes.html) to manage tools. The following tools are automatically installed (requires `nix`):

- `pre-commit`
- `just`
- `uv`
- `pipx`

Run `nix develop` to start the development environment, then run `just install` to install dependencies.

If you prefer to use a [Dev Container](https://containers.dev), a configuration file ([devcontainer.json](./.devcontainer.example/devcontainer.json)) is provided with Nix support and Python tooling extensions.

## ✅ Verifying changes

Before pushing your code, verify that your changes adhere to the project's coding standards. Run `just ci` to execute all necessary formatters, linters, type checks, and tests. Alternatively, let the `pre-commit` hooks handle this automatically.

## ✨ Submitting changes

Please submit pull requests on GitHub. Before opening a PR, ensure your changes pass all checks by running `just ci`.

## 🚀 Release process

This project's package is published to PyPI through GitHub Releases:

1. Prepare a release via the [Prepare Release](https://github.com/lasuillard-s/pydantic-fixedwidth/actions/workflows/prepare-release.yaml) workflow using a tag that starts with `v`.
2. Review and merge the preparation PR.
3. Create and publish a new release in GitHub Releases.
4. The [release workflow](./.github/workflows/release.yaml) will attach the built distributions to the GitHub Release and publish them to PyPI.
