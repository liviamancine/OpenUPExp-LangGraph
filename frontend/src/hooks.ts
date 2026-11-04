import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { eventsUrl } from "./api/client";

/** Escuta os eventos da execução (SSE) e invalida as consultas afetadas. */
export function useRunEvents(runId: string | undefined, onEvent?: (tipo: string, dados: Record<string, unknown>) => void) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!runId) return;
    const es = new EventSource(eventsUrl(runId));
    const handler = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as { tipo: string; dados: Record<string, unknown> };
        onEvent?.(data.tipo, data.dados);
      } catch { /* evento malformado */ }
      qc.invalidateQueries({ queryKey: ["run", runId] });
      qc.invalidateQueries({ queryKey: ["tasks", runId] });
      qc.invalidateQueries({ queryKey: ["artifacts", runId] });
      qc.invalidateQueries({ queryKey: ["inbox"] });
    };
    const tipos = ["run_queued", "run_running", "task_started", "task_completed", "task_failed", "artifact_version",
      "hitl_requested", "hitl_decided", "decision_applied", "run_completed", "run_failed", "export_created",
      "artifact_edited"];
    tipos.forEach((t) => es.addEventListener(t, handler as EventListener));
    return () => es.close();
  }, [runId, qc, onEvent]);
}
