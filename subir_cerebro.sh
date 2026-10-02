#!/usr/bin/env bash
# subir_cerebro.sh — Sube la corteza (memory_biorag.db) al repositorio y
# vuelve a protegerla con skip-worktree.
#
# POR QUÉ EXISTE: la DB tiene la flag skip-worktree puesta para que git nunca
# reemplace el archivo bajo los MCPs vivos (eso causó el split-brain del
# 2026-10-02). La consecuencia: git add se niega con la flag puesta.
# Este script levanta la flag, sube SOLO la corteza, y la vuelve a poner.
# Uso:  ./subir_cerebro.sh  "mensaje de commit opcional"
set -euo pipefail
cd "$(dirname "$0")"

DB="MemoryBioRAG_Data/memory_biorag.db"
MSG="${1:-chore(memory): subir corteza SQLite canónica al repo}"

echo "1/4 Levantando skip-worktree..."
git update-index --no-skip-worktree "$DB"

echo "2/4 Preparando la corteza (solo ese archivo)..."
git add "$DB"

echo "3/4 Commiteando..."
if git diff --cached --quiet -- "$DB"; then
    echo "   Sin cambios: el repo ya tiene exactamente la corteza actual."
else
    git commit -m "$MSG" -- "$DB"
    echo "   Subido: $(git log --oneline -1)"
fi

echo "4/4 Volviendo a poner skip-worktree (protección)..."
git update-index --skip-worktree "$DB"

echo "=== Verificación ==="
echo "Flag:  $(git ls-files -v -- "$DB")   (S = protegido)"
echo "SHA:   $(sha256sum "$DB" | cut -d' ' -f1)"
echo "Listo — la corteza quedó subida y protegida."
