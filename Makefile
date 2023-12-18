# -- linting -------------------------------------------------------------------

.PHONY: ruff
ruff:
	ruff check .

.PHONY: unbehead
unbehead:
	unbehead --check

.PHONY: lint
lint: ruff unbehead
