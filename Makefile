# -- linting -------------------------------------------------------------------

.PHONY: unbehead
unbehead:
	unbehead --check

.PHONY: lint
lint: unbehead
