# Roadmap

Local web app (site/ frontend + Python extraction scripts) to browse
geotagged photos on a map and pull originals by location. Matured through
UX/bugfix passes, then the same uv/pre-commit/ruff/mypy-strict hardening as
the rest of the personal-tools repos, with the npm install folded into
`make install`.

## Near-term

- End-to-end test for the extraction pipeline (see TODO.md), not just the pure-logic unit test.
- Clarify re-run semantics for `make extract-photos` against an already-processed directory.
