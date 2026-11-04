# PDF para a autora da teoria

`OpenUPExp-visao-geral-e-decisoes-pendentes.pdf` reúne o capítulo 00 (a plataforma em linguagem
simples), as telas da plataforma com explicações (`tour.py` e `prints/`) e o capítulo 12
(decisões pendentes, sem a seção 12.2, que é da equipe).

Para gerar de novo depois de alterar os capítulos (precisa de Python com `markdown` e do Google Chrome):

```bash
python3 docs/architecture/pdf/gerar_pdf.py . /tmp/livia.html
google-chrome --headless=new --no-pdf-header-footer \
  --print-to-pdf=docs/architecture/pdf/OpenUPExp-visao-geral-e-decisoes-pendentes.pdf file:///tmp/livia.html
```

Os prints foram capturados em 20/10/2026; para atualizá-los, substitua os arquivos em `prints/`
mantendo os nomes.
