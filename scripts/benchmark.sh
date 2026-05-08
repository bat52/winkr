#!/usr/bin/env bash
# Benchmark wrapper: compare token efficiency of Cline+Aider vs Cline-only.
#
# Usage:
#   ./scripts/benchmark.sh [--task "description"] [--iterations N] [--output-dir DIR]
#
# Creates a temporary workspace, validates dependencies, runs the Python
# benchmark module, and prints the report.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
TASK="Extract the greet() and farewell() functions from main.py into a new file utils.py"
ITERATIONS=1
OUTPUT_DIR="./benchmark_results"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --task)
            TASK="$2"
            shift 2
            ;;
        --iterations)
            ITERATIONS="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--task TASK] [--iterations N] [--output-dir DIR]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
echo "=== winkr benchmark ==="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found" >&2
    exit 1
fi
echo "  [OK] python3 found"

# Check npx (for Cline)
if ! command -v npx &>/dev/null; then
    echo "ERROR: npx not found (required for Cline)" >&2
    exit 1
fi
echo "  [OK] npx found"

# Check winkr
if ! command -v winkr &>/dev/null; then
    echo "WARNING: winkr not found in PATH — Flow A (Cline+Aider) may fail" >&2
else
    echo "  [OK] winkr found"
fi

# Check git
if ! command -v git &>/dev/null; then
    echo "ERROR: git not found" >&2
    exit 1
fi
echo "  [OK] git found"

echo ""

# ---------------------------------------------------------------------------
# Run benchmark
# ---------------------------------------------------------------------------
echo "Task:       $TASK"
echo "Iterations: $ITERATIONS"
echo "Output:     $OUTPUT_DIR"
echo ""

# Ensure the benchmark module is importable
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

python3 -m llm_agent_toolkit.benchmark \
    --task "$TASK" \
    --iterations "$ITERATIONS" \
    --output-dir "$OUTPUT_DIR"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "=== Benchmark complete ==="
    echo "Reports saved to: $OUTPUT_DIR"
else
    echo "=== Benchmark failed (exit code $EXIT_CODE) ===" >&2
fi

exit $EXIT_CODE
