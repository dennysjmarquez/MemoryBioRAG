#!/usr/bin/env bash
# estado_cerebro.sh — Estado del respaldo de la corteza (SOLO LECTURA).
#
# POR QUÉ EXISTE: Dennys quiere saber en 1 segundo si la memoria
# (memory_biorag.db) tiene cambios sin commitear o si falta subirla a
# GitHub. Este script no modifica nada — solo responde 4 preguntas.
#
# Uso:  ./estado_cerebro.sh
set -euo pipefail
cd "$(dirname "$0")"

DB="MemoryBioRAG_Data/memory_biorag.db"

echo "=== ESTADO DE LA CORTEZA ==="

# 1. ¿Hay cambios sin commitear desde el último commit?
if git diff --quiet HEAD -- "$DB" 2>/dev/null; then
    echo "1. Commiteada al día: SIN cambios pendientes"
else
    echo "1. ⚠️  MODIFICADA y SIN commitear (el último commit no la refleja)"
fi

# 2. Último commit que tocó la corteza
echo "2. Último commit de la corteza: $(git log -1 --format='%h %ad %s' --date=short -- "$DB")"

# 3. ¿El commit local está en GitHub? (HEAD local vs origin/master)
if git rev-parse -q --verify origin/master >/dev/null 2>&1; then
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/master)
    if [ "$LOCAL" = "$REMOTE" ]; then
        echo "3. Push: TODO subido a GitHub (HEAD == origin/master)"
    else
        N=$(git rev-list --count origin/master..HEAD 2>/dev/null || echo "?")
        echo "3. ⚠️  Push PENDIENTE: $N commit(s) local(es) sin subir — push desde GitKraken"
    fi
else
    echo "3. (sin remoto origin/master configurado)"
fi

# 4. Respaldos locales de la DB en backups/
NBAK=$(ls -1 MemoryBioRAG_Data/backups/*.db 2>/dev/null | wc -l)
echo "4. Respaldos locales en MemoryBioRAG_Data/backups/: $NBAK archivo(s)"
echo "============================"
