
// =======================================================
// POLÍTICAS DE RETENTATIVA (RETRY POLICIES)
// =======================================================

retry_policy ConstantRetry {
  max_retries 2
  strategy {
    type constant_delay
    delay_ms 1000
  }
}

retry_policy ExponentialRetry {
  max_retries 4
  strategy {
    type exponential_backoff
    delay_ms 1500
    multiplier 2.0
  }
}

// =======================================================
// CLIENTES INDIVIDUAIS
// =======================================================

// 1. Groq - Llama 3 70B (Identificador Oficial Ativo na Groq)
client<llm> GroqLlama70B {
  provider openai-generic
  retry_policy ConstantRetry
  options {
    base_url "https://api.groq.com/openai/v1"
    model "openai/gpt-oss-20b"
    api_key env.GROQ_API_KEY
    temperature 0.0
    max_tokens 2048
  }
}

// 2. Groq - Llama 3.1 8B (Fallback rápido em caso de limite no 70B)
client<llm> GroqLlama8B {
  provider "openai-generic"
  retry_policy ConstantRetry
  options {
    base_url "https://api.groq.com/openai/v1"
    model "openai/gpt-oss-20b"
    api_key env.GROQ_API_KEY
    temperature 0.0
    max_tokens 2048
  }
}

// 3. Google Gemini Flash (Modelo Estável no Google AI Studio)
client<llm> CustomGeminiFlash {
  provider "google-ai"
  retry_policy ExponentialRetry
  options {
    model "gemini-1.5-flash"
    api_key env.GEMINI_API_KEY
  }
}

// =======================================================
// CLIENTE RESILIENTE DO BLACKBOARD (TRIPLA REDUNDÂNCIA)
// =======================================================

client<llm> ResilientBlackboardLLM {
  provider fallback
  options {
    strategy [GroqLlama70B, CustomGeminiFlash, GroqLlama8B]
  }
}


// Learn more about clients at https://docs.boundaryml.com/docs/snippets/clients/overview

// Using the new OpenAI Responses API for enhanced formatting
client<llm> CustomGPT5 {
  provider openai-responses
  options {
    model "gpt-5"
    api_key env.OPENAI_API_KEY
  }
}

client<llm> CustomGPT5Mini {
  provider openai-responses
  retry_policy Exponential
  options {
    model "gpt-5-mini"
    api_key env.OPENAI_API_KEY
  }
}

// Openai with chat completion
//client<llm> CustomGPT5Chat {
  //provider openai
  //options {
    //model "gpt-5"
    //api_key env.OPENAI_API_KEY
  //}
//}

client<llm> GroqLlama {
  provider openai-generic
  options {
    base_url "https://api.groq.com/openai/v1"
    model "openai/gpt-oss-20b"
    api_key env.GROQ_API_KEY

    reasoning_effort "low"
    max_completion_tokens 1024
  }
}

// Latest Anthropic Claude 4 models
client<llm> CustomOpus4 {
  provider anthropic
  options {
    model "claude-opus-4-1-20250805"
    api_key env.ANTHROPIC_API_KEY
  }
}

client<llm> CustomSonnet4 {
  provider anthropic
  options {
    model "claude-sonnet-4-20250514"
    api_key env.ANTHROPIC_API_KEY
  }
}

client<llm> CustomHaiku {
  provider anthropic
  retry_policy Constant
  options {
    model "claude-3-5-haiku-20241022"
    api_key env.ANTHROPIC_API_KEY
  }
}

// Example Google AI client (uncomment to use)
// client<llm> CustomGemini {
//   provider google-ai
//   options {
//     model "gemini-2.5-pro"
//     api_key env.GOOGLE_API_KEY
//   }
// }

// Example AWS Bedrock client (uncomment to use)
// client<llm> CustomBedrock {
//   provider aws-bedrock
//   options {
//     model "anthropic.claude-sonnet-4-20250514-v1:0"
//     region "us-east-1"
//     // AWS credentials are auto-detected from env vars
//   }
// }

// Example Azure OpenAI client (uncomment to use)
// client<llm> CustomAzure {
//   provider azure-openai
//   options {
//     model "gpt-5"
//     api_key env.AZURE_OPENAI_API_KEY
//     base_url "https://MY_RESOURCE_NAME.openai.azure.com/openai/deployments/MY_DEPLOYMENT_ID"
//     api_version "2024-10-01-preview"
//   }
// }

// Example Vertex AI client (uncomment to use)
// client<llm> CustomVertex {
//   provider vertex-ai
//   options {
//     model "gemini-2.5-pro"
//     location "us-central1"
//     // Uses Google Cloud Application Default Credentials
//   }
// }

// Example Ollama client for local models (uncomment to use)
// client<llm> CustomOllama {
//   provider openai-generic
//   options {
//     base_url "http://localhost:11434/v1"
//     model "llama4"
//     default_role "user" // Most local models prefer the user role
//     // No API key needed for local Ollama
//   }
// }

// https://docs.boundaryml.com/docs/snippets/clients/round-robin
client<llm> CustomFast {
  provider round-robin
  options {
    // This will alternate between the two clients
    strategy [CustomGPT5Mini, CustomHaiku]
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/fallback
client<llm> OpenaiFallback {
  provider fallback
  options {
    // This will try the clients in order until one succeeds
    strategy [CustomGPT5Mini, CustomGPT5]
  }
}

// https://docs.boundaryml.com/docs/snippets/clients/retry
retry_policy Constant {
  max_retries 3
  strategy {
    type constant_delay
    delay_ms 200
  }
}

retry_policy Exponential {
  max_retries 2
  strategy {
    type exponential_backoff
    delay_ms 300
    multiplier 1.5
    max_delay_ms 10000
  }
}

