import { useEffect, useMemo, useState } from "react";
import { useBlocker } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  Bot, CheckCircle2, CircleDot, Cloud, Cpu, Database, Eye, Layers, ListChecks, Lock, Network, Plus, RefreshCw, Save,
  Server, SlidersHorizontal, Sparkles, Trash2, TriangleAlert, Wrench, X,
} from "lucide-react";
import { schluessel, useEinstellungen, useEinstellungenAendern, useModelle } from "../api/hooks";
import type { Einstellungen, Modell, ModellQuelle } from "../api/types";
import { groesse, modellName, uhrzeit } from "../lib/format";
import { AnbieterLogo, QuellenLogo } from "../lib/anbieter";
import { useBestaetigen, useFehlerToast, useToast } from "../components/rueckmeldung";
import { AgentBadge, Badge, Banner, Button, Card, CardHead, Einstellung, Feld, IconButton, Segmented, Spinner, Switch } from "../components/ui";

type Entwurf = Pick<Einstellungen, "agenten" | "agenten_modus" | "ausgeschlossene_modelle" | "server_suchen" | "zusatz_server"
  | "embedding_modell" | "ollama_url" | "top_k" | "parallel" | "icd_abgleich" | "denken">;
const FELDER: (keyof Entwurf)[] = ["agenten", "agenten_modus", "ausgeschlossene_modelle", "server_suchen", "zusatz_server",
  "embedding_modell", "ollama_url", "top_k", "parallel", "icd_abgleich", "denken"];
const auszug = (e: Einstellungen) => Object.fromEntries(FELDER.map((f) => [f, e[f]])) as Entwurf;

export function Technik() {
  const { data } = useEinstellungen();
  if (!data) return <div className="seite zentriert"><Spinner groesse="gross" /></div>;
  return <TechnikFormular key={JSON.stringify(auszug(data.einstellungen))} gespeichert={auszug(data.einstellungen)}
    ollamaFest={data.umgebung.ollama_url_fest} docker={data.umgebung.docker} modellHost={data.umgebung.modell_host} />;
}

