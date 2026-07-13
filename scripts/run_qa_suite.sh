#!/bin/bash
set -e

# Get workspace directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PARENT_DIR="$(dirname "$DIR")"

echo "================================================================================"
echo "Initializing BioRAG QA Evaluation Suite..."
echo "================================================================================"

# Check if we should regenerate the baseline
if [ "$1" == "--generate-baseline" ] || [ "$1" == "generate" ]; then
    echo "Regenerating QA baseline..."
    python3 "$PARENT_DIR/scripts/generar_casos_qa.py"
    # Copy generated cases to baseline
    cp "$PARENT_DIR/scripts/casos_qa.jsonl" "$PARENT_DIR/scripts/casos_qa_baseline_v1.jsonl"
    echo "Baseline regenerated and stored."
fi

# 2. Run evaluation (default uses casos_qa_baseline_v1.jsonl)
python3 "$PARENT_DIR/scripts/evaluar_qa.py"

echo "================================================================================"
echo "BioRAG QA Evaluation Suite finished."
echo "================================================================================"
