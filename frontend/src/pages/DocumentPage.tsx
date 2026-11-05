/** Documento enviado ao projeto, aberto a partir de uma citação: rola até o trecho e o destaca. */
import { useEffect, useMemo, useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { SourceDocumentText } from "../api/types";
import Icon from "../components/Icon";
import { ErrorBox, Hint, Loading } from "../components/ui";

// Procura o trecho ignorando maiúsculas, espaços e quebras de linha; devolve [início, fim] no texto original.
function findQuote(text: string, quote: string): [number, number] | null {
  const words = quote.replace(/^\s*["“]|["”]\s*$/g, "").split(/\s+/).filter(Boolean)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) return null;
  for (let n = words.length; n >= Math.min(words.length, 6); n--) {  // se não achar inteiro, tenta o começo
    const m = new RegExp(words.slice(0, n).join("\\s+"), "i").exec(text);
    if (m) return [m.index, m.index + m[0].length];
  }
  return null;
}

export default function DocumentPage() {
  const { documentId } = useParams();
  const [params] = useSearchParams();
  const trecho = params.get("trecho") ?? "";
  const doc = useQuery({ queryKey: ["source-document", documentId],
    queryFn: () => api.get<SourceDocumentText>(`/source-documents/${documentId}`) });
  const mark = useRef<HTMLElement>(null);
  const found = useMemo(() => (doc.data && trecho ? findQuote(doc.data.texto, trecho) : null), [doc.data, trecho]);
  useEffect(() => { mark.current?.scrollIntoView({ block: "center" }); }, [found]);

  if (doc.isLoading) return <Loading what="Abrindo o documento" />;
  if (!doc.data) return <ErrorBox error={doc.error} />;
  const { texto, arquivo, project_id } = doc.data;
  return (
    <div className="stack">
      <div className="row small"><Link to={`/projetos/${project_id}`}><Icon name="arrowLeft" size={14} /> Voltar ao projeto</Link></div>
      <h1 style={{ margin: 0 }}><Icon name="file" /> {arquivo}</h1>
      {trecho && (found
        ? <Hint icon="search">O trecho citado está destacado em amarelo.</Hint>
        : <Hint icon="alert" tone="warn">O trecho citado não foi achado igual neste documento: a IA pode ter mudado as
            palavras. Procure no texto: <em>"{trecho}"</em></Hint>)}
      <pre className="doc-text">{found
        ? <>{texto.slice(0, found[0])}<mark ref={mark}>{texto.slice(found[0], found[1])}</mark>{texto.slice(found[1])}</>
        : texto}</pre>
    </div>
  );
}
