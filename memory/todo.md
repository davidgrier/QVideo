---
name: QVideo TODO list
description: Concrete deficiencies identified in polish assessment (2026-03-20)
type: project
---

# QVideo TODO

## High priority

~~All high-priority items resolved (2026-03-20).~~

## Medium priority

~~**Module docstrings**: All 14 lib/ modules now have module-level docstrings (2026-03-20).~~

## Low priority

### Missing Python 3.13 classifier in pyproject.toml
`requires-python = ">=3.10"` already allows 3.13, but there is no explicit
`"Programming Language :: Python :: 3.13"` classifier. Add once CI is tested
on 3.13 (add `"3.13"` to the matrix in `test.yml` first).

~~**`__all__` formatting**: All nine backends now use split-string form (2026-03-20).~~

~~**No test for lib/types.py**: Removed — a single type alias has nothing to test.~~
