import { useState } from "react";
import { BookOpen, Bot, BrainCircuit, ChevronDown, ExternalLink, Globe, HelpCircle, Send, TriangleAlert } from "lucide-react";
import type { Agent, Lauf, Quelle } from "../../../api/types";
import { useAntwortenSenden } from "../../../api/hooks";
import { modellName, prozent } from "../../../lib/format";
import type { Register } from "../../../lib/quellen";
import { useFehlerToast, useToast } from "../../../components/rueckmeldung";
import { AnbieterLogo } from "../../../lib/anbieter";
import { AgentBadge, Badge, Button, Card, CardHead } from "../../../components/ui";

const ART_ICON = { buch: BookOpen, web: Globe, netz: BrainCircuit };

// ── Rückfragen ─────────────────────────────────────────────────────────────

const entwuerfe = new Map<string, string>(); // überstehen Neuzeichnen und Seitenwechsel

export function Rueckfragen({ e, patientId }: { e: Lauf; patientId: number }) {
  const [, neu] = useState(0);
  const senden = useAntwortenSenden();
  const toast = useToast();
  const fehler = useFehlerToast();
  if (!e.rahmen?.rueckfragen) return null;
  const schl = (f: string) => `${patientId}|${f}`;

  const abschicken = () => {
    const antworten = e.rueckfragen.map((f) => ({ frage: f.frage, antwort: (entwuerfe.get(schl(f.frage)) ?? "").trim() }))
      .filter((a) => a.antwort);
    if (!antworten.length) return toast("Bitte mindestens eine Rückfrage beantworten.");
    senden.mutate({ id: patientId, antworten }, {
      onSuccess: () => {
        antworten.forEach((a) => entwuerfe.delete(schl(a.frage)));
        toast("Antworten in der Akte ergänzt – neuer Abgleich läuft");
      },
      onError: fehler,
    });
  };

  return (
    <Card>
      <CardHead icon={HelpCircle} titel="Rückfragen der Agenten" zaehler={e.rueckfragen.length} />
      <div className="card-body">
        {!e.rueckfragen.length ? (
          <p className="klein muted">Keine Rückfragen – den Agenten fehlten keine wesentlichen Angaben.</p>
        ) : (
          <>
            <p className="klein muted">Antworten werden in der Akte unter „Ergänzungen“ gespeichert und lösen einen neuen Abgleich aus.</p>
            {e.rueckfragen.map((f) => (
              <div key={f.frage} className="frage">
                <div className="frage-kopf">
                  <span>{f.frage}</span>
                  <span className="frage-von">{f.agenten.map((nr) => <AgentBadge key={nr} nr={nr} />)}</span>
                </div>
                <textarea rows={1} placeholder="Antwort …" aria-label={`Antwort auf: ${f.frage}`}
                  defaultValue={entwuerfe.get(schl(f.frage)) ?? ""}
                  onChange={(ev) => { entwuerfe.set(schl(f.frage), ev.target.value); neu((x) => x + 1); }} />
              </div>
            ))}
            <Button variante="primary" block icon={Send} disabled={senden.isPending} onClick={abschicken}>
              Antworten übernehmen und neu abgleichen
            </Button>
          </>
        )}
      </div>
    </Card>
  );
}

// ── Zitierte Quellen ───────────────────────────────────────────────────────

function NetzErgebnis({ q }: { q: Quelle }) {
  return (
    <div className="netz-ergebnis">
      {(q.vorhersagen ?? []).map((v) => (
        <div key={v.bezeichnung} className="netz-zeile">
          <span className="ellipse">{v.bezeichnung}</span>
          {q.netz_art !== "regression" ? (
            <><div className="balken"><i style={{ width: `${v.wert * 100}%` }} /></div><span className="tnum">{prozent(v.wert)}</span></>
          ) : <span className="tnum">{v.wert} {v.einheit}</span>}
        </div>
      ))}
      {q.eingabe && (
        <div className="netz-eingabe">
          Eingaben: {Object.entries(q.eingabe).map(([k, v]) => <code key={k}>{k}={String(v)}</code>)}
        </div>
      )}
      {q.hinweis && <div className="netz-hinweis"><TriangleAlert aria-hidden />{q.hinweis}</div>}
    </div>
  );
}