function TechnikFormular({ gespeichert, ollamaFest, docker, modellHost }:
  { gespeichert: Entwurf; ollamaFest: boolean; docker: boolean; modellHost: string }) {
  const [e, setE] = useState<Entwurf>(gespeichert);
  const geaendert = JSON.stringify(e) !== JSON.stringify(gespeichert);
  const { data: liste, isFetching, dataUpdatedAt } = useModelle();
  const qc = useQueryClient();
  const aendern = useEinstellungenAendern();
  const toast = useToast();
  const fehler = useFehlerToast();
  const bestaetigen = useBestaetigen();
  const setze = <K extends keyof Entwurf>(k: K, v: Entwurf[K]) => setE((x) => ({ ...x, [k]: v }));

  const sperre = useBlocker(({ currentLocation, nextLocation }) => geaendert && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (sperre.state !== "blocked") return;
    bestaetigen({ titel: "Ungespeicherte Einstellungen verwerfen?", ok: "Verwerfen", gefahr: true }).then((ja) => (ja ? sperre.proceed() : sperre.reset()));
  }, [sperre, bestaetigen]);

  const modelle = liste?.modelle ?? [];
  const chat = modelle.filter((m) => !m.embedding);
  const embedding = modelle.filter((m) => m.embedding);
  const vorhanden = new Set(chat.map((m) => m.id));

  // Agenten in der Reihenfolge, in der sie beim nächsten Abgleich antreten
  const agenten = useMemo(() => e.agenten_modus === "alle"
    ? chat.filter((m) => !m.cloud && !e.ausgeschlossene_modelle.includes(m.id))
      .sort((a, b) => b.groesse - a.groesse || a.id.localeCompare(b.id)).map((m) => m.id)
    : e.agenten, [e, chat]);
  const fehlend = e.agenten_modus === "auswahl" ? e.agenten.filter((m) => liste && !vorhanden.has(m)) : [];
  const cloudAgenten = agenten.filter((id) => chat.find((m) => m.id === id)?.cloud);

  const umschalten = (m: Modell, an: boolean) => {
    if (e.agenten_modus === "alle") {
      setze("ausgeschlossene_modelle", an ? e.ausgeschlossene_modelle.filter((x) => x !== m.id) : [...e.ausgeschlossene_modelle, m.id]);
    } else {
      setze("agenten", an ? [...e.agenten, m.id] : e.agenten.filter((x) => x !== m.id));
    }
  };
  const speichern = () => {
    if (e.agenten_modus === "auswahl" && !e.agenten.length) return toast("Bitte mindestens ein Modell als Agent auswählen.", { fehler: true });
    const werte: Partial<Einstellungen> = { ...e };
    if (ollamaFest) delete werte.ollama_url;
    aendern.mutate(werte, { onSuccess: () => toast("Technische Einstellungen gespeichert – gelten ab dem nächsten Abgleich"), onError: fehler });
  };

  const gruppen = [...chat.reduce((g, m) => g.set(m.quelle_name, [...(g.get(m.quelle_name) ?? []), m]), new Map<string, Modell[]>())];

  return (
    <div className="seite">
      <div className="seitenkopf">
        <div>
          <h2>Modelle & Technik</h2>
          <p className="muted">Alle Sprachmodelle, die auf diesem Rechner{docker ? " (Docker-Host)" : ""} verfügbar sind – bei jedem Öffnen und alle 30 Sekunden neu geprüft.</p>
        </div>
      </div>

      <div className="stapel">
        <Card>
          <CardHead icon={Layers} titel="Verfügbare Sprachmodelle" zaehler={chat.length}>
            <span className="klein leise">{dataUpdatedAt ? `geprüft ${uhrzeit(liste?.geprueft)}` : ""}</span>
            <Button klein icon={RefreshCw} disabled={isFetching} onClick={() => qc.invalidateQueries({ queryKey: schluessel.modelle })}>
              {isFetching ? "Prüfe …" : "Neu prüfen"}
            </Button>
          </CardHead>
          <div className="card-body stapel-klein">
            <QuellenLeiste quellen={liste?.quellen ?? []} suchen={e.server_suchen} modellHost={modellHost} />
            <div className="modus">
              <div>
                <b>Welche Modelle arbeiten als Agenten?</b>
                <p className="klein muted">
                  {e.agenten_modus === "alle"
                    ? "Jeder Abgleich verwendet alle lokalen Chat-Modelle, die in diesem Moment verfügbar sind. Neu installierte Modelle arbeiten automatisch mit; ausgeschaltete bleiben außen vor."
                    : "Nur die eingeschalteten Modelle arbeiten als Agenten – in der Reihenfolge, in der Sie sie einschalten."}
                </p>
              </div>
              <Segmented label="Agentenauswahl" wert={e.agenten_modus} onChange={(v) => setze("agenten_modus", v)}
                werte={[{ wert: "auswahl", text: "Eigene Auswahl", icon: ListChecks }, { wert: "alle", text: "Alle lokalen Modelle", icon: Sparkles }]} />
            </div>
            {cloudAgenten.length > 0 && (
              <Banner ton="warn" icon={Cloud}>
                Cloud- bzw. Netzwerkmodelle ({cloudAgenten.map(modellName).join(", ")}) erhalten Anamnese und Befunde. Für echte Patientendaten nur lokale Modelle verwenden.
              </Banner>
            )}
            {fehlend.length > 0 && (
              <Banner ton="danger" icon={TriangleAlert}>
                Als Agent eingetragen, aber derzeit nicht verfügbar: {fehlend.map((m) => (
                  <span key={m} className="fehlend-chip"><code>{m}</code>
                    <button type="button" aria-label={`${m} entfernen`} onClick={() => setze("agenten", e.agenten.filter((x) => x !== m))}><X aria-hidden /></button>
                  </span>))}
                <br /><small>Diese Agenten fallen beim nächsten Abgleich aus, bis das Modell wieder bereitsteht.</small>
              </Banner>
            )}
            {!liste ? <div className="zentriert" style={{ padding: 30 }}><Spinner /></div>
              : !chat.length ? <Banner ton="warn" icon={TriangleAlert}>Keine Sprachmodelle gefunden. Läuft Ollama{docker ? " auf dem Host und ist es aus dem Container erreichbar" : ""}?</Banner>
                : (
                  <div className="tabelle-huelle">
                    <table className="modelltabelle">
                      <thead>
                        <tr><th className="spalte-schalter">Agent</th><th>Modell</th><th>Parameter</th><th>Größe</th><th>Fähigkeiten</th><th>Standort</th></tr>
                      </thead>
                      {gruppen.map(([quelle, ms]) => (
                        <tbody key={quelle}>
                          <tr className="gruppenzeile"><td colSpan={6}><span className="zeile"><QuellenLogo quelle={ms[0].quelle} />{quelle}<span className="leise">· {ms.length} {ms.length === 1 ? "Modell" : "Modelle"}</span></span></td></tr>
                          {ms.map((m) => {
                            const nr = agenten.indexOf(m.id) + 1;
                            const gesperrt = e.agenten_modus === "alle" && m.cloud;
                            return (
                              <tr key={m.id} className={nr ? "gewaehlt" : ""}>
                                <td className="spalte-schalter">
                                  <div className="zeile">
                                    <Switch an={nr > 0} disabled={gesperrt} onChange={(v) => umschalten(m, v)}
                                      label={`${m.name} als Agent ${nr ? "abwählen" : "verwenden"}`} />
                                    {nr > 0 && <AgentBadge nr={nr} modell={m.id} />}
                                  </div>
                                </td>
                                <td>
                                  <span className="modell-zelle">
                                    <AnbieterLogo modell={m.id} familie={m.familie} groesse={18} />
                                    <code className="modellname">{m.name}</code>
                                    {m.familie && <small className="leise">{m.familie}</small>}
                                  </span>
                                </td>
                                <td className="tnum">{m.parameter || "–"}{m.quantisierung && <small className="leise"> · {m.quantisierung}</small>}</td>
                                <td className="tnum">{m.groesse && !m.cloud ? groesse(m.groesse) : "–"}</td>
                                <td><Faehigkeiten f={m.faehigkeiten} /></td>
                                <td><Standort m={m} /></td>
                              </tr>
                            );
                          })}
                        </tbody>
                      ))}
                    </table>
                  </div>
                )}
          </div>
        </Card>

        <div className="raster-2">
          <div className="stapel">
            <Card>
              <CardHead icon={Bot} titel="Agenten beim nächsten Abgleich" zaehler={agenten.length} />
              <div className="card-body">
                {agenten.length ? (
                  <ol className="agentenliste">
                    {agenten.map((id, i) => {
                      const m = chat.find((x) => x.id === id);
                      return (
                        <li key={id}>
                          <AgentBadge nr={i + 1} modell={id} />
                          <AnbieterLogo modell={id} familie={m?.familie} />
                          <code className="ellipse" title={id}>{modellName(id)}</code>
                          <small className="leise">{m?.quelle_name ?? "nicht verfügbar"}</small>
                        </li>
                      );
                    })}
                  </ol>
                ) : <p className="klein muted">Noch kein Agent – schalten Sie oben Modelle ein.</p>}
                <p className="klein muted" style={{ marginTop: 10 }}>Je verschiedener die Modelle (Hersteller, Trainingsdaten), desto aussagekräftiger ist ihre Übereinstimmung.</p>
              </div>
              <Einstellung icon={Cpu} titel="Gleichzeitig laufende Agenten" text="Mehr als 1 nur, wenn der Grafikspeicher mehrere Modelle zugleich fasst.">
                <input type="number" min={1} max={12} value={e.parallel} aria-label="Gleichzeitig laufende Agenten"
                  onChange={(v) => setze("parallel", Math.max(1, Math.min(12, Number(v.target.value) || 1)))} />
              </Einstellung>
            </Card>
            <Card>
              <CardHead icon={Database} titel="Embedding-Modell der Fachbibliothek" />
              <div className="card-body stapel-klein">
                <p className="klein muted">Wandelt Buchabschnitte und Suchanfragen in Vektoren um. Ein Wechsel indexiert alle Fachbücher neu.</p>
                <div className="auswahlliste" role="radiogroup" aria-label="Embedding-Modell">
                  {embedding.map((m) => (
                    <label key={m.id} className={`auswahl${e.embedding_modell === m.id ? " an" : ""}`}>
                      <input type="radio" name="embedding" checked={e.embedding_modell === m.id} onChange={() => setze("embedding_modell", m.id)} />
                      <AnbieterLogo modell={m.id} familie={m.familie} />
                      <code className="ellipse">{m.name}</code>
                      <small className="leise">{m.quelle_name}{m.groesse ? ` · ${groesse(m.groesse)}` : ""}</small>
                      <Standort m={m} />
                    </label>
                  ))}
                  {e.embedding_modell && !embedding.some((m) => m.id === e.embedding_modell) && liste && (
                    <label className="auswahl an"><input type="radio" checked readOnly /><code>{e.embedding_modell}</code><Badge ton="danger">nicht verfügbar</Badge></label>
                  )}
                  {!embedding.length && <p className="klein muted">Kein Embedding-Modell gefunden – z. B. <code className="mono">ollama pull granite-embedding:278m</code>.</p>}
                </div>
              </div>
            </Card>
          </div>
          <div className="stapel">
            <Verbindungen e={e} setze={setze} ollamaFest={ollamaFest} docker={docker} modellHost={modellHost} />
            <Card>
              <CardHead icon={SlidersHorizontal} titel="Suche und Abgleich" />
              <Einstellung titel="Literaturstellen je Suchanfrage" text="Wie viele Abschnitte die Bibliothekssuche pro Anfrage liefert (1–10).">
                <input type="number" min={1} max={10} value={e.top_k} aria-label="Literaturstellen je Suchanfrage"
                  onChange={(v) => setze("top_k", Math.max(1, Math.min(10, Number(v.target.value) || 1)))} />
              </Einstellung>
              <Einstellung titel="ICD-10-Kategorien zusammenfassen" text="Nennungen mit gleicher dreistelliger Kategorie (z. B. K35) gelten als dieselbe Diagnose. Fängt Synonyme ab, kann aber bei falsch geratenen Codes Verschiedenes zusammenlegen.">
                <Switch an={e.icd_abgleich} onChange={(v) => setze("icd_abgleich", v)} label="ICD-10-Kategorien zusammenfassen" />
              </Einstellung>
              <Einstellung titel="Denkphase zulassen" text="Thinking-Modelle (Fähigkeit „Denken“) überlegen vor der Antwort. Gründlicher, aber je Agent oft mehrere Minuten länger.">
                <Switch an={e.denken} onChange={(v) => setze("denken", v)} label="Denkphase zulassen" />
              </Einstellung>
            </Card>
          </div>
        </div>
      </div>

      <div className="speicherleiste">
        <span className={`speicherzustand${geaendert ? " offen" : ""}`}>
          {geaendert ? <CircleDot aria-hidden /> : <CheckCircle2 aria-hidden />}
          {geaendert ? "Ungespeicherte Änderungen – gelten ab dem nächsten Abgleich" : "Gespeichert"}
        </span>
        {geaendert && <Button variante="ghost" onClick={() => setE(gespeichert)}>Verwerfen</Button>}
        <Button variante="primary" icon={Save} disabled={!geaendert || aendern.isPending} onClick={speichern}>Speichern</Button>
      </div>
    </div>
  );
}

