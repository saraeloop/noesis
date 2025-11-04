.PHONY: setup-dev docs-install validate-exports pr-contracts release-contracts

UV ?= uv
PYTHON ?= python3
PNPM ?= pnpm

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
