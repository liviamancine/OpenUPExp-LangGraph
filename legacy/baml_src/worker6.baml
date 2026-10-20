class AdditionalExplainabilityRequirement {
  categoria string
  requisito string
  justificativa string
}

function DevelopAdditionalExplainabilityRequirements(
  artefatos_visao: string,
  consulta_worker5: string,
  conhecimento_recuperado: string
) -> AdditionalExplainabilityRequirement[] {

  client ResilientBlackboardLLM

  prompt #"
Você elabora requisitos adicionais relacionados à explicabilidade
para a Vision do sistema.

### Entradas do Blackboard
{{ artefatos_visao }}

### Consulta do Worker 5
{{ consulta_worker5 }}

### Conhecimento recuperado pelo RAG
{{ conhecimento_recuperado }}

### Responsabilidade
Elaborar requisitos complementares para a seção:

5. Requisitos Adicionais relacionados à Explicabilidade

5.1 Padrões, Normas e Regulamentos Aplicáveis
5.2 Plataforma, Hardware e Desempenho
5.3 Qualidade das Explicações
5.4 Restrições de Design, Dependências e Assunções
5.5 Documentação e Suporte
5.6 Priorização dos Outros Requisitos

### Regras
1. Cada requisito deve estar relacionado à explicabilidade e ser
   complementar às necessidades identificadas nos artefatos da Visão.

2. Exija suporte direto no conhecimento recuperado pelo RAG e
   relação explícita com as necessidades da Visão.

3. A consulta do Worker 5 orienta a interpretação, mas não constitui
   evidência por si só.

4. Não invente normas, obrigações legais, restrições, tecnologias,
   métricas ou valores.

5. Não transforme automaticamente contexto, exemplos ou recomendações
   em obrigações do sistema.

6. Não detalhe implementação técnica nem atribua prioridade ou
   planned release.

7. Classifique cada requisito em uma única categoria. Não crie
   requisitos apenas para preencher categorias.

8. A justificativa deve identificar a necessidade da Visão e a
   informação específica recuperada que sustenta o requisito.

9. Se não houver evidência suficiente, descarte o requisito.
   Retorne uma lista vazia quando nenhum requisito for fundamentado.

   
### Validação obrigatória das evidências

10. Antes de elaborar um requisito, identifique a passagem
    exata do conhecimento recuperado que sustenta a obrigação.

11. Verifique se a passagem se aplica ao domínio do sistema
    e à situação descrita no requisito. Não generalize uma
    obrigação legal prevista para um contexto específico.

12. Diferencie explicitamente:
    a) obrigação legal ou normativa;
    b) recomendação técnica ou acadêmica;
    c) proposta de requisito derivada de uma necessidade
       identificada na Visão.

13. Não afirme que uma lei exige determinada funcionalidade
    quando o trecho recuperado não estabelece essa obrigação.

14. Não infira requisitos de explicabilidade, auditabilidade
    ou acesso a explicações apenas da existência de uma
    autoridade reguladora ou de princípios gerais de proteção
    de dados.

15. Para cada requisito aceito, registre a fonte, a página,
    o trecho relevante e a relação com uma necessidade
    identificada na Visão. Se algum desses elementos não
    puder ser identificado, descarte o requisito.

16. Não crie requisitos apenas para preencher categorias.
    Se nenhuma evidência suficiente for encontrada, retorne
    uma lista vazia.


### Saída
Retorne somente objetos contendo:
- categoria
- requisito
- justificativa

{{ ctx.output_format }}
"#
}