import { useState } from "react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router";
import { Plus, Search, Users } from "lucide-react";
import { usePatienten } from "../../api/hooks";
import { personMeta, ZUSTAND } from "../../lib/format";
import { Avatar, IconButton, Leer, Spinner, ZustandPunkt } from "../../components/ui";

/** Patientenliste links, gewählter Patient rechts. */
export function PatientenRahmen() {
  const { data: patienten, isLoading } = usePatienten();
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const s = q.trim().toLowerCase();
  const treffer = (patienten ?? []).filter((p) => !s || p.name.toLowerCase().includes(s) || p.geburtsdatum.includes(s)
    || p.diagnosen.some((d) => d.name.toLowerCase().includes(s) || d.icd10.toLowerCase().includes(s)));

  return (
    <div className="mit-liste">
      <aside className="plist" aria-label="Patientenliste">
        <div className="plist-kopf">
          <h2>Patienten <small>{patienten?.length || ""}</small></h2>
          <IconButton label="Neuer Patient" icon={Plus} onClick={() => navigate("/patienten/neu")} />
        </div>
        <label className="plist-suche">
          <Search aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, Geburtsdatum, Diagnose" aria-label="Patienten filtern" />
        </label>
        <ul>
          {isLoading && <li className="plist-leer"><Spinner /></li>}
          {treffer.map((p) => {
            const d = p.diagnosen[0];
            const unter = p.zustand === "laufend" ? "Agenten recherchieren …"
              : d ? `${d.name} · ${d.stimmen}/${d.agenten_gesamt}` : ZUSTAND[p.zustand].text;
            return (
              <li key={p.id}>
                <NavLink to={`/patienten/${p.id}`} className="plist-eintrag">
                  <Avatar name={p.name} />
                  <span className="plist-text">
                    <b>{p.name}</b>
                    <small>{personMeta(p) || "ohne Stammdaten"}</small>
                    <small className="plist-diag">{unter}</small>
                  </span>
                  <ZustandPunkt zustand={p.zustand} />
                </NavLink>
              </li>
            );
          })}
          {!isLoading && !treffer.length && (
            <li className="plist-leer">{patienten?.length ? "Keine Treffer" : "Noch keine Patienten angelegt"}</li>
          )}
        </ul>
      </aside>
      <main className="haupt">
        <Outlet />
      </main>
    </div>
  );
}

export function KeinPatient() {
  const navigate = useNavigate();
  return (
    <div className="seite">
      <div className="card">
        <Leer icon={Users} titel="Kein Patient geöffnet" text="Wählen Sie links einen Patienten oder legen Sie einen neuen an."
          aktion={<button type="button" className="btn btn-primary" onClick={() => navigate("/patienten/neu")}><Plus aria-hidden />Neuer Patient</button>} />
      </div>
    </div>
  );
}

export function usePatientId(): number | null {
  const { id } = useParams();
  return id && /^\d+$/.test(id) ? Number(id) : null;
}
