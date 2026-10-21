.PHONY: help check format-diff test-all docs clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

check: ## Run static type checking on the Python code
	@uv run --group dev pyright

format-diff: ## Run ruff linting diff
	@uv run --group dev ruff format . --diff

test:-all ## Run repository tests
	@uv run --group dev python -m test.rdfoo

docs: ## Build the documentation
	@uv run --group docs zensical build --clean

clean: ## Clean documentation artifacts
	-rm -r ./docs/source/modules
	-rm -r ./docs/build