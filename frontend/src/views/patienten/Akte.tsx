import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useBlocker, useNavigate } from "react-router";
import {
  Activity, CheckCircle2, CircleDot, ClipboardList, FlaskConical, HelpCircle, Home, Lock, Save, Trash2, User,
  type LucideIcon,
} from "lucide-react";
import { useEinstellungen, usePatient, usePatientLoeschen, usePatientSpeichern } from "../../api/hooks";
import type { PatientDaten } from "../../api/types";
import { useBestaetigen, useFehlerToast, useToast } from "../../components/rueckmeldung";
import { Avatar, Button, Feld, Spinner } from "../../components/ui";
import { usePatientId } from "./PatientenRahmen";

const LEER: PatientDaten = {
  name: "", geburtsdatum: "", geschlecht: "", anamnese: "", befunde: "", vorerkrankungen: "", medikation: "",
  allergien: "", familienanamnese: "", sozialanamnese: "", ergaenzungen: "",
};
const FELDER = Object.keys(LEER) as (keyof PatientDaten)[];

/** Formular für neue (/patienten/neu) und bestehende Akten (/patienten/:id/akte). */
export function Akte() {
  const id = usePatientId();
  const { data: patient, isLoading } = usePatient(id);
  if (id !== null && (isLoading || !patient)) return <div className="seite zentriert"><Spinner groesse="gross" /></div>;
  return <AkteFormular key={`${id ?? "neu"}-${patient?.geaendert ?? ""}`} id={id} ursprung={patient ?? LEER} />;
}

