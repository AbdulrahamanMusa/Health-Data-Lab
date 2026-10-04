// Typed handles on the hooks shinyreact puts on window.shinyreact. They share
// the React instance this bundle is built against (see vite.config.js).

type InputOptions = {
  debounceMs?: number;
  priority?: "event" | "deferred";
  type?: string;
};
export type OutputStatus = "pending" | "ready" | "recalculating" | "error";

interface ShinyReact {
  useShinyInput<T>(id: string, defaultValue: T, opts?: InputOptions): [T, (v: T) => void];
  useSetShinyInput<T>(id: string, defaultValue: T, opts?: InputOptions): (v: T) => void;
  useShinyInputValue<T>(id: string): T | undefined;
  useShinyOutputValue<T>(id: string, defaultValue?: T): T | undefined;
  useShinyOutputStatus(id: string): OutputStatus;
  useShinyOutputError(id: string): { message: string } | null;
  useShinyMessageHandler<T>(id: string, handler: (data: T) => void): void;
  useShinyInitialized(): boolean;
  useShinyBusy(): boolean;
}

const sr = (window as unknown as { shinyreact: ShinyReact }).shinyreact;

export const {
  useShinyInput,
  useSetShinyInput,
  useShinyInputValue,
  useShinyOutputValue,
  useShinyOutputStatus,
  useShinyOutputError,
  useShinyMessageHandler,
  useShinyInitialized,
  useShinyBusy,
} = sr;
