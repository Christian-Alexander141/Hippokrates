import { useRef, useState } from "react";
import {
  Award, BookOpen, BrainCircuit, CheckCircle2, FileWarning, Globe, Grid3x3, HelpCircle, ListChecks, RefreshCw, Search,
  Trash2, TriangleAlert, Upload,
} from "lucide-react";
import { useBibliothek, useBibliothekAktion, useEinstellungen, useEinstellungenAendern, useNetze } from "../api/hooks";
import type { Einstellungen, NetzInfo } from "../api/types";
import { groesse } from "../lib/format";
import { useBestaetigen, useFehlerToast, useToast } from "../components/rueckmeldung";
import { Badge, Banner, Card, CardHead, Einstellung, IconButton, Segmented, Spinner, Switch } from "../components/ui";

export function Admin() {
  const { data } = useEinstellungen();
  const aendern = useEinstellungenAendern();
  const fehler = useFehlerToast();
  const [gespeichert, setGespeichert] = useState(0);

  if (!data) return <div className="seite zentriert"><Spinner groesse="gross" /></div>;
  const e = data.einstellungen;
  const setzen = (werte: Partial<Einstellungen>) =>
    aendern.mutate(werte, { onSuccess: () => setGespeichert(Date.now()), onError: fehler });

  return (
    <div className="seite">
      <div className="seitenkopf">
        <div>
          <h2>Fachliche Vorgaben</h2>
          <p className="muted">Gelten für jeden künftigen Abgleich aller Patienten. Änderungen werden sofort gespeichert.</p>
        </div>
        <span key={gespeichert} className={`gespeichert${gespeichert ? " an" : ""}`}><CheckCircle2 aria-hidden />Gespeichert</span>
      </div>
      <div className="raster-2">
        <div className="stapel">
          <Fachbibliothek einst={e} setzen={setzen} />
          <Netze einst={e} setzen={setzen} />
        </div>
        <div className="stapel">
          <Card>
            <CardHead icon={Search} titel="Recherche der Agenten" />
            <Einstellung icon={Globe} titel="Internetrecherche in PubMed"
              text="Agenten dürfen zusätzlich in wissenschaftlichen Abstracts suchen (über Europe PMC) und diese als Beleg zitieren."
              warnung={<p className="warnung"><TriangleAlert aria-hidden />Dabei verlassen englische Suchbegriffe wie „scurvy gingival bleeding“ den Rechner – keine Namen, aber Symptomkombinationen.</p>}>
              <Switch an={e.internet} onChange={(v) => setzen({ internet: v })} label="Internetrecherche" />
            </Einstellung>
            <Einstellung icon={HelpCircle} titel="Rückfragen stellen"
              text="Agenten dürfen nach fehlenden Angaben fragen, die die Diagnose eingrenzen würden. Antworten fließen in den nächsten Abgleich ein.">
              <Switch an={e.rueckfragen} onChange={(v) => setzen({ rueckfragen: v })} label="Rückfragen" />
            </Einstellung>
          </Card>
          <Card>
            <CardHead icon={ListChecks} titel="Abgleich und Darstellung" />
            <Einstellung icon={RefreshCw} titel="Automatisch neu abgleichen" text="Jede gespeicherte Änderung an der Patientenakte startet sofort einen neuen Abgleich.">
              <Switch an={e.auto_abgleich} onChange={(v) => setzen({ auto_abgleich: v })} label="Automatisch neu abgleichen" />
            </Einstellung>
            <Einstellung icon={Award} titel="Diagnosen je Agent" text="Wie viele Differentialdiagnosen jeder Agent nennen soll.">
              <Segmented label="Diagnosen je Agent" wert={e.max_diagnosen} onChange={(v) => setzen({ max_diagnosen: v })}
                werte={[3, 5, 7, 10].map((n) => ({ wert: n, text: n }))} />
            </Einstellung>
            <Einstellung icon={Grid3x3} titel="Einzelnennungen einklappen" text="Diagnosen, die nur ein einziger Agent nennt, erscheinen eingeklappt unter der Rangliste.">
              <Switch an={e.einzelnennungen_einklappen} onChange={(v) => setzen({ einzelnennungen_einklappen: v })} label="Einzelnennungen einklappen" />
            </Einstellung>
          </Card>
        </div>
      </div>
    </div>
  );
}

type Setzen = (werte: Partial<Einstellungen>) => void;

