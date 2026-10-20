import type { Manifest, TaskExec, TaskSpec } from "../api/types";
import { taskName } from "./names";

export type ElementStatus = "completed" | "running" | "waiting_human" | "failed" | "stale";

export interface Level {
  file: string;
  label: string;
}

/** Última execução de cada elemento BPMN (tarefas ancoradas usam bpmn_anchor). */
export function latestByElement(tasks: TaskExec[]): Map<string, TaskExec> {
  const map = new Map<string, TaskExec>();
  for (const t of tasks) {
    if (!t.bpmn_element_id) continue;
    const prev = map.get(t.bpmn_element_id);
    if (!prev || prev.inicio <= t.inicio) map.set(t.bpmn_element_id, t);
  }
  return map;
}

function statusOf(t: TaskExec | undefined): ElementStatus | undefined {
  if (!t) return undefined;
  if (t.status === "completed") return "completed";
  if (t.status === "waiting_human") return "waiting_human";
  if (t.status === "failed") return "failed";
  return "running";
}

function aggregate(statuses: (ElementStatus | undefined)[], total: number): ElementStatus | undefined {
  const s = statuses.filter(Boolean) as ElementStatus[];
  if (!s.length) return undefined;
  if (s.includes("failed")) return "failed";
  if (s.includes("waiting_human")) return "waiting_human";
  if (s.includes("running")) return "running";
  if (s.length === total && s.every((x) => x === "completed")) return "completed";
  return "running";
}

function taskElement(t: TaskSpec): string | null {
  return t.bpmn_element ?? t.bpmn_anchor;
}

/** Status de cada elemento do arquivo BPMN exibido, agregando subprocessos e fases. */
export function statusesForFile(file: string, manifest: Manifest, tasks: TaskExec[]): Map<string, ElementStatus> {
  const latest = latestByElement(tasks);
  const out = new Map<string, ElementStatus>();
  const ofTasks = (ts: TaskSpec[]) => {
    const els = ts.map(taskElement).filter(Boolean) as string[];
    return aggregate(els.map((e) => statusOf(latest.get(e))), els.length);
  };
  if (file === manifest.root.bpmn_file) {
    for (const ph of manifest.phases) {
      const st = ofTasks(ph.subprocesses.flatMap((sp) => sp.tasks));
      if (st) out.set(ph.bpmn_element, st);
    }
  }
  for (const ph of manifest.phases) {
    if (ph.bpmn_file === file) {
      for (const sp of ph.subprocesses) {
        const st = ofTasks(sp.tasks);
        if (st) out.set(sp.bpmn_element, st);
      }
    }
    for (const sp of ph.subprocesses) {
      if (sp.bpmn_file === file) {
        for (const t of sp.tasks) {
          const el = t.bpmn_element;
          const st = el ? statusOf(latest.get(el)) : undefined;
          if (el && st) out.set(el, st);
        }
      }
    }
  }
  return out;
}

/** Para onde leva o clique num call activity (fase → arquivo da fase; subprocesso → arquivo do subprocesso). */
export function drillTarget(elementId: string, manifest: Manifest): Level | null {
  for (const ph of manifest.phases) {
    if (ph.bpmn_element === elementId) return { file: ph.bpmn_file, label: `${ph.id} ${taskName(ph.id, ph.name)}` };
    for (const sp of ph.subprocesses) {
      if (sp.bpmn_element === elementId) return { file: sp.bpmn_file, label: `${sp.id} ${taskName(sp.id, sp.name)}` };
    }
  }
  return null;
}

export function taskByElement(elementId: string, manifest: Manifest): TaskSpec | null {
  for (const ph of manifest.phases)
    for (const sp of ph.subprocesses)
      for (const t of sp.tasks) if (t.bpmn_element === elementId) return t;
  return null;
}

export function iterationsByElement(tasks: TaskExec[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const t of tasks) if (t.bpmn_element_id) m.set(t.bpmn_element_id, Math.max(m.get(t.bpmn_element_id) ?? 0, t.iteracao));
  return m;
}
