"""Gera o HTML (capítulos 00 e 12) para impressão em PDF."""
import re
import sys
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).parent))
from tour import html as tour_html  # noqa: E402  (mesma pasta deste script)

repo = Path(sys.argv[1])
out = Path(sys.argv[2])
docs = repo / "docs" / "architecture"
logo = (repo / "frontend" / "public" / "logo.svg").read_text(encoding="utf-8")

CHAPTER_NAMES = {
    "00": "capítulo 00", "01": "capítulo 01", "02": "capítulo 02", "03": "capítulo 03", "04": "capítulo 04",
    "05": "capítulo 05", "06": "capítulo 06", "07": "capítulo 07", "08": "capítulo 08", "09": "capítulo 09",
    "10": "capítulo 10", "11": "capítulo 11", "12": "capítulo 12", "13": "capítulo 13", "14": "capítulo 14",
}


def prepare(md: str) -> str:
    # links para outros capítulos viram texto (o PDF tem só os caps. 00 e 12)
    md = re.sub(r"\*\*\[([^\]]+)\]\((\d\d)-[^)]+\.md\)\*\*", r"**\1**", md)
    md = re.sub(r"\[([^\]]+)\]\((\d\d)-[^)]+\.md\)", r"\1", md)
    # blocos mermaid viram <div class="mermaid">
    md = re.sub(r"```mermaid\n(.*?)```", lambda m: f'<div class="mermaid">\n{m.group(1)}</div>', md, flags=re.S)
    return md


FLOW = """<div class="flow">
  <div class="doc">Documentos do projeto<br><small>escopo, leis, manuais, artigos</small></div><div class="arrow">→</div>
  <div class="step s1"><b>1 · Entender o problema</b><small>Visão</small></div><div class="arrow">→</div>
  <div class="step s2"><b>2 · Ouvir as pessoas</b><small>Elicitação</small></div><div class="arrow">→</div>
  <div class="step s3"><b>3 · Analisar e priorizar</b><small>Análise</small></div><div class="arrow">→</div>
  <div class="step s4"><b>4 · Escrever a especificação</b><small>Especificação</small></div><div class="arrow">→</div>
  <div class="doc">DRE<br><small>documento final</small></div>
</div>
<p class="flow-note">Em cada etapa, a IA prepara uma proposta e <b>as pessoas aprovam</b> — ou pedem ajustes.</p>"""


def render(name: str) -> str:
    text = (docs / name).read_text(encoding="utf-8")
    if name.startswith("12"):
        # 12.2 trata de decisões técnicas da equipe: fora do material para a autora
        text = re.sub(r"## 12\.2 Para a equipe.*?(?=## 12\.3)", "", text, flags=re.S)
    if name.startswith("00"):
        text = re.sub(r"```mermaid\n.*?```", "@@FLOW@@", text, count=1, flags=re.S)
    text = prepare(text)
    return markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])


cap00, cap12 = render("00-visao-geral.md"), render("12-decisoes-pendentes.md")
cap00 = cap00.replace("<p>@@FLOW@@</p>", FLOW).replace("@@FLOW@@", FLOW)

