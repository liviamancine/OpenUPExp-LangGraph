"""Parte "A plataforma em imagens": prints das telas com explicações."""
import base64
from pathlib import Path

PRINTS = Path(__file__).parent / "prints"

# (arquivo, título, explicação, ligação com a teoria ou observação)
SHOTS = [
    ("__sec__", "Entrada e projetos", "", ""),
    ("01-entrar", "Tela de entrada",
     "A primeira tela já apresenta as quatro etapas do processo. Cada pessoa entra com o próprio e-mail; "
     "o que ela vê e pode fazer depende do seu papel no projeto.", ""),
    ("02-projetos", "Meus projetos",
     "Lista os projetos da pessoa. O painel no alto resume o caminho de qualquer projeto: em cada etapa, a IA "
     "prepara uma proposta e a equipe revisa e aprova.", ""),
    ("03-projeto-etapas", "Projeto: a jornada das quatro etapas",
     "Cada cartão é uma etapa do OpenUPExp, com sua cor e situação: <i>concluída e aprovada</i>, <i>aguardando "
     "uma decisão</i> ou <i>pronta para começar</i>. O botão <b>Começar</b> usa automaticamente o resultado "
     "aprovado da etapa anterior. Ao lado, a lista <i>Antes de começar</i> mostra o que falta preparar.",
     "Teoria: as quatro macroatividades do processo (Visão → Elicitação → Análise → Especificação)."),
    ("04-escolha-modelo", "Projeto: como a IA vai trabalhar",
     "Antes de começar uma etapa, escolhe-se qual modelo de IA vai executá-la. Os modelos prontos para uso "
     "aparecem primeiro; os sem chave ficam apagados. O <b>modo de teste</b> percorre o processo com respostas "
     "simuladas, sem IA e sem custo — útil para conhecer a plataforma.", ""),
    ("05-documentos", "Projeto: documentos",
     "Aqui se envia o escopo (obrigatório) e o material de consulta: leis, manuais, artigos e entrevistas. "
     "Os documentos são preparados para busca, divididos por artigo e seção, para que a IA possa citá-los com precisão.",
     "Teoria: corresponde à <i>Explainability Reference Base</i> do BPMN."),
    ("__sec__", "Acompanhar e decidir", "", ""),
    ("06-pendencias", "O que precisa de mim",
     "Reúne os momentos em que a IA parou e espera por pessoas: <b>revisar e aprovar</b>, <b>dar opinião</b> "
     "(consenso) ou <b>enviar material</b> das conversas.",
     "Teoria: os pontos de decisão humana do BPMN (gateways e <i>Reach Consensus</i>)."),
    ("07-etapa-andamento", "Uma etapa em andamento",
     "A faixa no alto diz o que está acontecendo e qual é a próxima ação. O <b>mapa do processo</b> é o próprio "
     "diagrama BPMN da teoria, colorido pelo andamento e com os textos em português; à direita, o <b>passo a "
     "passo</b> mostra cada tarefa e quem a executou (IA, automático ou pessoas).",
     "Teoria: os arquivos BPMN são exibidos como estão; só os textos são traduzidos na tela."),
    ("08-revisao", "Revisar e aprovar",
     "Três passos explicam o que fazer. À esquerda, as partes do documento (com a contagem de pontos em aberto); "
     "no centro, o documento como vai ficar; à direita, a decisão: <b>aprovar</b> ou <b>pedir para a IA refazer</b> "
     "uma parte, com um comentário que orienta a nova tentativa.",
     "Teoria: gateway <i>Explainability Vision approved?</i> e a anotação \"revisitar 1.1 ou 1.2\"."),
    ("09-revisao-parte", "Uma parte aberta, com citações e verificação automática",
     "Cada item pode ser comentado ou editado. Requisitos que vêm de leis e manuais mostram a <b>citação "
     "conferida</b> (o trecho foi encontrado literalmente na fonte, com arquivo e página). À esquerda, a "
     "<b>verificação automática</b> lista regras objetivas; ela ajuda, mas não substitui a leitura humana.", ""),
    ("10-material", "Enviar o material das conversas (Etapa 2)",
     "A etapa de Elicitação pausa aqui. À esquerda, o <b>roteiro de conversas</b> que a IA propôs para cada "
     "stakeholder; à direita, o envio das transcrições ou anotações. Também é possível seguir sem material, "
     "justificando.",
     "Teoria: tarefa 2.2.1 <i>Obtain Explainability Needs</i>; o formato do plano é provisório (A-14)."),
    ("11-consenso", "Opinião da equipe (consenso)",
     "Cada participante registra se <b>concorda</b>, <b>concorda com observações</b> ou <b>discorda</b>, com "
     "comentários. O responsável encerra a rodada ou pede ajustes; se alguém discordar, encerrar exige "
     "justificativa, que fica registrada no documento.",
     "Teoria: tarefas <i>Reach Consensus</i>; quem participa e a regra de fechamento são provisórios (A-13)."),
    ("__sec__", "O documento final", "", ""),
    ("12-historias", "Documento final: histórias de usuário",
     "Ao fim da Etapa 4, o documento reúne todas as partes. Cada requisito vira uma ou mais histórias no formato "
     "<b>Como / Quero / Para</b>, com critérios <b>Dado / Quando / Então</b> e as características da explicação.",
     "Teoria: formatos recomendados em <i>especificar-requisitos.md</i>; templates ainda pendentes (A-14, A-21)."),
    ("13-matriz", "Documento final: matriz de rastreabilidade",
     "A matriz liga cada história ao requisito, ao requisito refinado, ao stakeholder, às necessidades, à origem "
     "na Etapa 2, aos critérios, às características e à prioridade. Ela é <b>calculada</b> a partir dos vínculos "
     "registrados ao longo do processo, e não escrita pela IA.", ""),
    ("__sec__", "Pesquisa: modelos de IA e laboratório", "", ""),
    ("14-lab-resumo", "Laboratório: resumo de uma comparação",
     "O laboratório refaz uma mesma tarefa com modelos e estratégias de contexto diferentes, usando <b>exatamente "
     "o mesmo material de entrada</b>. O resumo mostra, por combinação, o acerto em relação ao gabarito, os itens, "
     "os pontos em aberto, os tokens e o tempo. <i>Neste exemplo o gabarito é de teste, não de especialistas.</i>", ""),
    ("15-lab-comparacao", "Laboratório: comparação detalhada",
     "Uma coluna por tentativa, com a execução original como referência: material entregue, acerto (precisão e "
     "cobertura), formato aceito, itens produzidos, lacunas, citações conferidas, chamadas, custo e tempo. Os "
     "dados podem ser baixados em CSV para análise estatística.", ""),
    ("16-modelos", "Administração: modelos de IA",
     "O administrador cadastra modelos, testa a conexão e a compatibilidade com os formatos da plataforma e "
     "escolhe o padrão. O <b>modelo local</b> (Qwen3 4B) é a referência para comparação: protegido, opcional e "
     "desligado por padrão, porque sem placa de vídeo é lento e pesado.", ""),
]


def html() -> str:
    parts = ['<section class="chapter"><h1>A plataforma em imagens</h1>'
             '<blockquote><p>Telas reais da plataforma, capturadas em 20/10/2026 no projeto de estudo de caso '
             '(INPI). Algumas execuções estão em <b>modo de teste</b> (respostas simuladas), usado aqui só para '
             'mostrar os momentos de decisão em aberto.</p></blockquote>']
    n = 0
    for name, title, text, theory in SHOTS:
        if name == "__sec__":
            parts.append(f"<h2>{title}</h2>")
            continue
        n += 1
        data = base64.b64encode((PRINTS / f"{name}.jpg").read_bytes()).decode()
        note = f'<p class="theory">{theory}</p>' if theory else ""
        parts.append(f'<figure class="shot"><figcaption><span class="num">Figura {n}</span> {title}</figcaption>'
                     f'<img src="data:image/jpeg;base64,{data}" alt="{title}"><p>{text}</p>{note}</figure>')
    parts.append("</section>")
    return "\n".join(parts)
