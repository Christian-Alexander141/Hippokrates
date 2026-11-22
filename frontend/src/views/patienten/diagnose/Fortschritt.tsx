import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { Lauf } from "../../../api/types";
import { modellName, SCHRITT_TEXT, schritteFuer, zeit } from "../../../lib/format";
import { AnbieterLogo } from "../../../lib/anbieter";
import { AgentBadge, Spinner } from "../../../components/ui";

/** Laufender Abgleich: je Agent eine Kachel mit aktuellem Schritt. */
export function Fortschritt({ lauf }: { lauf: Lauf }) {
  const schritte = schritteFuer(lauf.rahmen);
  let summe = 0;
  const kacheln = lauf.agenten.map((a) => {
    let fertig = 0;
    let jetzt = -1;
    if (a.status === "fertig") fertig = schritte.length;
    else if (a.status === "laufend") { jetzt = Math.max(0, schritte.indexOf(a.schritt)); fertig = jetzt; }
    summe += ["fertig", "fehler"].includes(a.status) ? 1 : (fertig + (jetzt >= 0 ? 0.5 : 0)) / schritte.length;
    const text = a.status === "laufend" ? SCHRITT_TEXT[a.schritt] ?? a.schritt
      : a.status === "fehler" ? a.fehler : a.status === "fertig" ? `fertig nach ${Math.round(a.dauer ?? 0)} s` : "wartet";
    return (
      <div key={a.nr} className={`lauf-agent ${a.status}`}>
        <div className="lauf-agent-kopf">
          <AgentBadge nr={a.nr} modell={a.modell} />
          <AnbieterLogo modell={a.modell} />
          <code className="ellipse" title={a.modell}>{modellName(a.modell)}</code>
          {a.status === "fertig" && <CheckCircle2 className="ok" aria-label="fertig" />}
          {a.status === "fehler" && <AlertTriangle className="fehler" aria-label="Fehler" />}
          {a.status === "laufend" && <Spinner groesse="klein" />}
        </div>
        <div className="schritte" aria-hidden>
          {schritte.map((s, i) => <i key={s} className={i < fertig ? "ok" : i === jetzt ? "jetzt" : ""} title={SCHRITT_TEXT[s]} />)}
        </div>
        <small title={text ?? ""}>{text}</small>
      </div>
    );
  });
  const fertig = lauf.agenten.filter((a) => ["fertig", "fehler"].includes(a.status)).length;
  const anteil = lauf.agenten.length ? Math.round((100 * summe) / lauf.agenten.length) : 3;

  return (
    <section className="card lauf" aria-live="polite">
      <div className="lauf-kopf">
        <Spinner groesse="gross" />
        <div>
          <b>{lauf.agenten.length ? "Die Agenten recherchieren unabhängig voneinander" : "Verfügbare Modelle werden geprüft …"}</b>
          <small>{fertig} von {lauf.agenten.length} Agenten fertig · gestartet {zeit(lauf.gestartet)}</small>
        </div>
        <span className="lauf-prozent tnum">{anteil} %</span>
      </div>
      <div className="lauf-balken"><i style={{ width: `${anteil}%` }} /></div>
      {kacheln.length > 0 && <div className="lauf-agenten">{kacheln}</div>}
    </section>
  );
}
