# FastAPI Backend

This project uses [uv](https://docs.astral.sh/uv/) for Python package and environment management.

### UV Workflow

**Set up environment** (after cloning or pulling latest):
```bash
uv sync
```

**Add a new dependency:**
```bash
uv add <package-name>
# Dev-only dependency
uv add --dev <package-name>
```
> `uv add` automatically updates both `pyproject.toml` and `uv.lock`, and installs the package into `.venv`.

**Update lock file** (after manually editing `pyproject.toml`):
```bash
uv lock          # re-resolve and update uv.lock
uv lock --upgrade  # upgrade all packages to latest allowed versions
```

**Pin Python version** (updates `.python-version`):
```bash
uv python pin 3.9
```

### Start Server
```bash
uv run fastapi run app/main.py --port 8000 --host 0.0.0.0
```

### Docker

- build
```bash
docker-compose up
```
- uninstall
```bash
docker-compose down
```
- paste your original dicom cases into ~/primary.
- update your manifest.xlsx file.