const FAEHIGKEIT: Record<string, { text: string; icon: typeof Wrench; titel: string }> = {
  tools: { text: "Werkzeuge", icon: Wrench, titel: "Unterstützt Werkzeugaufrufe (Tool Calling) – nötig für LangChain-Agenten mit Werkzeugen" },
  vision: { text: "Bild", icon: Eye, titel: "Versteht Bilder" },
  thinking: { text: "Denken", icon: Sparkles, titel: "Thinking-Modell mit Denkphase" },
  insert: { text: "Code", icon: Cpu, titel: "Code-Vervollständigung" },
};

function Faehigkeiten({ f }: { f: string[] }) {
  const sichtbar = f.filter((x) => FAEHIGKEIT[x]);
  if (!sichtbar.length) return <span className="leise">–</span>;
  return (
    <span className="faehigkeiten">
      {sichtbar.map((x) => {
        const { text, icon: Icon, titel } = FAEHIGKEIT[x];
        return <span key={x} className="faehigkeit" title={titel}><Icon aria-hidden />{text}</span>;
      })}
    </span>
  );
}

function Standort({ m }: { m: Modell }) {
  if (m.standort === "cloud") return <Badge ton="warn" icon={Cloud} title="Anfragen verlassen den Rechner">Cloud</Badge>;
  if (m.standort === "netzwerk") return <Badge ton="warn" icon={Network} title="Läuft auf einem anderen Rechner im Netzwerk">Netzwerk</Badge>;
  return <Badge ton="ok" icon={Lock} title="Läuft auf diesem Rechner">lokal</Badge>;
}

