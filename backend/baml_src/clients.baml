// Perfis nomeados por papel (docs/architecture/08-contratos-baml.md §8.5).
// Experimentos sobrescrevem o cliente em tempo de execução (ClientRegistry),
// sem fallback, para não trocar de modelo silenciosamente.

retry_policy PadraoRetry {
  max_retries 2
  strategy {
    type exponential_backoff
    delay_ms 500
    multiplier 2
    max_delay_ms 8000
  }
}

client<llm> GroqGptOss120b {
  provider openai-generic
  retry_policy PadraoRetry
  options {
    base_url "https://api.groq.com/openai/v1"
    api_key env.GROQ_API_KEY
    model "openai/gpt-oss-120b"
    temperature 0.0
  }
}

client<llm> GroqGptOss20b {
  provider openai-generic
  retry_policy PadraoRetry
  options {
    base_url "https://api.groq.com/openai/v1"
    api_key env.GROQ_API_KEY
    model "openai/gpt-oss-20b"
    temperature 0.0
  }
}

client<llm> OpenAIGpt5Mini {
  provider openai-responses
  retry_policy PadraoRetry
  options {
    api_key env.OPENAI_API_KEY
    model "gpt-5-mini"
  }
}

client<llm> AnthropicSonnet {
  provider anthropic
  retry_policy PadraoRetry
  options {
    api_key env.ANTHROPIC_API_KEY
    model "claude-sonnet-5-5"
    max_tokens 8192
    temperature 0.0
  }
}

client<llm> GeminiFlash {
  provider google-ai
  retry_policy PadraoRetry
  options {
    api_key env.GEMINI_API_KEY
    model "gemini-3.5-flash"
    generationConfig { temperature 0.0 }
  }
}

// Produção: fallback entre famílias diferentes de modelo.
client<llm> OpenUPExpDefault {
  provider fallback
  options {
    strategy [GroqGptOss120b, OpenAIGpt5Mini, AnthropicSonnet]
  }
}

// Tarefas simples (consultas, digests).
client<llm> OpenUPExpCheap {
  provider fallback
  options {
    strategy [GroqGptOss20b, GeminiFlash]
  }
}
