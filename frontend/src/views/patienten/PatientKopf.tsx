import { NavLink, Outlet, useNavigate } from "react-router";
import { Activity, AlertOctagon, CalendarDays, ClipboardList, Pill, RefreshCw } from "lucide-react";
import { useAbgleich, useAbgleichStarten, usePatient, usePatienten } from "../../api/hooks";
import { datum, zeit } from "../../lib/format";
import { useFehlerToast, useToast } from "../../components/rueckmeldung";
import { Avatar, Button, Leer, Spinner, ZustandBadge } from "../../components/ui";
import { usePatientId } from "./PatientenRahmen";

/** Klinischer Patientenkopf (Stammdaten, Allergien, Status) mit Reitern Diagnose | Patientenakte. */
export function PatientKopf() {
  const id = usePatientId();
  const { data: patient, isLoading, error } = usePatient(id);
  const { data: stand } = useAbgleich(id);
  const { data: liste } = usePatienten();
  const starten = useAbgleichStarten();
  const toast = useToast();
  const fehler = useFehlerToast();
  const navigate = useNavigate();

  if (isLoading) return <div className="seite zentriert"><Spinner groesse="gross" /></div>;
  if (error || !patient || id === null) {
    return (
      <div className="seite"><div className="card">
        <Leer icon={ClipboardList} titel="Patient nicht gefunden" text="Die Akte existiert nicht (mehr)."
          aktion={<Button onClick={() => navigate("/patienten")}>Zur Patientenliste</Button>} />
      </div></div>
    );
  }
  const eintrag = liste?.find((p) => p.id === id);
  const alter = stand?.patient.alter ?? eintrag?.alter;
  const allergien = patient.allergien.trim();
  const keineAllergien = /^(keine|nein|nkda|–|-)\b/i.test(allergien);
  const keineMedikation = /^(keine|nein|–|-)\b/i.test(patient.medikation.trim());
  const medikation = keineMedikation ? 0 : patient.medikation.trim().split(/\n|;/).filter((z) => z.trim()).length;

  return (
    <>
      <div className="patientkopf">
        <div className="patientkopf-zeile">
          <Avatar name={patient.name} gross />
          <div className="patientkopf-name">
            <h2>{patient.name}</h2>
            <div className="patientkopf-meta">
              {alter != null && <span><b>{alter}</b> Jahre</span>}
              {patient.geschlecht && <span>{patient.geschlecht}</span>}
              {patient.geburtsdatum && <span><CalendarDays aria-hidden />geb. {datum(patient.geburtsdatum)}</span>}
              <span className="leise">Akte geändert {zeit(patient.geaendert)}</span>
            </div>
          </div>
          <div className="patientkopf-aktionen">
            {eintrag && <ZustandBadge zustand={eintrag.zustand} />}
            {stand?.patient.hat_daten && (
              <Button variante="primary" icon={RefreshCw} disabled={starten.isPending}
                onClick={() => starten.mutate(id, { onSuccess: () => toast("Neuer Abgleich gestartet"), onError: fehler })}>
                Neu abgleichen
              </Button>
            )}
          </div>
        </div>
        <div className="patientkopf-flaggen">
          {allergien && !keineAllergien ? (
            <span className="flagge flagge-allergie" title={allergien}><AlertOctagon aria-hidden /><b>Allergien:</b><span className="ellipse">{allergien}</span></span>
          ) : (
            <span className="flagge"><AlertOctagon aria-hidden />{keineAllergien ? "Keine Allergien bekannt" : "Allergien nicht erfasst"}</span>
          )}
          <span className="flagge"><Pill aria-hidden />{medikation ? `${medikation} ${medikation === 1 ? "Dauermedikament" : "Dauermedikamente"}` : keineMedikation ? "Keine Dauermedikation" : "Dauermedikation nicht erfasst"}</span>
        </div>
        <nav className="reiter" aria-label="Patientenbereiche">
          <NavLink to={`/patienten/${id}/diagnose`}><Activity aria-hidden />Diagnose</NavLink>
          <NavLink to={`/patienten/${id}/akte`}><ClipboardList aria-hidden />Patientenakte</NavLink>
        </nav>
      </div>
      <Outlet />
    </>
  );
}
