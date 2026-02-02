#!/bin/bash
set -e

echo "🚀 Deploy Evolvian"

echo "🔄 Reindexando todos los clientes..."
python -m api.internal.reindex_client

echo "🧠 Iniciando API..."
uvicorn main:app --host 0.0.0.0 --port $PORT
