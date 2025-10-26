# AIGlucose
AI Glucose project

## Configuration

- `LLM_PROVIDER`: Choose between `lmstudio`, `openai`, `huggingface`, or `gemini`.
- `LLM_MODEL`: Model identifier understood by the chosen provider. Defaults to the LM Studio model when not supplied.
- `LLM_EXTRA_OPTIONS`: Optional JSON object with provider-specific generation parameters passed through to the request context.
- `GEMINI_API_KEY`: When using the Gemini provider, supply your Google API key.
- `GEMINI_GENERATION_CONFIG`: Optional JSON object merged into the default generation configuration for Gemini.
- `GEMINI_SAFETY_SETTINGS`: Optional JSON (list or dict) of safety settings forwarded to Gemini.
- `OPENAI_API_KEY`: Optional API key when using the OpenAI provider.
- `HUGGINGFACE_ENDPOINT_URL` / `HUGGINGFACE_API_TOKEN`: Credentials for Hugging Face Inference endpoints.
- `LMSTUDIO_BASE_URL`: Override the LM Studio REST endpoint.

Ensure any additional provider specific parameters are supplied through `LLM_EXTRA_OPTIONS` in JSON format if needed.