function AkteFormular({ id, ursprung }: { id: number | null; ursprung: PatientDaten }) {
  const start = useMemo(() => Object.fromEntries(FELDER.map((f) => [f, ursprung[f] ?? ""])) as unknown as PatientDaten, [ursprung]);
  const [werte, setWerte] = useState<PatientDaten>(start);
  const geaendert = FELDER.some((f) => werte[f] !== start[f]);
  const speichern = usePatientSpeichern();
  const loeschen = usePatientLoeschen();
  const { data: einst } = useEinstellungen();
  const bestaetigen = useBestaetigen();
  const toast = useToast();
  const fehler = useFehlerToast();
  const navigate = useNavigate();
  const formular = useRef<HTMLFormElement>(null);
  const erlaubt = useRef(false); // nach dem Speichern darf ohne Rückfrage navigiert werden

  const sperre = useBlocker(({ currentLocation, nextLocation }) =>
    geaendert && !erlaubt.current && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (sperre.state !== "blocked") return;
    bestaetigen({ titel: "Ungespeicherte Änderungen verwerfen?", text: "Die Änderungen an der Patientenakte gehen verloren.", ok: "Verwerfen", gefahr: true })
      .then((ja) => (ja ? sperre.proceed() : sperre.reset()));
  }, [sperre, bestaetigen]);
  useEffect(() => {
    const vorEntladen = (e: BeforeUnloadEvent) => { if (geaendert) e.preventDefault(); };
    window.addEventListener("beforeunload", vorEntladen);
    return () => window.removeEventListener("beforeunload", vorEntladen);
  }, [geaendert]);
  useEffect(() => {
    const taste = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); formular.current?.requestSubmit(); }
    };
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, []);

  const setze = (f: keyof PatientDaten) => (e: { target: { value: string } }) => setWerte((w) => ({ ...w, [f]: e.target.value }));
  const absenden = (ev: React.FormEvent) => {
    ev.preventDefault();
    speichern.mutate({ id, daten: werte }, {
      onSuccess: (r) => {
        erlaubt.current = true;
        toast(r.abgleich_gestartet ? "Gespeichert – die Agenten recherchieren" : "Gespeichert",
          { aktion: { text: "Zur Diagnose", fn: () => navigate(`/patienten/${r.patient.id}/diagnose`) } });
        if (!id) navigate(`/patienten/${r.patient.id}/akte`, { replace: true });
      },
      onError: fehler,
    });
  };
  const entfernen = async () => {
    if (!id || !(await bestaetigen({ titel: `„${start.name}“ endgültig löschen?`, text: "Die Akte wird mit allen Abgleichen dauerhaft von diesem Rechner entfernt.", ok: "Löschen", gefahr: true }))) return;
    loeschen.mutate(id, {
      onSuccess: () => { erlaubt.current = true; toast("Patient gelöscht"); navigate("/patienten"); },
      onError: fehler,
    });
  };

  return (
    <div className="seite">
      <form ref={formular} onSubmit={absenden} autoComplete="off" className="stapel">
        {!id && (
          <div className="seitenkopf">
            <Avatar name={werte.name || "?"} gross />
            <div><h2>{werte.name.trim() || "Neuer Patient"}</h2><p className="muted">Pflichtangabe ist nur der Name.</p></div>
          </div>
        )}
        <Abschnitt icon={User} titel="Stammdaten" text={<><Lock aria-hidden className="inline-icon" />Der Name bleibt auf diesem Rechner und wird nie an ein Sprachmodell übergeben.</>}>
          <div className="felder stamm">
            <Feld label="Name *" htmlFor="f-name"><input id="f-name" required value={werte.name} onChange={setze("name")} autoFocus={!id} /></Feld>
            <Feld label="Geburtsdatum" htmlFor="f-geb"><input id="f-geb" type="date" value={werte.geburtsdatum} onChange={setze("geburtsdatum")} /></Feld>
            <Feld label="Geschlecht" htmlFor="f-geschlecht">
              <select id="f-geschlecht" value={werte.geschlecht} onChange={setze("geschlecht")}>
                <option value="">–</option><option>weiblich</option><option>männlich</option><option>divers</option>
              </select>
            </Feld>
          </div>
        </Abschnitt>
        <Abschnitt icon={Activity} titel="Aktuelle Beschwerden" text="Hauptsymptome, Beginn, Verlauf, Begleitsymptome – je genauer, desto besser grenzen die Agenten ein.">
          <textarea className="gross" aria-label="Aktuelle Beschwerden" value={werte.anamnese} onChange={setze("anamnese")}
            placeholder="z. B. Seit sechs Wochen zunehmende Müdigkeit, Zahnfleischbluten beim Zähneputzen …" />
        </Abschnitt>
        <Abschnitt icon={FlaskConical} titel="Befunde und Laborwerte" text="Untersuchungsbefunde und Laborwerte mit Einheit – eigene neuronale Netze lesen ihre Eingaben von hier.">
          <textarea aria-label="Befunde und Laborwerte" value={werte.befunde} onChange={setze("befunde")}
            placeholder="z. B. Hb 10,9 g/dl, MCV 74 fl, CRP 8 mg/l, Petechien an beiden Unterschenkeln …" />
        </Abschnitt>
        <Abschnitt icon={ClipboardList} titel="Vorgeschichte" text="Bekannte Erkrankungen, Medikamente und Unverträglichkeiten.">
          <div className="felder">
            <Feld label="Vorerkrankungen"><textarea value={werte.vorerkrankungen} onChange={setze("vorerkrankungen")} placeholder="ggf. mit ICD-10-Code" /></Feld>
            <Feld label="Dauermedikation"><textarea value={werte.medikation} onChange={setze("medikation")} placeholder="Wirkstoff · Dosis · Einnahme – je Zeile ein Medikament" /></Feld>
            <Feld label="Allergien und Unverträglichkeiten" breit>
              <textarea style={{ minHeight: 50 }} value={werte.allergien} onChange={setze("allergien")} placeholder="z. B. Penicillin (Exanthem) – oder „keine bekannt“" />
            </Feld>
          </div>
        </Abschnitt>
        <Abschnitt icon={Home} titel="Familie und Lebensumstände" text="Erkrankungen in der Familie, Beruf, Ernährung, Rauchen, Alkohol, Reisen.">
          <div className="felder">
            <Feld label="Familienanamnese"><textarea value={werte.familienanamnese} onChange={setze("familienanamnese")} /></Feld>
            <Feld label="Sozialanamnese und Risikofaktoren"><textarea value={werte.sozialanamnese} onChange={setze("sozialanamnese")} /></Feld>
          </div>
        </Abschnitt>
        <Abschnitt icon={HelpCircle} titel="Ergänzungen" text="Antworten auf Rückfragen der Agenten werden hier automatisch eingetragen.">
          <textarea aria-label="Ergänzungen" value={werte.ergaenzungen} onChange={setze("ergaenzungen")} />
        </Abschnitt>

        <div className="speicherleiste">
          <span className={`speicherzustand${geaendert ? " offen" : ""}`}>
            {geaendert ? <CircleDot aria-hidden /> : <CheckCircle2 aria-hidden />}
            {geaendert
              ? `Ungespeicherte Änderungen${einst?.einstellungen.auto_abgleich ? " – Speichern startet einen neuen Abgleich" : ""}`
              : id ? "Alle Änderungen gespeichert" : "Neue Akte"}
          </span>
          {geaendert && <Button variante="ghost" onClick={() => setWerte(start)}>Verwerfen</Button>}
          <button type="submit" className="btn btn-primary" disabled={speichern.isPending}>
            <Save aria-hidden />Speichern <kbd className="kbd-hell">Strg S</kbd>
          </button>
        </div>
        {id && (
          <div className="gefahrenzone">
            <div><b>Patient löschen</b><p>Entfernt die Akte mit allen Abgleichen dauerhaft von diesem Rechner.</p></div>
            <Button variante="danger" icon={Trash2} onClick={entfernen}>Löschen</Button>
          </div>
        )}
      </form>
    </div>
  );
}

function Abschnitt({ icon: Icon, titel, text, children }: { icon: LucideIcon; titel: string; text: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <header className="abschnitt-kopf">
        <span className="setting-icon"><Icon aria-hidden /></span>
        <div><h3>{titel}</h3><p>{text}</p></div>
      </header>
      <div className="card-body">{children}</div>
    </section>
  );
}
