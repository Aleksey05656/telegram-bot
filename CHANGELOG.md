## [2025-09-20] - E4: Recommendation engine invariants
### Added
- Normalised `RecommendationEngine.generate_prediction` payload and predictor facade in `core/services`.
- Dependency-injected worker with Redis locks and queue status reporting.
- Test suites covering probability invariants and worker behaviour.

### Changed
- README and docs updated with ML invariants and new architecture notes.

### Fixed
- Removed invalid awaits and global clients in prediction worker, resolving audit findings.
