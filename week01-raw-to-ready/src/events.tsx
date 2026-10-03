import type { ReactNode } from "react";
import { createContext, useContext, useMemo } from "react";

import { useSetShinyInput } from "@/shiny";

/**
 * Every event input is mounted exactly once, here at the app root.
 * shinyreact re-sends an input's value when a hook for it mounts; for event
 * inputs that would replay the last action whenever a component remounts.
 */
export type EventId = "decide" | "verify" | "revert" | "upload" | "use_sample" | "export";
type Send = (id: EventId, payload: Record<string, unknown>) => void;

const EventsContext = createContext<Send>(() => {});

function useEvent(id: EventId) {
  return useSetShinyInput<Record<string, unknown> | null>(id, null, { debounceMs: 0, priority: "event" });
}

export function EventsProvider({ children }: { children: ReactNode }) {
  // A fixed list of hooks, called in the same order on every render.
  const setters = {
    decide: useEvent("decide"),
    verify: useEvent("verify"),
    revert: useEvent("revert"),
    upload: useEvent("upload"),
    use_sample: useEvent("use_sample"),
    export: useEvent("export"),
  };
  const send = useMemo<Send>(
    () => (id, payload) => setters[id]({ ...payload, nonce: Date.now() + Math.random() }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    Object.values(setters),
  );
  return <EventsContext.Provider value={send}>{children}</EventsContext.Provider>;
}

export const useSend = () => useContext(EventsContext);