export function Quellen({ reg, e }: { reg: Register; e: Lauf }) {
  const r = e.rahmen;
  return (
    <Card>
      <CardHead icon={BookOpen} titel="Zitierte Quellen" zaehler={reg.liste.length} />
      <div className="card-body dicht">
        {!reg.liste.length ? (
          <p className="klein muted" style={{ padding: "14px 0" }}>
            {r && !r.buecher?.length && !r.internet && !r.netze?.length
              ? "Weder Fachbücher, Internetrecherche noch eigene Netze waren freigegeben – die Agenten stützten sich nur auf ihr Modellwissen."
              : "Die Agenten haben keine der gefundenen Quellen als Beleg angegeben."}
          </p>
        ) : reg.liste.map(({ nr, q, agenten, diagnosen }) => {
          const Icon = ART_ICON[q.art];
          return (
            <div key={nr} id={`quelle-${nr}`} className="quelle">
              <span className={`q-nr q-${q.art}`}>{nr}</span>
              <div>
                <div className="q-titel">
                  {q.art === "web"
                    ? <a href={q.url} target="_blank" rel="noopener noreferrer">{q.titel}<ExternalLink aria-hidden /></a>
                    : q.art === "netz" ? <>{q.titel}{q.version && <span className="leise"> · v{q.version}</span>}</> : q.datei}
                </div>
                <div className="q-meta">
                  <Icon aria-hidden />
                  {q.art === "web" ? `PubMed · ${q.fundstelle}` : q.art === "netz" ? "Eigenes neuronales Netz" : q.seite ? `Fachbuch · Seite ${q.seite}` : "Fachbuch"}
                  <span>·</span>
                  {[...agenten].sort((a, b) => a - b).map((n) => <AgentBadge key={n} nr={n} />)}
                </div>
                <div className="q-diag">Beleg für {[...diagnosen].join(", ")}</div>
                {q.art === "netz" ? <NetzErgebnis q={q} /> : (
                  <details className="auszug-d">
                    <summary><ChevronDown className="pfeil" aria-hidden />Auszug</summary>
                    <div className="auszug">{q.text}</div>
                  </details>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ── Agenten im Einzelnen ───────────────────────────────────────────────────

const STATUS: Record<Agent["status"], [string, string]> = {
  fertig: ["ok", "fertig"], fehler: ["danger", "Fehler"], abgebrochen: ["neutral", "abgebrochen"],
  laufend: ["primary", "läuft"], wartend: ["neutral", "wartet"],
};

export function AgentenDetails({ e }: { e: Lauf }) {
  const ok = e.agenten.filter((a) => a.status === "fertig").length;
  return (
    <Card>
      <CardHead icon={Bot} titel="Agenten im Einzelnen"><span className="klein leise tnum">{ok}/{e.agenten.length} erfolgreich</span></CardHead>
      <div className="card-body dicht">
        {e.agenten.map((a) => {
          const [ton, text] = STATUS[a.status];
          return (
            <details key={a.nr} className="agent">
              <summary>
                <AgentBadge nr={a.nr} modell={a.modell} />
                <AnbieterLogo modell={a.modell} />
                <code className="ellipse" title={a.modell}>{modellName(a.modell)}</code>
                <Badge ton={ton}>{text}</Badge>
                <small className="leise tnum">{a.dauer ? `${Math.round(a.dauer)} s` : ""}</small>
                <ChevronDown className="pfeil" aria-hidden />
              </summary>
              <div className="agent-inhalt">
                {a.fehler && <div className="fehlertext">{a.fehler}</div>}
                {a.hinweise.map((t) => <div key={t} className="hinweistext"><TriangleAlert aria-hidden /><span>{t}</span></div>)}
                {a.diagnosen.length > 0 && (
                  <><div className="ag-titel">Eigene Rangliste</div>
                    <ol>{a.diagnosen.map((d) => <li key={d.name}>{d.name} <span className="mono leise">{d.icd10}</span></li>)}</ol></>
                )}
                {a.suchanfragen.length > 0 ? (
                  <><div className="ag-titel">Recherche</div>
                    <div>{a.suchanfragen.map((s) => {
                      const Icon = ART_ICON[s.art];
                      return <span key={s.art + s.text} className="such"><Icon aria-hidden />{s.text}</span>;
                    })}</div></>
                ) : a.status === "fertig" && <div className="klein muted">Ohne Recherche – keine Quellen freigegeben.</div>}
                {a.quellen.length > 0 && (
                  <div className="klein muted" style={{ marginTop: 6 }}>
                    {a.quellen.length} Quellen gefunden, {new Set(a.diagnosen.flatMap((d) => d.quellen)).size} davon zitiert
                  </div>
                )}
                {a.rueckfragen.length > 0 && (
                  <><div className="ag-titel">Rückfragen</div><ul className="einrueck">{a.rueckfragen.map((f) => <li key={f}>{f}</li>)}</ul></>
                )}
              </div>
            </details>
          );
        })}
      </div>
    </Card>
  );
}
