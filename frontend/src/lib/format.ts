import type { Rahmen, Schritt, Zustand } from "../api/types";

export const zahl = (n: number) => n.toLocaleString("de-DE", { maximumFractionDigits: 1 });

export const zeit = (s?: string | null) =>
  s ? new Date(s).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";

export const uhrzeit = (s?: string | null) =>
  s ? new Date(s).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";

export const datum = (s?: string | null) => {
  if (!s) return "";
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
};

export function dauer(von: string, bis: string | null) {
  if (!bis) return "";
  const s = (new Date(bis).getTime() - new Date(von).getTime()) / 1000;
  return s < 90 ? `${Math.max(1, Math.round(s))} s` : `${Math.round(s / 60)} min`;
}

export function relativ(s?: string | null) {
  if (!s) return "";
  const sek = Math.round((Date.now() - new Date(s).getTime()) / 1000);
  if (sek < 10) return "gerade eben";
  if (sek < 60) return `vor ${sek} s`;
  if (sek < 3600) return `vor ${Math.round(sek / 60)} min`;
  if (sek < 86400) return `vor ${Math.round(sek / 3600)} h`;
  return zeit(s);
}

export const groesse = (b: number) =>
  b >= 1e9 ? `${zahl(b / 1e9)} GB` : b >= 1e6 ? `${zahl(b / 1e6)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`;

export const prozent = (w: number) => `${(w * 100).toLocaleString("de-DE", { maximumFractionDigits: 1 })} %`;

export const initialen = (n: string) =>
  (n || "?").split(/[\s,]+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

export const farbton = (n: string) => [...(n || "")].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 11);

const AGENT_FARBEN = ["#0b7285", "#7c5cd6", "#d97706", "#db2777", "#16a34a", "#2563eb", "#ca8a04", "#be123c",
  "#0f766e", "#4f46e5", "#ea580c", "#64748b"];
export const agentFarbe = (nr: number) => AGENT_FARBEN[(nr - 1) % AGENT_FARBEN.length];

/** Anzeigename einer Modellkennung: „lmstudio::llama-3“ -> „llama-3“. */
export const modellName = (id: string) => (id.includes("::") ? id.split("::").slice(1).join("::") : id);
export const modellQuelle = (id: string) => (id.includes("::") ? id.split("::")[0] : "ollama");

export const personMeta = (p: { alter?: number | null; geschlecht?: string }) =>
  [p.alter != null ? `${p.alter} Jahre` : "", p.geschlecht].filter(Boolean).join(" · ");

export const ZUSTAND: Record<Zustand, { ton: string; text: string }> = {
  aktuell: { ton: "ok", text: "Aktuell" },
  veraltet: { ton: "warn", text: "Veraltet" },
  laufend: { ton: "primary", text: "Abgleich läuft" },
  fehler: { ton: "danger", text: "Fehlgeschlagen" },
  abgebrochen: { ton: "neutral", text: "Abgebrochen" },
  ohne: { ton: "neutral", text: "Kein Abgleich" },
  leer: { ton: "neutral", text: "Keine Angaben" },
};

export const SCHRITT_TEXT: Record<string, string> = {
  startet: "startet",
  plant: "plant die Recherche",
  bibliothek: "durchsucht die Fachbibliothek",
  internet: "sucht in PubMed",
  netze: "befragt eigene neuronale Netze",
  diagnose: "erstellt Diagnosen",
};

export function schritteFuer(r: Rahmen | null | undefined): Schritt[] {
  const s: Schritt[] = [];
  const netze = (r?.netze?.length ?? 0) > 0;
  if (r?.buecher?.length || r?.internet || netze) s.push("plant");
  if (r?.buecher?.length) s.push("bibliothek");
  if (r?.internet) s.push("internet");
  if (netze) s.push("netze");
  return [...s, "diagnose"];
}
