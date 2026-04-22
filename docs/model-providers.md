# Model Providers

The settings UI separates model profiles by execution context so simulation and actual-trading defaults never share the same tab by accident.

## Tabs

- `Local Models / Simulation`
- `Local Models / Actual Trading`
- `Remote Models / Simulation`
- `Remote Models / Actual Trading`

## Local model families

- `gpt-oss`
- `qwen2.5`
- `qwen3`
- `llama3.1`
- `llama3.2`
- `deepseek-r1`

These are exposed as suggested Ollama-compatible model tags in the UI and can be overridden with any locally installed compatible model name.

## Remote paid providers

- `ChatGPT / OpenAI`
- `Claude / Anthropic`
- `Gemini / Google`
- `DeepSeek API`

Each remote provider has a separate `Simulation` and `Actual Trading` profile with isolated defaults, API keys, and routing choices.

## Storage and secrecy

- API keys are accepted write-only from the frontend
- Keys are encrypted before being stored in the database
- Read endpoints only return `has_secret` flags and non-secret config values

## Task routing

Each AI task can map to a preferred provider/model with a fallback chain:

- news summarization
- sentiment analysis
- event extraction
- signal explanation
- trade rationale generation
- candidate ranking
- portfolio commentary
- simulation commentary

Runs are logged in `model_runs` with latency, status, and optional usage metrics.
