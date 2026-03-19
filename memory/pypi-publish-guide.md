---
name: PyPI publish guide
description: Step-by-step process used to publish QVideo v3.0.0 to PyPI via GitHub Actions
type: project
---

# Publishing to PyPI via GitHub Actions

## 1. Prepare pyproject.toml metadata

```toml
[project]
name = "YourPackage"
version = "1.0.0"
description = "..."
readme = "README.md"
license = { text = "GPL-3.0-or-later" }   # use SPDX text form, NOT { file = "..." }
requires-python = ">=3.10"
authors = [{ name = "Your Name", email = "you@example.com" }]
keywords = [...]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "Programming Language :: Python :: 3",
    ...
]
dependencies = [...]

[project.urls]
Homepage = "https://github.com/you/yourpackage"
Repository = "https://github.com/you/yourpackage"
"Bug Tracker" = "https://github.com/you/yourpackage/issues"
```

> **Important:** Use `license = { text = "SPDX-identifier" }`, not `license = { file = "..." }`.
> The file form causes setuptools to emit a `License-File` metadata field
> (Metadata-Version 2.4) that some PyPI tooling rejects.

## 2. Create the GitHub Actions workflow

`.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  build:
    name: Build distribution
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install build tools
        run: pip install --upgrade pip build

      - name: Build sdist and wheel
        run: python -m build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Download build artifacts
        uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

## 3. Create a PyPI API token

1. Log in to pypi.org
2. Account settings → API tokens → **Add API token**
3. Name: `<repo>-github-actions`
4. Scope: **Entire account** (required for first upload; switch to project-scoped after first publish)
5. Copy the token (shown only once)

## 4. Add the token as a GitHub secret

1. GitHub repo → Settings → Secrets and variables → Actions
2. **New repository secret**
   - Name: `PYPI_API_TOKEN`
   - Value: paste the token

## 5. Tag and push to trigger the workflow

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow runs on any tag matching `v*`. Check progress at:
`https://github.com/<owner>/<repo>/actions`

## 6. After first successful publish

Replace the account-scoped token with a project-scoped one:
1. pypi.org → Manage project → Settings → API tokens → **Add token**
2. Scope: the specific project
3. Copy the new token and update the `PYPI_API_TOKEN` secret in GitHub with it
4. Delete the old account-scoped token:
   - pypi.org → Account settings → API tokens
   - Find the account-scoped token
   - Click Options → Delete → confirm
