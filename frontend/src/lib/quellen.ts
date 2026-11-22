import type { Lauf, Quelle } from "../api/types";

export interface RegisterEintrag { nr: number; q: Quelle; agenten: Set<number>; diagnosen: Set<string> }
export interface Register { liste: RegisterEintrag[]; ref: (agentNr: number, lokal: number) => number | null }

/** Gemeinsame Nummerierung der von allen Agenten zitierten Quellen (Fachbuch, PubMed, eigene Netze). */
export function quellenRegister(e: Lauf): Register {
  const agenten = new Map(e.agenten.map((a) => [a.nr, a]));
  const liste: RegisterEintrag[] = [];
  const index = new Map<string, number>();
  const ref = (agentNr: number, lokal: number) => {
    const q = agenten.get(agentNr)?.quellen.find((x) => x.nr === lokal);
    if (!q) return null;
    const k = q.art === "web" ? `w${q.id}` : q.art === "netz" ? `n${q.id}` : `b${q.id ?? `${q.datei}${q.seite}`}`;
    if (!index.has(k)) {
      liste.push({ nr: liste.length + 1, q, agenten: new Set(), diagnosen: new Set() });
      index.set(k, liste.length);
    }
    return index.get(k)!;
  };
  for (const g of e.konsens) for (const n of g.nennungen) for (const lokal of n.quellen) {
    const nr = ref(n.agent, lokal);
    if (nr) { liste[nr - 1].agenten.add(n.agent); liste[nr - 1].diagnosen.add(g.name); }
  }
  return { liste, ref };
}

export const quellTitel = (q: Quelle) =>
  q.art === "web" ? q.titel ?? "" : q.art === "netz" ? q.titel ?? `Netz ${q.netz}` : `${q.datei}${q.seite ? `, S. ${q.seite}` : ""}`;

export function zuQuelleSpringen(nr: number) {
  const el = document.getElementById(`quelle-${nr}`);
  if (!el) return;
  el.scrollIntoView({ block: "center", behavior: "smooth" });
  el.classList.remove("blink");
  void el.offsetWidth;
  el.classList.add("blink");
}
