import type { ReactNode } from "react";
import { createContext, useContext, useMemo } from "react";

import { useSetShinyInput } from "@/shiny";

/**
 * Every event input is mounted exactly once, at the app root: shinyreact
 * re-sends an input's value when a hook for it mounts, which would replay the
 * last action whenever a component remounted.
 */
export type EventId = "analyse" | "select_sample" | "upload" | "open_case" | "export_report";
type Send = (id: EventId, payload: Record<string, unknown>) => void;

const Ctx = createContext<Send>(() => {});

function useEvent(id: EventId) {
  return useSetShinyInput<Record<string, unknown> | null>(id, null, { debounceMs: 0, priority: "event" });
}

export function EventsProvider({ children }: { children: ReactNode }) {
  const setters = {
    analyse: useEvent("analyse"),
    select_sample: useEvent("select_sample"),
    upload: useEvent("upload"),
    open_case: useEvent("open_case"),
    export_report: useEvent("export_report"),
  };
  const send = useMemo<Send>(
    () => (id, payload) => setters[id]({ ...payload, nonce: Date.now() + Math.random() }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    Object.values(setters),
  );
  return <Ctx.Provider value={send}>{children}</Ctx.Provider>;
}

export const useSend = () => useContext(Ctx);
