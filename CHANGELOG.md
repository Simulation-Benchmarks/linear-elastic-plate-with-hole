# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-15

### Added
- FAIR4RS metadata: `CITATION.cff` (CFF 1.2.0) and `codemeta.json` (CodeMeta 2.0) including all authors and contributors.
- REUSE-compliant licensing: `LICENSES/MIT.txt`, `LICENSES/CC-BY-4.0.txt`, `LICENSES/CC0-1.0.txt`, and `REUSE.toml` for bulk license annotations.
- GitHub Actions workflow `.github/workflows/reuse.yml` that runs `reuse lint`, generates JSON and SPDX reports, and uploads them as artifacts.
- Zenodo DOI placeholder badge in `README.md`; the first release will be archived on Zenodo via the already-enabled GitHub–Zenodo integration.

### Notes
- This is the first tagged release. Source code files are released under MIT, documentation/figures under CC-BY-4.0, and data/config/generated artifacts under CC0-1.0.
- After Zenodo assigns the real DOI, replace the placeholder DOIs in `README.md`, `CITATION.cff`, and `codemeta.json`.

[Unreleased]: https://github.com/Simulation-Benchmarks/linear-elastic-plate-with-hole/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Simulation-Benchmarks/linear-elastic-plate-with-hole/releases/tag/v0.1.0
