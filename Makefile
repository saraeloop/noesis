.PHONY: setup-dev docs-install validate-exports pr-contracts release-contracts ci-smoke prerelease

UV ?= uv
PYTHON ?= python3
PNPM ?= pnpm
NOESIS_CI_ROOT ?= ./.noesis-ci
NOESIS_CI_RUNS ?= $(NOESIS_CI_ROOT)/smoke-runs
NOESIS_CI_LEARN ?= $(NOESIS_CI_ROOT)/state

# Install Python dependencies using uv (matches CI release job)
setup-dev:
	$(UV) sync

# Install docs dependencies with pnpm inside docs/ (matches CI release job)
docs-install:
	cd docs && $(PNPM) install --frozen-lockfile

# Run the export/doc contract validator (shared by PR + release)
validate-exports:
	$(PYTHON) scripts/validate_exports.py --strict

# PR parity: run dry-run pre-release suite to surface drift quickly
pr-contracts: validate-exports
	$(PYTHON) scripts/pre_release.py --check-all

# Release parity: executes the full pre-release suite (requires setup-dev + docs-install first)
release-contracts: setup-dev docs-install validate-exports
	$(PYTHON) scripts/pre_release.py --check-all --execute

# CI-style smoke: run pre-release dry run with CI-scoped artifacts.
ci-smoke:
	NOESIS_RUNS_DIR=$(NOESIS_CI_RUNS) NOESIS_LEARN_HOME=$(NOESIS_CI_LEARN) \
		$(PYTHON) scripts/pre_release.py --check-all

# CI-style prerelease: execute full suite with CI-scoped artifacts.
prerelease: setup-dev docs-install validate-exports
	NOESIS_RUNS_DIR=$(NOESIS_CI_RUNS) NOESIS_LEARN_HOME=$(NOESIS_CI_LEARN) \
		$(PYTHON) scripts/pre_release.py --check-all --execute
