import { useEffect, useState } from "react";

import { type ThemeName, setChartTheme } from "@/components/common";

export type ThemeMode = "light" | "dark" | "system";
const KEY = "hdl-theme";

export function readMode(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    // Storage can be blocked (private windows, previews); fall back to light.
  }
  return "light";
}

function saveMode(m: ThemeMode) {
  try {
    localStorage.setItem(KEY, m);
  } catch {
    // Non-fatal: the choice just will not survive a reload.
  }
}

const systemDark = () => typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches;

export function resolve(mode: ThemeMode): ThemeName {
  return mode === "system" ? (systemDark() ? "dark" : "light") : mode;
}

export function applyTheme(t: ThemeName) {
  document.documentElement.dataset.theme = t;
  document.documentElement.style.colorScheme = t;
  setChartTheme(t);
}

export function useTheme() {
  const [mode, setModeState] = useState<ThemeMode>(readMode);
  const [theme, setTheme] = useState<ThemeName>(() => resolve(readMode()));

  useEffect(() => {
    const t = resolve(mode);
    applyTheme(t);
    setTheme(t);
    if (mode !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const next = resolve("system");
      applyTheme(next);
      setTheme(next);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [mode]);

  const setMode = (m: ThemeMode) => {
    saveMode(m);
    setModeState(m);
  };
  return { mode, setMode, theme };
}
