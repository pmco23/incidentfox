export type ThemeMode = "dark" | "light";

const STORAGE_KEY = "incidentfox_theme";

export function getTheme(): ThemeMode {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "light" ? "light" : "dark";
}

export function applyTheme(mode: ThemeMode) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (mode === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
}

export function setTheme(mode: ThemeMode) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, mode);
  }
  applyTheme(mode);
}


