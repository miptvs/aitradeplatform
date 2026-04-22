#!/bin/sh
set -eu

export OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:11434}"

ollama serve &
ollama_pid=$!

echo "Waiting for Ollama API on ${OLLAMA_HOST}..."
until ollama list >/dev/null 2>&1; do
  sleep 2
done

if [ "${OLLAMA_PRELOAD_MODELS:-true}" = "true" ] && [ -n "${OLLAMA_MODELS:-}" ]; then
  IFS=','
  for model in $OLLAMA_MODELS; do
    trimmed_model=$(echo "$model" | xargs)
    if [ -z "$trimmed_model" ]; then
      continue
    fi

    echo "Preloading Ollama model: $trimmed_model"
    if ! ollama pull "$trimmed_model"; then
      echo "Warning: failed to pull $trimmed_model. The stack will stay up and you can retry later."
    fi
  done
fi

wait "$ollama_pid"
