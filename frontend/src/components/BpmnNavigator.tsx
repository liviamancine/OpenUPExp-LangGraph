import { useEffect, useRef, useState } from "react";
import NavigatedViewer from "bpmn-js/lib/NavigatedViewer";
import "bpmn-js/dist/assets/diagram-js.css";
import "bpmn-js/dist/assets/bpmn-js.css";
import { api } from "../api/client";
import type { Manifest, TaskExec } from "../api/types";
import { translateBpmn } from "../bpmn/names";
import { drillTarget, iterationsByElement, statusesForFile, taskByElement, type Level } from "../bpmn/status";

interface Props {
  manifest: Manifest;
  tasks: TaskExec[];
  selected: string | null;
  onSelect: (elementId: string) => void;
}

const STATUS_CLASSES = ["st-completed", "st-running", "st-waiting_human", "st-failed", "st-stale", "st-selected", "st-clickable"];

export default function BpmnNavigator({ manifest, tasks, selected, onSelect }: Props) {
  const host = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const viewer = useRef<any>(null);
  const [stack, setStack] = useState<Level[]>([{ file: manifest.root.bpmn_file, label: "Processo completo" }]);
  const [error, setError] = useState<string | null>(null);
  const [loadedFile, setLoadedFile] = useState<string | null>(null);
  const current = stack[stack.length - 1];

  // instancia o viewer uma vez
  useEffect(() => {
    viewer.current = new NavigatedViewer({ container: host.current });
    return () => viewer.current?.destroy();
  }, []);

  // carrega o arquivo BPMN do nível atual
  useEffect(() => {
    let cancelled = false;
    setError(null);
    api.get<string>(`/process/bpmn/${encodeURIComponent(current.file)}`)
      .then(async (xml) => {
        if (cancelled) return;
        const result = await viewer.current.importXML(translateBpmn(xml, manifest));
        if (result.warnings?.length) console.warn("BPMN", current.file, result.warnings);
        viewer.current.get("canvas").zoom("fit-viewport", "auto");
        setLoadedFile(current.file);
      })
      .catch((e) => setError(`Não foi possível exibir ${current.file}: ${e.message ?? e}`));
    return () => { cancelled = true; };
  }, [current.file, manifest]);

  // clique: call activity → desce um nível; tarefa/gateway → seleciona
  useEffect(() => {
    const bus = viewer.current?.get("eventBus");
    if (!bus) return;
    const onClick = (e: { element: { id: string; type: string } }) => {
      const target = drillTarget(e.element.id, manifest);
      if (target) setStack((s) => [...s, target]);
      else if (taskByElement(e.element.id, manifest)) onSelect(e.element.id);
    };
    bus.on("element.click", onClick);
    return () => bus.off("element.click", onClick);
  }, [manifest, onSelect]);

  // marcadores de status e badges de iteração
  useEffect(() => {
    if (!viewer.current || loadedFile !== current.file) return;
    const canvas = viewer.current.get("canvas");
    const registry = viewer.current.get("elementRegistry");
    const overlays = viewer.current.get("overlays");
    overlays.clear();
    const statuses = statusesForFile(current.file, manifest, tasks);
    const iterations = iterationsByElement(tasks);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    registry.getAll().forEach((el: any) => {
      STATUS_CLASSES.forEach((c) => canvas.removeMarker(el.id, c));
      const st = statuses.get(el.id);
      if (st) canvas.addMarker(el.id, `st-${st}`);
      if (drillTarget(el.id, manifest) || taskByElement(el.id, manifest)) canvas.addMarker(el.id, "st-clickable");
      if (el.id === selected) canvas.addMarker(el.id, "st-selected");
      const it = iterations.get(el.id);
      if (it && it > 1) {
        overlays.add(el.id, { position: { top: -10, right: 10 }, html: `<span class="bpmn-badge">iteração ${it}</span>` });
      }
    });
  }, [tasks, manifest, selected, loadedFile, current.file]);

  return (
    <div className="stack">
      <div className="breadcrumb">
        {stack.map((lvl, i) => (
          <span key={lvl.file} className="row" style={{ gap: 6 }}>
            {i > 0 && <span className="muted">›</span>}
            <button disabled={i === stack.length - 1} onClick={() => setStack(stack.slice(0, i + 1))}>{lvl.label}</button>
          </span>
        ))}
        <span className="muted small grow" style={{ textAlign: "right" }}>
          Clique em um bloco para entrar nele; em uma tarefa para ver o que aconteceu.
        </span>
      </div>
      {error && <div className="alert err">{error}</div>}
      <div className="bpmn-host" ref={host} />
      <div className="row small muted">
        <span className="badge completed">feito</span><span className="badge running">em andamento</span>
        <span className="badge waiting_human">aguardando pessoas</span><span className="badge failed">com erro</span>
        <span className="tiny">Diagramas originais do processo OpenUPExp</span>
      </div>
    </div>
  );
}
