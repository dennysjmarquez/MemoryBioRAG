#!/usr/bin/env bash
# subir_cerebro.sh — Sube la corteza (memory_biorag.db) al repositorio.
#
# POR QUÉ EXISTE: la corteza SQLite es la memoria viva compartida de los
# agentes y este repo la trackea a propósito como respaldo. Este script
# commitea SOLO ese archivo, sin tocar nada más del repo.
#
# HISTORIAL DE FLAGS: hasta 2026-10-02 la DB tenía skip-worktree puesta
# (protegía contra pisadas durante el split-brain). Dennys la removió para
# que `git status` muestre los cambios de la DB (visibilidad total).
# Si alguna vez hay que re-protegerla:
#   git update-index --skip-worktree MemoryBioRAG_Data/memory_biorag.db
#
# Uso:  ./subir_cerebro.sh  "mensaje de commit opcional"
set -euo pipefail
cd "$(dirname "$0")"

DB="MemoryBioRAG_Data/memory_biorag.db"
MSG="${1:-chore(memory): subir corteza SQLite canónica al repo}"

echo "1/3 Preparando la corteza (solo ese archivo)..."
git add "$DB"

echo "2/3 Commiteando..."
if git diff --cached --quiet -- "$DB"; then
    echo "   Sin cambios: el repo ya tiene exactamente la corteza actual."
else
    git commit -m "$MSG" -- "$DB"
    echo "   Subido: $(git log --oneline -1)"
fi

echo "3/3 Verificación..."
echo "Flag:  $(git ls-files -v -- "$DB")   (H = normal, sin skip-worktree)"
echo "SHA:   $(sha256sum "$DB" | cut -d' ' -f1)"
echo "Listo — la corteza quedó commiteada."
echo "Recuerda: el push a GitHub se hace desde GitKraken (manual)."
