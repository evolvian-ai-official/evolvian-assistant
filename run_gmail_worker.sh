#!/bin/bash
echo "🚀 Iniciando Gmail Poll Worker para Evolvian AI..."
while true; do
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
  echo "🕐 [$TIMESTAMP] Ejecutando revisión de Gmail..."
  RESPONSE=$(curl -s -X POST https://evolvian-assistant.onrender.com/gmail_poll/check -H "Content-Type: application/json")
  if echo "$RESPONSE" | grep -q '"status":"ok"'; then
    echo "✅ [$TIMESTAMP] Poll exitoso → $RESPONSE"
  else
    echo "⚠️ [$TIMESTAMP] Error en poll → $RESPONSE"
    echo "⏳ [$TIMESTAMP] Reintentando en 60 segundos..."
    sleep 60
    RETRY_RESPONSE=$(curl -s -X POST https://evolvian-assistant.onrender.com/gmail_poll/check -H "Content-Type: application/json")
    if echo "$RETRY_RESPONSE" | grep -q '"status":"ok"'; then
      echo "✅ [$TIMESTAMP] Segundo intento exitoso."
    else
      echo "❌ [$TIMESTAMP] Segundo intento fallido → $RETRY_RESPONSE"
    fi
  fi
  echo "💤 [$TIMESTAMP] Esperando 5 minutos para la siguiente ejecución..."
  sleep 300
done