function Fachbibliothek({ einst, setzen }: { einst: Einstellungen; setzen: Setzen }) {
  const { data: b } = useBibliothek();
  const { hochladen, loeschen, indexieren } = useBibliothekAktion();
  const toast = useToast();
  const fehler = useFehlerToast();
  const bestaetigen = useBestaetigen();
  const [drueber, setDrueber] = useState(false);
  const datei = useRef<HTMLInputElement>(null);
  const aus = new Set(einst.deaktivierte_buecher);

  const laden = (liste: File[]) => {
    const ok = liste.filter((d) => /\.(pdf|txt|md)$/i.test(d.name));
    if (!ok.length) return toast("Erlaubt sind PDF-, TXT- und MD-Dateien.", { fehler: true });
    hochladen.mutate(ok, {
      onSuccess: () => toast(ok.length === 1 ? `„${ok[0].name}“ hinzugefügt – wird indexiert` : `${ok.length} Fachbücher hinzugefügt – werden indexiert`),
      onError: fehler,
    });
  };
  const umschalten = (name: string, an: boolean) => {
    const neu = new Set(aus);
    if (an) neu.delete(name); else neu.add(name);
    setzen({ deaktivierte_buecher: [...neu] });
  };
  const entfernen = async (name: string) => {
    if (await bestaetigen({ titel: `„${name}“ entfernen?`, text: "Das Buch wird aus der Fachbibliothek und dem Suchindex gelöscht.", ok: "Entfernen", gefahr: true })) {
      loeschen.mutate(name, { onError: fehler });
    }
  };

  const s = b?.status;
  const aktiv = b?.dateien.filter((d) => !aus.has(d.name)).length ?? 0;
  return (
    <Card>
      <CardHead icon={BookOpen} titel="Fachbibliothek">
        {b && b.dateien.length > 0 && <span className="klein leise">{aktiv} von {b.dateien.length} berücksichtigt</span>}
        <IconButton label="Bibliotheksordner neu einlesen" icon={RefreshCw} onClick={() => indexieren.mutate(undefined, { onError: fehler })} />
      </CardHead>
      <div className="card-body stapel-klein">
        {b && !b.embedding_modell && <Banner ton="warn" icon={TriangleAlert}>Kein Embedding-Modell gewählt – Fachbücher werden erst nach Auswahl unter „Modelle & Technik“ indexiert.</Banner>}
        {s?.laeuft && (
          <div className="index-lauf">
            <Spinner groesse="klein" /><span className="ellipse">Indexiere {s.datei || "…"}</span><span className="klein tnum">{s.fertig} / {s.gesamt}</span>
            <div className="balken"><i style={{ width: `${s.gesamt ? (100 * s.fertig) / s.gesamt : 0}%` }} /></div>
          </div>
        )}
        {s?.fehler.filter((f) => !b!.dateien.some((d) => f.startsWith(`${d.name}: `))).map((f) => <Banner key={f} ton="danger" icon={FileWarning}>{f}</Banner>)}
        <label className={`ablage${drueber ? " drueber" : ""}`}
          onDragEnter={(ev) => { ev.preventDefault(); setDrueber(true); }} onDragOver={(ev) => { ev.preventDefault(); setDrueber(true); }}
          onDragLeave={() => setDrueber(false)} onDrop={(ev) => { ev.preventDefault(); setDrueber(false); laden([...ev.dataTransfer.files]); }}>
          <input ref={datei} type="file" multiple accept=".pdf,.txt,.md" hidden
            onChange={(ev) => { laden([...(ev.target.files ?? [])]); ev.target.value = ""; }} />
          {hochladen.isPending ? <Spinner /> : <Upload aria-hidden />}
          <b>Fachbücher hinzufügen</b>
          <span>Dateien hierher ziehen oder klicken · PDF mit Textebene, TXT, MD</span>
        </label>
        <div className="buecher">
          {b?.dateien.map((d) => {
            const an = !aus.has(d.name);
            return (
              <div key={d.name} className={`buch${an ? "" : " aus"}`}>
                <div className="buch-icon"><BookOpen aria-hidden /></div>
                <div className="buch-text">
                  <b title={d.name}>{d.name.replace(/\.(pdf|txt|md)$/i, "")}</b>
                  <small>
                    {d.name.split(".").pop()?.toUpperCase()} · {groesse(d.groesse)}{d.abschnitte ? ` · ${d.abschnitte} Abschnitte` : ""}
                    {d.fehler ? <Badge ton="danger">Fehler</Badge>
                      : s?.laeuft && s.datei === d.name ? <Badge ton="primary">wird indexiert</Badge>
                        : d.indexiert ? <Badge ton="ok" icon={CheckCircle2}>indexiert</Badge> : <Badge>ausstehend</Badge>}
                    {!an && <span>nicht berücksichtigt</span>}
                  </small>
                  {d.fehler && <small className="text-danger">{d.fehler}</small>}
                </div>
                <Switch an={an} onChange={(v) => umschalten(d.name, v)} label={`${d.name} berücksichtigen`} />
                <IconButton label={`${d.name} entfernen`} icon={Trash2} gefahr onClick={() => entfernen(d.name)} />
              </div>
            );
          })}
          {b && !b.dateien.length && <p className="klein muted zentriert-text" style={{ padding: "14px 0 4px" }}>Noch keine Fachbücher. Ohne Literatur stützen sich die Agenten nur auf ihr Modellwissen.</p>}
        </div>
        {b && <p className="klein leise">Nur eingeschaltete Bücher werden durchsucht. Speicherort: <code className="mono">{b.ordner}</code></p>}
      </div>
    </Card>
  );
}

