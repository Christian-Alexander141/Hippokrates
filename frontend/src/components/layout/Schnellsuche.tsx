import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Cpu, LayoutDashboard, Plus, Search, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { usePatienten } from "../../api/hooks";
import type { Zustand } from "../../api/types";
import { personMeta } from "../../lib/format";
import { Avatar, ZustandPunkt } from "../ui";

interface PatientTreffer { id: string; titel: string; unter: string; name: string; zustand: Zustand; ziel: string }
interface BereichTreffer { id: string; titel: string; icon: LucideIcon; ziel: string }

/** Strg+K: Patienten und Bereiche per Tastatur öffnen. */
export function Schnellsuche({ offen, schliessen }: { offen: boolean; schliessen: () => void }) {
  const { data: patienten = [] } = usePatienten();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [aktiv, setAktiv] = useState(0);
  const eingabe = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (offen) {
      setQ("");
      setAktiv(0);
      setTimeout(() => eingabe.current?.focus(), 0);
    }
  }, [offen]);

  const treffer = useMemo(() => {
    const s = q.trim().toLowerCase();
    const p = patienten
      .filter((x) => !s || x.name.toLowerCase().includes(s) || x.geburtsdatum.includes(s)
        || x.diagnosen.some((d) => d.name.toLowerCase().includes(s) || d.icd10.toLowerCase().includes(s)))
      .slice(0, 8)
      .map((x): PatientTreffer => ({ id: `p${x.id}`, titel: x.name, name: x.name, zustand: x.zustand,
        unter: [personMeta(x), x.diagnosen[0]?.name].filter(Boolean).join(" · "), ziel: `/patienten/${x.id}` }));
    const bereiche: BereichTreffer[] = [
      { id: "neu", titel: "Neuen Patienten anlegen", icon: Plus, ziel: "/patienten/neu" },
      { id: "ueb", titel: "Übersicht", icon: LayoutDashboard, ziel: "/" },
      { id: "adm", titel: "Adminbereich – Fachbibliothek, Netze, Vorgaben", icon: SlidersHorizontal, ziel: "/admin" },
      { id: "tec", titel: "Modelle & Technik", icon: Cpu, ziel: "/technik" },
    ].filter((b) => !s || b.titel.toLowerCase().includes(s));
    return { p, bereiche, alle: [...p, ...bereiche] as { ziel: string }[] };
  }, [q, patienten]);

  if (!offen) return null;

  const oeffnen = (ziel: string) => { schliessen(); navigate(ziel); };
  const taste = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setAktiv((a) => Math.min(a + 1, treffer.alle.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setAktiv((a) => Math.max(a - 1, 0)); }
    if (e.key === "Enter" && treffer.alle[aktiv]) oeffnen(treffer.alle[aktiv].ziel);
    if (e.key === "Escape") schliessen();
  };

  let i = -1;
  return (
    <div className="palette-hintergrund" onMouseDown={(e) => e.target === e.currentTarget && schliessen()}>
      <div className="palette" role="dialog" aria-label="Schnellsuche">
        <div className="palette-suche">
          <Search aria-hidden />
          <input ref={eingabe} value={q} placeholder="Patient, Diagnose, ICD-10 oder Bereich …" aria-label="Suchbegriff"
            onChange={(e) => { setQ(e.target.value); setAktiv(0); }} onKeyDown={taste} />
        </div>
        <ul>
          {treffer.p.length > 0 && <li className="palette-gruppe">Patienten</li>}
          {treffer.p.map((t) => {
            i++;
            const n = i;
            return (
              <li key={t.id} className={n === aktiv ? "aktiv" : ""} onMouseEnter={() => setAktiv(n)} onClick={() => oeffnen(t.ziel)}>
                <Avatar name={t.name} />
                <span className="ellipse" style={{ flex: 1 }}><b>{t.titel}</b><br /><small className="leise">{t.unter || "–"}</small></span>
                <ZustandPunkt zustand={t.zustand} />
              </li>
            );
          })}
          {treffer.bereiche.length > 0 && <li className="palette-gruppe">Bereiche</li>}
          {treffer.bereiche.map((t) => {
            i++;
            const n = i;
            const Icon = t.icon;
            return (
              <li key={t.id} className={n === aktiv ? "aktiv" : ""} onMouseEnter={() => setAktiv(n)} onClick={() => oeffnen(t.ziel)}>
                <Icon aria-hidden /><span>{t.titel}</span>
              </li>
            );
          })}
          {!treffer.alle.length && <li className="palette-gruppe">Keine Treffer</li>}
        </ul>
        <div className="palette-fuss"><span><kbd>↑</kbd> <kbd>↓</kbd> auswählen</span><span><kbd>↵</kbd> öffnen</span><span><kbd>Esc</kbd> schließen</span></div>
      </div>
    </div>
  );
}
