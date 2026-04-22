from app.services.providers.openai_compatible import OpenAICompatibleProviderAdapter


class DeepSeekCompatibleProviderAdapter(OpenAICompatibleProviderAdapter):
    provider_type = "deepseek"
