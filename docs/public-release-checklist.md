# Public Release Checklist

This is the first pass of the work needed before the repo should be made public.

## Positioning

- Narrow the public positioning to `structured CAD workflow + fit checks + experimental Bambu handoff`.
- Add a short repository description and tagline that do not overclaim arbitrary CAD generation.
- Decide whether the public audience is CAD builders, LLM tooling developers, or Bambu automation users first.

## Documentation

- Keep the top-level README short and product-oriented.
- Move host-specific runtime notes into implementation docs rather than the main README.
- Add a support matrix for:
  - core CAD workflow
  - fit checker
  - Bambu seed-template path
  - Bambu GUI automation
  - Bambu CLI export
- Add a license before public release.
- Add contribution guidance if outside contributions are expected.

## Examples And Artifacts

- Reduce `generated/` to a deliberate demo set rather than a working-directory snapshot.
- Keep only one recommended multicolor `.3mf` example for Bambu review.
- Decide whether SVG previews still belong in the repo or should be dropped.
- Consider moving review artifacts into a dedicated `examples/output/` or `demo/` layout.

## Platform And Runtime Assumptions

- Document that the current Bambu automation path is macOS-first.
- Make the Hammerspoon dependency optional and clearly experimental.
- Clarify which parts of the Bambu path are verified on A1 + AMS lite only.
- Add explicit notes about Studio version sensitivity and serializer drift risk.

## Code And Testing

- Stabilize the broader pytest run so it does not hang intermittently.
- Add CI for the non-CAD test suite.
- Separate pure schema/patch tests from host-dependent Bambu automation tests.
- Decide whether generated artifacts belong under test coverage or only as manual fixtures.

## Privacy And Repository Hygiene

- Re-run the privacy sweep before public release, including `.3mf` metadata inspection.
- Check that no local usernames, absolute paths, or machine-specific repo URLs remain in tracked files.
- Remove accidental duplicate generated files and other review-only clutter.
- Confirm no secrets, access tokens, or private service names have entered docs or fixtures.

## Product Decisions Still Open

- Whether Bambu support stays inside this repo or moves into a separate plugin/tooling repo.
- Whether the public API should stabilize around the brief schema, the Bambu handoff spec, or both.
- Whether printer-native project generation should remain explicitly experimental after first release.