function Netze({ einst, setzen }: { einst: Einstellungen; setzen: Setzen }) {
  const { data, isFetching, refetch } = useNetze();
  const aktiv = new Set(einst.netze_aktiv);
  const umschalten = (name: string, an: boolean) => {
    const neu = new Set(aktiv);
    if (an) neu.add(name); else neu.delete(name);
    setzen({ netze_aktiv: [...neu] });
  };
  const verschwunden = einst.netze_aktiv.filter((n) => data && !data.werkzeuge.some((w) => w.name === n));

  return (
    <Card>
      <CardHead icon={BrainCircuit} titel="Eigene neuronale Netze" zaehler={data?.werkzeuge.length}>
        <IconButton label="Netze-Ordner neu durchsuchen" icon={RefreshCw} onClick={() => refetch()} disabled={isFetching} />
      </CardHead>
      <div className="card-body stapel-klein">
        <p className="klein muted">
          Freigeschaltete Netze befragen die Agenten wie ein Werkzeug: Sie übertragen die Eingaben aus der Akte, das Netz
          rechnet lokal, das Ergebnis wird als Quelle zitiert. Neue Netze als <code className="mono">.py</code>-Datei in den
          Ordner legen – siehe <code className="mono">docs/eigene-netze.md</code>.
        </p>
        {data?.fehler.map((f) => <Banner key={f} ton="danger" icon={FileWarning}>{f}</Banner>)}
        {verschwunden.length > 0 && <Banner ton="warn" icon={TriangleAlert}>Freigeschaltet, aber nicht mehr vorhanden: {verschwunden.join(", ")}</Banner>}
        {data?.werkzeuge.map((n) => <NetzKarte key={n.name} n={n} an={aktiv.has(n.name)} umschalten={(v) => umschalten(n.name, v)} />)}
        {data && !data.werkzeuge.length && !data.fehler.length && <p className="klein muted zentriert-text">Keine Netze gefunden.</p>}
        {data && <p className="klein leise">Ordner: <code className="mono">{data.ordner}</code></p>}
      </div>
    </Card>
  );
}

function NetzKarte({ n, an, umschalten }: { n: NetzInfo; an: boolean; umschalten: (an: boolean) => void }) {
  return (
    <div className={`netz${an ? " an" : ""}`}>
      <div className="netz-kopf">
        <span className="netz-icon"><BrainCircuit aria-hidden /></span>
        <div className="ellipse" style={{ flex: 1 }}>
          <b className="mono">{n.name}</b>
          <small className="leise"> {n.version && `v${n.version} · `}{n.quelle}</small>
        </div>
        <Badge ton={n.art === "klassifikation" ? "info" : "neutral"}>{n.art}</Badge>
        <Switch an={an} onChange={umschalten} label={`${n.name} für Agenten freigeben`} />
      </div>
      <p className="klein">{n.beschreibung}</p>
      <div className="netz-details">
        <div><span className="feld-label">Eingaben</span>{n.eingaben.map((e) => <code key={e.name} title={e.beschreibung}>{e.name}</code>)}</div>
        {n.klassen.length > 0 && <div><span className="feld-label">Klassen</span>{n.klassen.map((k) => <span key={k} className="badge badge-umriss">{k}</span>)}</div>}
      </div>
      {n.hinweis && <p className="netz-hinweis"><TriangleAlert aria-hidden />{n.hinweis}</p>}
    </div>
  );
}
