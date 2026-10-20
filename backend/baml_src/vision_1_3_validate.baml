// Subprocesso 1.3 Validate Explainability Vision
// A revisão (1.3.1) e a decisão do gateway são humanas. Aqui fica apenas o digest
// gerado na consolidação (1.3.2), usado como contexto auxiliar das fases seguintes.

class PhaseDigest {
  resumo string @description("Resumo compacto (até ~600 palavras) da fase aprovada")
  ids_cobertos string[] @description("Todos os IDs de itens mencionados no resumo")
}

class DigestInput {
  documento string @description("Documento aprovado da fase, em Markdown")
  ids_obrigatorios string[] @description("IDs que DEVEM ser mencionados no resumo")
}

function BuildPhaseDigest(entrada: DigestInput, contexto: ContextItem[]) -> PhaseDigest {
  client OpenUPExpCheap
  prompt #"
    {{ _.role("system") }}
    Você resume um documento aprovado do processo OpenUPExp para servir de contexto auxiliar às
    fases seguintes. O resumo NÃO substitui o documento: os dados completos continuam disponíveis.

    REGRAS
    - Mencione explicitamente, por ID, TODOS os itens listados em ids_obrigatorios.
    - Não acrescente informação que não esteja no documento.
    - Preserve lacunas relevantes (o que ainda requer investigação).

    {{ _.role("user") }}
    IDS OBRIGATÓRIOS
    {{ entrada.ids_obrigatorios }}

    DOCUMENTO APROVADO
    {{ entrada.documento }}

    {{ ctx.output_format }}
  "#
}
