# Task Completion Checklist

After completing any code changes, always run through these steps:

1. **Format code:**
   ```bash
   uvx ruff format src/ tests/
   ```

2. **Lint check:**
   ```bash
   uvx ruff check src/ tests/
   ```

3. **Run tests:**
   ```bash
   uv run pytest -x -q
   ```
   All 392+ tests must pass.

4. **Verify no unintended changes:**
   ```bash
   git diff
   ```

## Key rules
- Tools must always return strings, never raise exceptions
- New validators go in `validators.py`, new constants in `constants.py`
- New tools get their own file in `src/fbi_crime_data_mcp/tools/` and must be imported in `server.py`
- New tools must be added to the appropriate caching tier in `server.py` (90d / 30d / 1d) — or explicitly excluded
- Tests for tools go in `tests/test_tools/` (one file per tool), core module tests in `tests/`
- Date format varies: `mm-yyyy` for most crime data, `yyyy` for employment/trends/LEOKA/LESDC/UoF
