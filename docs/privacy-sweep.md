# Privacy Sweep

Last reviewed: 2026-04-20

## Scope

The repo was checked for:

- personal names and usernames
- absolute local filesystem paths
- email addresses
- tokens or secret-like strings
- private service names
- machine-specific metadata embedded in shipped `.3mf` artifacts

## What Was Checked

- top-level docs and examples
- `src/` and `tests/`
- tracked generated scripts and example outputs
- internal text metadata inside tracked `.3mf` files
- both commits currently in public-facing Git history

## Findings

- No personal email addresses were found in tracked source, docs, or examples.
- No local absolute paths tied to the actual workstation were found in tracked repo files.
- No token-like strings or obvious secrets were found.
- The tracked `.3mf` files contain Bambu printer/profile metadata, which is expected for printer-facing project files.
- The only absolute path found in source is a synthetic test fixture path in `tests/test_bambu_mcp.py`:
  - `/Users/test/.hammerspoon/init.lua`
  - This is a fake path used for test coverage, not a real local path.
- Git history was checked across both existing commits before changing repository visibility.

## Remediation Applied

- Removed an accidental duplicate generated script: `generated/esp32_dev_board_enclosure 2.py`
- Removed obsolete intermediate `.3mf` artifacts that were not the recommended review outputs
- Reframed the README away from machine-diary language and toward reviewable product scope
- Moved public-release concerns into an explicit checklist document

## Remaining Privacy Considerations Before Public Release

- Re-run the same sweep after any new `.3mf` sample is added.
- Keep machine-specific runtime notes in implementation docs, not in user-facing marketing copy.
- Review whether all tracked generated artifacts are still worth shipping once public positioning is finalized.
