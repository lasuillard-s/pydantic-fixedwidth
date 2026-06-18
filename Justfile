_default:
    just --list

# Install deps and tools
install:
    uv python install
    uv sync --frozen

# Update deps and tools
update:
    uv sync --upgrade
    pre-commit autoupdate

alias up := update

# =============================================================================
# Development
# =============================================================================

# Run all checks
ci: lint test

# Autoformat code
format:
    uv run ruff format .

alias fmt := format

# Run all linters
lint:
    uv run ruff check .
    uv run mypy --show-error-codes --pretty .

# Run all tests
test:
    uv run pytest

# Apply autofixes
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Build this project
build:
    uv build

# =============================================================================
# Utility
# =============================================================================

# Remove temporary files
clean:
    rm --recursive --force \
        .mypy_cache/ \
        .pytest_cache/ \
        .ruff_cache/ \
        dist/ \
        coverage.xml \
        junit.xml
    find . -path '*/__pycache__*' -delete
    find . -path "*.log*" -delete
