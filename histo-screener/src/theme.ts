import { useEffect, useState } from "react";

export type ThemeMode = "light" | "dark" | "system";
const KEY = "histo-theme";

export function readMode(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    // Storage can be blocked; fall back to light.
  }
  return "light";
}

const systemDark = () => typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches;
export const resolve = (m: ThemeMode) => (m === "system" ? (systemDark() ? "dark" : "light") : m);

export function applyTheme(t: "light" | "dark") {
  document.documentElement.dataset.theme = t;
  document.documentElement.style.colorScheme = t;
}

export function useTheme() {
  const [mode, setModeState] = useState<ThemeMode>(readMode);
  useEffect(() => {
    applyTheme(resolve(mode));
    if (mode !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => applyTheme(resolve("system"));
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [mode]);
  const setMode = (m: ThemeMode) => {
    try {
      localStorage.setItem(KEY, m);
    } catch {
      // Non-fatal: the choice won't survive a reload.
    }
    setModeState(m);
  };
  return { mode, setMode };
}