function QuellenLeiste({ quellen, suchen, modellHost }: { quellen: ModellQuelle[]; suchen: boolean; modellHost: string }) {
  return (
    <div className="quellen-leiste">
      {quellen.map((q) => (
        <span key={q.schluessel} className={`quelle-chip${q.erreichbar ? " ok" : " fehler"}`} title={q.fehler || q.url}>
          <span className={`dot ${q.erreichbar ? "dot-ok" : "dot-danger"}`} />
          <QuellenLogo quelle={q.schluessel} art={q.art} />
          <b>{q.name}</b>
          <span className="leise">{q.erreichbar ? `${q.anzahl} ${q.anzahl === 1 ? "Modell" : "Modelle"}` : "nicht erreichbar"}</span>
        </span>
      ))}
      {suchen && <span className="klein leise">Außerdem gesucht auf {modellHost}: LM Studio, llama.cpp/LocalAI, Jan, GPT4All, text-generation-webui, KoboldCpp</span>}
    </div>
  );
}

function Verbindungen({ e, setze, ollamaFest, docker, modellHost }:
  { e: Entwurf; setze: <K extends keyof Entwurf>(k: K, v: Entwurf[K]) => void; ollamaFest: boolean; docker: boolean; modellHost: string }) {
  const [neu, setNeu] = useState({ name: "", url: "", api_schluessel: "" });
  const hinzufuegen = () => {
    if (!neu.name.trim() || !/^https?:\/\//.test(neu.url.trim())) return;
    setze("zusatz_server", [...e.zusatz_server, { name: neu.name.trim(), url: neu.url.trim(), api_schluessel: neu.api_schluessel }]);
    setNeu({ name: "", url: "", api_schluessel: "" });
  };
  return (
    <Card>
      <CardHead icon={Server} titel="Modellquellen" />
      <div className="card-body stapel-klein">
        <Feld label="Ollama-Adresse" htmlFor="t-url"
          hinweis={ollamaFest ? "Fest vorgegeben über HIPPOKRATES_OLLAMA_URL (z. B. in docker-compose.yml)." : docker ? "Im Container erreicht man den Host über host.docker.internal." : undefined}>
          <input id="t-url" value={e.ollama_url} disabled={ollamaFest} onChange={(v) => setze("ollama_url", v.target.value)} />
        </Feld>
      </div>
      <Einstellung icon={RefreshCw} titel="Lokale Modellserver automatisch suchen"
        text={`Prüft bei jeder Modellabfrage die üblichen Ports von LM Studio (1234), llama.cpp/LocalAI (8080), Jan (1337), GPT4All (4891), text-generation-webui (5000) und KoboldCpp (5001) auf ${modellHost}.`}>
        <Switch an={e.server_suchen} onChange={(v) => setze("server_suchen", v)} label="Lokale Modellserver automatisch suchen" />
      </Einstellung>
      <div className="card-body stapel-klein">
        <span className="feld-label">Weitere OpenAI-kompatible Server</span>
        {e.zusatz_server.map((s, i) => (
          <div key={s.url + i} className="server-zeile">
            <Server aria-hidden /><b>{s.name}</b><code className="ellipse">{s.url}</code>
            {s.api_schluessel && <Badge>mit Schlüssel</Badge>}
            <IconButton label={`${s.name} entfernen`} icon={Trash2} gefahr flach
              onClick={() => setze("zusatz_server", e.zusatz_server.filter((_, j) => j !== i))} />
          </div>
        ))}
        <div className="server-neu">
          <input placeholder="Name, z. B. vLLM" value={neu.name} onChange={(v) => setNeu({ ...neu, name: v.target.value })} aria-label="Servername" />
          <input placeholder="http://localhost:8000/v1" value={neu.url} onChange={(v) => setNeu({ ...neu, url: v.target.value })} aria-label="Server-Adresse" />
          <input placeholder="API-Schlüssel (optional)" type="password" value={neu.api_schluessel} onChange={(v) => setNeu({ ...neu, api_schluessel: v.target.value })} aria-label="API-Schlüssel" />
          <Button icon={Plus} onClick={hinzufuegen} disabled={!neu.name.trim() || !/^https?:\/\//.test(neu.url.trim())}>Hinzufügen</Button>
        </div>
        <p className="klein leise">Adressen außerhalb dieses Rechners werden als „Netzwerk“ bzw. „Cloud“ gekennzeichnet.</p>
      </div>
    </Card>
  );
}
