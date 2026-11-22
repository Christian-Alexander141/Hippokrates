import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import { Activity, BookOpen, Bot, BrainCircuit, Clock, FileText, Globe, Info, RefreshCw, TriangleAlert } from "lucide-react";
import { useAbgleich, useAbgleichStarten, useEinstellungen } from "../../../api/hooks";
import type { Lauf } from "../../../api/types";
import { dauer, modellName, zeit } from "../../../lib/format";
import { quellenRegister } from "../../../lib/quellen";
import { useFehlerToast, useToast } from "../../../components/rueckmeldung";
import { Banner, Button, Card, Leer, Spinner } from "../../../components/ui";
import { Hinweis } from "../../Uebersicht";
import { usePatientId } from "../PatientenRahmen";
import { Ergebnis } from "./Ergebnis";
import { Fortschritt } from "./Fortschritt";
import { AgentenDetails, Quellen, Rueckfragen } from "./Seitenleiste";

export function Diagnose() {
  const id = usePatientId()!;
  const { data: stand, isLoading } = useAbgleich(id);
  const { data: einst } = useEinstellungen();
  const starten = useAbgleichStarten();
  const toast = useToast();
  const fehler = useFehlerToast();
  const navigate = useNavigate();

  if (isLoading || !stand) return <div className="seite zentriert"><Spinner groesse="gross" /></div>;
  const { patient: p, lauf, ergebnis: e } = stand;
  const laeuft = lauf?.status === "laufend";
  const abgleichen = () => starten.mutate(id, { onSuccess: () => toast("Neuer Abgleich gestartet"), onError: fehler });
  const neuKnopf = (text: string) => (
    <Button klein icon={RefreshCw} disabled={starten.isPending} onClick={abgleichen}>{text}</Button>
  );

  const banner: ReactNode[] = [];
  if (lauf && !laeuft && lauf.status !== "fertig") {
    const ausfaelle = lauf.agenten.filter((a) => a.fehler);
    banner.push(
      <Banner key="lauf" ton={lauf.status === "fehler" ? "danger" : "warn"} icon={TriangleAlert}
        aktion={p.hat_daten ? neuKnopf("Erneut versuchen") : undefined}>
        <b>Der letzte Abgleich ist {lauf.status === "fehler" ? "fehlgeschlagen" : "abgebrochen"}.</b> {lauf.meldung}
        {ausfaelle.length > 0 && <ul>{ausfaelle.map((a) => <li key={a.nr}>A{a.nr} {modellName(a.modell)}: {a.fehler}</li>)}</ul>}
      </Banner>,
    );
  } else if (lauf?.meldung && !laeuft) {
    banner.push(<Banner key="meldung" ton="warn" icon={TriangleAlert}>{lauf.meldung}</Banner>);
  }
  if (e && !e.aktuell && !laeuft) {
    banner.push(
      <Banner key="alt" ton="warn" icon={Clock} aktion={neuKnopf("Jetzt abgleichen")}>
        Dieses Ergebnis beruht auf einem älteren Stand der Patientenakte.
      </Banner>,
    );
  }

  return (
    <div className="seite">
      <div className="stapel">
        {laeuft && lauf && <Fortschritt lauf={lauf} />}
        {banner}
        {!e && !laeuft && (
          <Card>
            {p.hat_daten
              ? <Leer icon={Activity} titel="Noch kein Abgleich" text="Starten Sie den Abgleich – die Agenten recherchieren dann unabhängig voneinander."
                  aktion={<Button variante="primary" icon={RefreshCw} onClick={abgleichen}>Abgleich starten</Button>} />
              : <Leer icon={FileText} titel="Noch keine klinischen Angaben"
                  text="Erfassen Sie Beschwerden, Befunde und Vorgeschichte in der Patientenakte. Der Abgleich startet danach automatisch."
                  aktion={<Button variante="primary" onClick={() => navigate(`/patienten/${id}/akte`)}>Patientenakte öffnen</Button>} />}
          </Card>
        )}
        {e && (
          <>
            {laeuft && <p className="hinweis-zeile"><Info aria-hidden />Darunter das letzte abgeschlossene Ergebnis – es wird ersetzt, sobald der neue Abgleich fertig ist.</p>}
            <RahmenChips e={e} />
            <ErgebnisRaster e={e} patientId={id} gedimmt={laeuft} einklappen={!!einst?.einstellungen.einzelnennungen_einklappen} />
          </>
        )}
      </div>
      <Hinweis />
    </div>
  );
}

function ErgebnisRaster({ e, patientId, gedimmt, einklappen }: { e: Lauf; patientId: number; gedimmt: boolean; einklappen: boolean }) {
  const reg = quellenRegister(e);
  return (
    <div className={`diagnose-raster${gedimmt ? " gedimmt" : ""}`}>
      <div className="stapel"><Ergebnis e={e} reg={reg} einklappenErlaubt={einklappen} /></div>
      <aside className="stapel">
        <Rueckfragen e={e} patientId={patientId} />
        <Quellen reg={reg} e={e} />
        <AgentenDetails e={e} />
      </aside>
    </div>
  );
}

function RahmenChips({ e }: { e: Lauf }) {
  const r = e.rahmen;
  const ok = e.agenten.filter((a) => a.status === "fertig").length;
  const b = r?.buecher ?? [];
  const n = r?.netze ?? [];
  return (
    <div className="rahmen">
      <span className="chip an" title={e.agenten.map((a) => `A${a.nr}: ${a.modell}`).join("\n")}>
        <Bot aria-hidden /><b>{ok}</b>&nbsp;von {e.agenten.length} Agenten{r?.agenten_modus === "alle" ? " · alle lokalen Modelle" : ""}
      </span>
      {r && <span className={`chip${b.length ? " an" : ""}`} title={b.join("\n")}><BookOpen aria-hidden />{b.length ? <><b>{b.length}</b>&nbsp;{b.length === 1 ? "Fachbuch" : "Fachbücher"}</> : "ohne Fachbücher"}</span>}
      {r && <span className={`chip${r.internet ? " an" : ""}`}><Globe aria-hidden />{r.internet ? "mit PubMed-Recherche" : "ohne Internetrecherche"}</span>}
      {n.length > 0 && <span className="chip an" title={n.join("\n")}><BrainCircuit aria-hidden /><b>{n.length}</b>&nbsp;{n.length === 1 ? "eigenes Netz" : "eigene Netze"}</span>}
      <span className="chip"><Clock aria-hidden />{zeit(e.beendet)} · {dauer(e.gestartet, e.beendet)}</span>
    </div>
  );
}
