# Task: Python 3.12 Compatibility

## Context

The `takopi-ralph` package currently requires Python 3.14+, but the server runs Python 3.12.3. After code analysis, the Python 3.14 requirement appears unnecessarily strict - the codebase uses no Python 3.14-specific features.

### Current Environment
- **Server Python**: 3.12.3
- **Package requires**: Python >=3.14
- **takopi installed**: v0.14.0.dev0 (requires >=0.13)

### Code Analysis Findings

After reviewing all source files, **no Python 3.14-specific syntax or features** were found:

1. **No structural pattern matching** (`match`/`case` statements)
   - The `match` variable names found are regex `.search()` results, not pattern matching
2. **No Python 3.14 typing features** (TypeAlias with new syntax, TypeVar defaults)
3. **No ExceptionGroup/TaskGroup** (3.11+)
4. **All files use** `from __future__ import annotations` for forward compatibility
5. **ruff config** already targets `py312`: `target-version = "py312"`

### Dependencies Compatibility

| Dependency | Required | Py3.12 Support |
|------------|----------|----------------|
| takopi | >=0.13 | Yes (also requires 3.14 but likely same issue) |
| pydantic | >=2.10 | Yes |
| anyio | >=4.8.0 | Yes |

## Implementation Plan

### 1. Update pyproject.toml Python Version
**File**: `pyproject.toml`

Change:
```toml
requires-python = ">=3.14"
```
To:
```toml
requires-python = ">=3.12"
```

Also update classifiers:
```toml
classifiers = [
    ...
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    ...
]
```

### 2. Regenerate Lock File
After updating pyproject.toml:
```bash
cd /root/dev/takopi-ralph
rm uv.lock
uv lock
```

### 3. Verify takopi Compatibility
The installed `takopi v0.14.0.dev0` also requires Python 3.14. Need to check if banteg's takopi actually needs 3.14 or if this is the same false constraint.

Options:
- If takopi works on 3.12: proceed with installation
- If takopi genuinely needs 3.14: need to either upgrade Python or patch takopi

### 4. Install and Test
```bash
cd /root/dev/takopi-ralph
uv pip install -e .
# or
uv tool install -e .
```

### 5. Run Test Suite
```bash
cd /root/dev/takopi-ralph
uv run pytest
```

## Risks

1. **takopi dependency**: If takopi genuinely requires Python 3.14, this change alone won't work
2. **Hidden 3.14 features**: May have missed something in code review
3. **Upstream updates**: Future takopi-ralph updates may introduce actual 3.14 requirements

## Success Criteria

- [ ] Package installs on Python 3.12.3
- [ ] All tests pass
- [ ] `/ralph help` command works via takopi
- [ ] No import errors when loading the plugin

## Reasoning

The Python 3.14 requirement appears to be a forward-looking constraint rather than a technical necessity. The `ruff` config targeting `py312` and the use of `from __future__ import annotations` throughout suggests the author intended compatibility with older Python versions but set an unnecessarily aggressive minimum version.
