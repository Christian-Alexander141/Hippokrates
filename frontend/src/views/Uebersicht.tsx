import { useState } from "react";
import { useNavigate } from "react-router";
import { Activity, AlertTriangle, CheckCircle2, Plus, Search, Users, type LucideIcon } from "lucide-react";
import { usePatienten } from "../api/hooks";
import type { PatientEintrag, Zustand } from "../api/types";
import { personMeta, relativ, zeit } from "../lib/format";
import { Avatar, Button, Card, Icd, Leer, Spinner, ZustandBadge } from "../components/ui";

type Filter = "alle" | "laufend" | "aktuell" | "veraltet" | "offen";
const FILTER: { wert: Filter; text: string; passt: (z: Zustand) => boolean }[] = [
  { wert: "alle", text: "Alle", passt: () => true },
  { wert: "laufend", text: "Laufend", passt: (z) => z === "laufend" },
  { wert: "aktuell", text: "Aktuell", passt: (z) => z === "aktuell" },
  { wert: "veraltet", text: "Veraltet", passt: (z) => z === "veraltet" },
  { wert: "offen", text: "Ohne Ergebnis", passt: (z) => ["ohne", "leer", "fehler", "abgebrochen"].includes(z) },
];

export function Uebersicht() {
  const { data: patienten, isLoading } = usePatienten();
  const [filter, setFilter] = useState<Filter>("alle");
  const [q, setQ] = useState("");
  const navigate = useNavigate();

  if (isLoading) return <div className="seite zentriert"><Spinner groesse="gross" /></div>;
  const P = patienten ?? [];
  const n = (z: Zustand) => P.filter((p) => p.zustand === z).length;
  const s = q.trim().toLowerCase();
  const f = FILTER.find((x) => x.wert === filter)!;
  const sichtbar = P.filter((p) => f.passt(p.zustand)
    && (!s || p.name.toLowerCase().includes(s) || p.diagnosen.some((d) => d.name.toLowerCase().includes(s))));

  return (
    <div className="seite">
      <div className="seitenkopf">
        <div>
          <h2>Arbeitsliste</h2>
          <p className="muted">Konsens der Diagnose-Agenten über alle Patienten. Öffnen Sie einen Patienten für die vollständige Auswertung.</p>
        </div>
      </div>

      {!P.length ? (
        <Card>
          <Leer icon={Users} titel="Noch keine Patienten"
            text="Legen Sie einen Patienten an und erfassen Sie Beschwerden und Befunde. Der erste Abgleich startet danach automatisch."
            aktion={<Button variante="primary" icon={Plus} onClick={() => navigate("/patienten/neu")}>Patient anlegen</Button>} />
        </Card>
      ) : (
        <>
          <div className="kennzahlen">
            <Kennzahl icon={Users} wert={P.length} text="Patienten" />
            <Kennzahl icon={CheckCircle2} wert={n("aktuell")} text="aktuelle Ergebnisse" ton="ok" />
            <Kennzahl icon={Activity} wert={n("laufend")} text="Abgleiche laufen" ton="primary" puls={n("laufend") > 0} />
            <Kennzahl icon={AlertTriangle} wert={n("veraltet")} text="veraltete Ergebnisse" ton="warn" />
          </div>

          <Card>
            <div className="arbeitsliste-kopf">
              <div className="segmented" role="tablist" aria-label="Filter">
                {FILTER.map((x) => (
                  <button key={x.wert} type="button" role="tab" aria-selected={filter === x.wert}
                    className={filter === x.wert ? "an" : ""} onClick={() => setFilter(x.wert)}>
                    {x.text}<span className="leise tnum">{P.filter((p) => x.passt(p.zustand)).length}</span>
                  </button>
                ))}
              </div>
              <label className="plist-suche kompakt">
                <Search aria-hidden />
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtern …" aria-label="Arbeitsliste filtern" />
              </label>
            </div>
            <div className="tabelle-huelle">
              <table className="arbeitsliste">
                <thead>
                  <tr><th>Patient</th><th>Führende Diagnosen</th><th>Zustimmung</th><th>Status</th><th>Letzter Abgleich</th></tr>
                </thead>
                <tbody>
                  {sichtbar.map((p) => <Zeile key={p.id} p={p} oeffnen={() => navigate(`/patienten/${p.id}`)} />)}
                  {!sichtbar.length && <tr><td colSpan={5} className="leise zentriert-text">Keine Patienten in dieser Auswahl.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
      <Hinweis />
    </div>
  );
}

function Zeile({ p, oeffnen }: { p: PatientEintrag; oeffnen: () => void }) {
  const d = p.diagnosen[0];
  return (
    <tr tabIndex={0} onClick={oeffnen} onKeyDown={(e) => e.key === "Enter" && oeffnen()}>
      <td>
        <div className="zeile">
          <Avatar name={p.name} />
          <div className="ellipse"><b>{p.name}</b><br /><small className="leise">{personMeta(p) || "–"}</small></div>
        </div>
      </td>
      <td className="diag-zelle">
        {p.diagnosen.length ? (
          <ol className="kurzdiagnosen">
            {p.diagnosen.map((x, i) => (
              <li key={i} className={i === 0 ? "erste" : ""}><span className="ellipse">{x.name}</span><Icd code={x.icd10} /></li>
            ))}
          </ol>
        ) : <span className="leise">{p.zustand === "laufend" ? "Die Agenten recherchieren …" : p.zustand === "leer" ? "Noch keine klinischen Angaben" : "Noch kein Ergebnis"}</span>}
      </td>
      <td>
        {d && (
          <div className="zustimmung">
            <div className="balken"><i style={{ width: `${(100 * d.stimmen) / d.agenten_gesamt}%` }} /></div>
            <span className="tnum">{d.stimmen}/{d.agenten_gesamt}</span>
          </div>
        )}
      </td>
      <td><ZustandBadge zustand={p.zustand} /></td>
      <td className="leise tnum" title={p.abgeglichen ? zeit(p.abgeglichen) : `Akte geändert ${zeit(p.geaendert)}`}>
        {p.abgeglichen ? relativ(p.abgeglichen) : "–"}
      </td>
    </tr>
  );
}

function Kennzahl({ icon: Icon, wert, text, ton = "neutral", puls }:
  { icon: LucideIcon; wert: number; text: string; ton?: string; puls?: boolean }) {
  return (
    <div className={`kennzahl kennzahl-${ton}`}>
      <span className={`kennzahl-icon${puls ? " puls" : ""}`}><Icon aria-hidden /></span>
      <div><b className="tnum">{wert}</b><span>{text}</span></div>
    </div>
  );
}

export function Hinweis() {
  return (
    <p className="disclaimer">
      Entscheidungsunterstützung für medizinisches Fachpersonal – ersetzt nicht die ärztliche Diagnose.
      Übereinstimmung mehrerer Modelle ist kein Beleg für Richtigkeit.
    </p>
  );
}
