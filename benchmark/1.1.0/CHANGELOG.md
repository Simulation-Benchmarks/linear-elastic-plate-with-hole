# Changelog

All notable changes to the benchmark description will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0]

### Changed
- Option `element_category` is now of proper `choices` type, no longer requiring a manual check of the options
- Renamed default option for `element_category` to `all-nodes`

### Added
- This changelog
- Option `principal-vertices` for `element_category` so the `mesh.msh` file always contains lowest order elements.

## [1.0.0]

Initial version in a dedicated subdirectory

### Added
- Semantic description of the benchmark problem
- Analytical solution of the Kirsch plate in Python
- Script for meshing the plate geometry using Gmsh + respective conda environment