html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>OpenUPExp — visão geral e decisões pendentes</title>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  @page {{ size: A4; margin: 18mm 16mm 18mm 16mm;
    @bottom-center {{ content: counter(page); }} }}
  :root {{ --ink:#1e1b4b; --muted:#5c6080; --accent:#6d4aff; --soft:#efeaff; --line:#dde0f0; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Plus Jakarta Sans", "Segoe UI", Arial, sans-serif; color: var(--ink);
    font-size: 10.5pt; line-height: 1.55; margin: 0; }}
  h1 {{ font-size: 21pt; margin: 0 0 10px; letter-spacing: -0.02em; color: var(--accent); }}
  h2 {{ font-size: 14pt; margin: 22px 0 8px; padding-bottom: 4px; border-bottom: 2px solid var(--soft);
    break-after: avoid; }}
  h3 {{ font-size: 12pt; margin: 16px 0 6px; break-after: avoid; }}
  p, li {{ orphans: 3; widows: 3; }}
  blockquote {{ margin: 10px 0; padding: 10px 14px; background: var(--soft); border-left: 4px solid var(--accent);
    border-radius: 0 8px 8px 0; }}
  blockquote p {{ margin: 4px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0 14px; font-size: 8.8pt; }}
  thead {{ display: table-header-group; }}
  tr {{ break-inside: avoid; }}
  th {{ background: #f3f1ff; text-align: left; font-weight: 700; }}
  th, td {{ border: 1px solid var(--line); padding: 5px 7px; vertical-align: top; }}
  code {{ font-family: "DejaVu Sans Mono", monospace; font-size: 8.5pt; background: #f4f5fb; padding: 0 3px;
    border-radius: 3px; word-break: break-word; }}
  .mermaid {{ text-align: center; margin: 14px 0; break-inside: avoid; }}
  td:first-child, th:first-child {{ white-space: nowrap; }}
  .flow {{ display: flex; align-items: stretch; gap: 4px; margin: 14px 0 4px; break-inside: avoid; }}
  .flow .arrow {{ align-self: center; color: var(--muted); font-size: 13pt; }}
  .flow .doc, .flow .step {{ flex: 1; border-radius: 10px; padding: 8px; font-size: 8.6pt; line-height: 1.3;
    display: flex; flex-direction: column; justify-content: center; text-align: center; }}
  .flow .doc {{ border: 1.5px dashed #b9bcd6; color: var(--muted); }}
  .flow small {{ display: block; color: var(--muted); font-size: 7.6pt; margin-top: 2px; }}
  .flow .step {{ border: 1.5px solid; }}
  .s1 {{ background: #efeaff; border-color: #7c5cff !important; }}
  .s2 {{ background: #e2edfd; border-color: #2f80ed !important; }}
  .s3 {{ background: #fdecd9; border-color: #e67a12 !important; }}
  .s4 {{ background: #dcf5e5; border-color: #16a34a !important; }}
  .flow-note {{ text-align: center; font-size: 9pt; color: var(--muted); margin: 2px 0 12px; }}
  .cover {{ height: 255mm; display: flex; flex-direction: column; justify-content: center; gap: 22px;
    page-break-after: always; padding: 0 6mm; }}
  .cover .brand {{ display: flex; align-items: center; gap: 16px; }}
  .cover .brand svg {{ width: 64px; height: 64px; }}
  .cover .name {{ font-size: 30pt; font-weight: 800; letter-spacing: -0.02em; }}
  .cover .name span {{ color: #14b8a6; }}
  .cover .title {{ font-size: 22pt; font-weight: 800; line-height: 1.2; }}
  .cover .sub {{ font-size: 12pt; color: var(--muted); max-width: 150mm; }}
  .cover .box {{ border: 1px solid var(--line); border-radius: 12px; padding: 14px 18px; font-size: 10pt;
    background: #fafaff; max-width: 150mm; }}
  .cover .box b {{ color: var(--accent); }}
  .cover .meta {{ font-size: 9pt; color: var(--muted); }}
  .chapter {{ page-break-before: always; }}
  .shot {{ margin: 10px 0 18px; break-inside: avoid; }}
  .shot img {{ width: 100%; border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 2px 8px rgba(30,27,75,.08); }}
  .shot figcaption {{ font-weight: 800; font-size: 11pt; margin-bottom: 6px; }}
  .shot .num {{ color: var(--accent); margin-right: 4px; }}
  .shot p {{ margin: 6px 0 0; font-size: 9.6pt; }}
  .shot .theory {{ font-size: 8.8pt; color: var(--muted); border-left: 3px solid #14b8a6; padding-left: 8px; }}
  .toc li {{ margin: 4px 0; }}
</style></head><body>
<section class="cover">
  <div class="brand">{logo}<div class="name">OpenUP<span>Exp</span></div></div>
  <div class="title">A plataforma em linguagem simples<br>e as decisões que dependem da autora</div>
  <div class="sub">Material preparado para a autora da teoria OpenUPExp, com a visão geral da plataforma
    e as perguntas em aberto — cada uma com a interpretação que adotamos enquanto isso.</div>
  <div class="box">
    <b>Como usar este documento</b>
    <ol class="toc">
      <li><b>Parte 1 — A plataforma em linguagem simples</b> (capítulo 00): o caminho de um projeto, o que a IA faz
        e o que as pessoas decidem.</li>
      <li><b>Parte 2 — A plataforma em imagens</b>: as telas reais, com explicações e a ligação de cada uma
        com a teoria.</li>
      <li><b>Parte 3 — Decisões pendentes</b> (capítulo 12): as perguntas para a autora. Comece pelas
        <i>"perguntas mais importantes"</i>; muitas vezes basta confirmar a interpretação adotada.</li>
    </ol>
    Os demais capítulos citados no texto fazem parte da documentação completa, no repositório da plataforma
    (<code>docs/architecture/</code>).
  </div>
  <div class="meta">Versão de 20/10/2026 · repositório OpenUPExp-LangGraph, branch <code>docs/arquitetura-plataforma</code></div>
</section>
<section class="chapter first">{cap00}</section>
{tour_html()}
<section class="chapter">{cap12}</section>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{ startOnLoad: true, theme: "base", themeVariables: {{
  primaryColor: "#efeaff", primaryBorderColor: "#6d4aff", primaryTextColor: "#1e1b4b", lineColor: "#6d4aff",
  fontFamily: "Plus Jakarta Sans, Arial, sans-serif" }} }});</script>
</body></html>"""
out.write_text(html.replace('<section class="chapter first">', '<section class="chapter-first">'), encoding="utf-8")
print("ok", out)
