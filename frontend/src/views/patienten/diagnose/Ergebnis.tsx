import type { CSSProperties } from "react";
import { Award, ChevronDown, Grid3x3, ListOrdered } from "lucide-react";
import type { Agent, KonsensGruppe, Lauf } from "../../../api/types";
import { agentFarbe, modellName, zahl } from "../../../lib/format";
import { quellTitel, zuQuelleSpringen, type Register } from "../../../lib/quellen";
import { AnbieterLogo } from "../../../lib/anbieter";
import { AgentBadge, Card, CardHead, Icd, Leer, Segmente } from "../../../components/ui";

const kurz = (m: string) => { const n = modellName(m); return n.length > 20 ? `${n.slice(0, 19)}…` : n; };

function Nennungen({ g, reg }: { g: KonsensGruppe; reg: Register }) {
  return (
    <div className="nennungen">
      {g.nennungen.map((n) => {
        const refs = n.quellen.map((q) => reg.ref(n.agent, q)).filter((x): x is number => x !== null);
        return (
          <div key={n.agent} className="nennung">
            <AgentBadge nr={n.agent} modell={n.modell} />
            <div>
              <div className="nennung-kopf">
                <AnbieterLogo modell={n.modell} groesse={14} />
                <code>{modellName(n.modell)}</code>
                <span>Platz {n.rang}</span>
                {n.name !== g.name && <span>als „{n.name}“</span>}
                {n.icd10 && n.icd10.toUpperCase() !== g.icd10 && <span className="mono">{n.icd10}</span>}
              </div>
              <p>{n.begruendung || <i className="leise">ohne Begründung</i>}</p>
              {refs.length > 0 && (
                <div className="refs">
                  {refs.map((nr) => (
                    <button key={nr} type="button" className="ref" title={quellTitel(reg.liste[nr - 1].q)} onClick={() => zuQuelleSpringen(nr)}>
                      [{nr}]
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Ring({ a, b }: { a: number; b: number }) {
  const r = 42;
  const u = 2 * Math.PI * r;
  const f = b ? a / b : 0;
  return (
    <div className="ring" role="img" aria-label={`${a} von ${b} Agenten`}>
      <svg viewBox="0 0 104 104">
        <circle cx="52" cy="52" r={r} fill="none" stroke="rgb(255 255 255 / 0.18)" strokeWidth="9" />
        <circle cx="52" cy="52" r={r} fill="none" stroke="#fff" strokeWidth="9" strokeLinecap="round"
          strokeDasharray={`${(u * f).toFixed(1)} ${u.toFixed(1)}`} />
      </svg>
      <div className="ring-text"><b>{a}/{b}</b><small>Agenten</small></div>
    </div>
  );
}

export function Ergebnis({ e, reg, einklappenErlaubt }: { e: Lauf; reg: Register; einklappenErlaubt: boolean }) {
  const k = e.konsens;
  const ag = e.agenten.filter((a) => a.status === "fertig");
  if (!k.length) return <Card><Leer icon={ListOrdered} titel="Keine Diagnosen" text="Die Agenten haben keine Diagnosen genannt." /></Card>;

  const einklappen = einklappenErlaubt && k[0].agenten_gesamt > 1;
  const ab1 = k.findIndex((g) => g.stimmen < 2);
  const grenze = einklappen && ab1 !== -1 ? Math.max(1, ab1) : k.length;
  const g = k[0];
  const genannt = new Set(g.nennungen.map((n) => n.agent));
  const satz = g.stimmen === g.agenten_gesamt && g.agenten_gesamt > 1
    ? `Übereinstimmend von allen ${g.agenten_gesamt} Agenten genannt` : `Von ${g.stimmen} der ${g.agenten_gesamt} Agenten genannt`;
  const weitere = k.slice(1, grenze);
  const einzeln = k.slice(grenze);

  return (
    <>
      <section className="hero" aria-label="Führende Diagnose">
        <div className="hero-oben">
          <div className="hero-text">
            <div className="eyebrow"><Award aria-hidden />Führende Diagnose</div>
            <h2>{g.name}</h2>
            <div className="hero-meta">
              {g.icd10 && <span className="hero-icd">{g.icd10}</span>}
              <span>{satz} · im Mittel Platz {zahl(g.mittlerer_rang)}</span>
            </div>
            <div className="hero-punkte">
              {ag.map((a) => (
                <span key={a.nr} className={`hero-punkt${genannt.has(a.nr) ? "" : " nein"}`} title={genannt.has(a.nr) ? "genannt" : "nicht genannt"}>
                  <AgentBadge nr={a.nr} modell={a.modell} /><AnbieterLogo modell={a.modell} groesse={14} />{kurz(a.modell)}
                </span>
              ))}
            </div>
          </div>
          <Ring a={g.stimmen} b={g.agenten_gesamt} />
        </div>
        <div className="hero-unten">
          <div className="unter-titel">Begründungen der Agenten</div>
          <Nennungen g={g} reg={reg} />
        </div>
      </section>

      {(weitere.length > 0 || einzeln.length > 0) && (
        <Card>
          <CardHead icon={ListOrdered} titel="Differentialdiagnosen"><span className="klein leise">nach Zustimmung, dann mittlerem Platz</span></CardHead>
          <div className="dd-liste">
            {weitere.map((x, i) => <Differential key={x.name} g={x} rang={i + 2} ag={ag} reg={reg} />)}
            {einzeln.length > 0 && (
              <details className="einzeln">
                <summary>
                  <ChevronDown className="pfeil" aria-hidden />
                  <span><b>{einzeln.length} {einzeln.length === 1 ? "Einzelnennung" : "Einzelnennungen"}</b> – nur von einem Agenten genannt</span>
                </summary>
                {einzeln.map((x, i) => <Differential key={x.name} g={x} rang={grenze + i + 1} ag={ag} reg={reg} />)}
              </details>
            )}
          </div>
        </Card>
      )}

      {ag.length > 1 && <Matrix k={k} ag={ag} />}
    </>
  );
}

function Differential({ g, rang, ag, reg }: { g: KonsensGruppe; rang: number; ag: Agent[]; reg: Register }) {
  const genannt = new Set(g.nennungen.map((n) => n.agent));
  const alias = [...new Set(g.nennungen.map((n) => n.name).filter((n) => n !== g.name))];
  return (
    <details className="dd">
      <summary>
        <span className="rang">{rang}</span>
        <span className="dd-name">
          <span className="zeile"><b>{g.name}</b><Icd code={g.icd10} /></span>
          {alias.length > 0 && <small>auch als: {alias.join(", ")}</small>}
        </span>
        <span className="zust"><Segmente agenten={ag} genannt={genannt} /><small className="tnum">{g.stimmen}/{g.agenten_gesamt}</small></span>
        <ChevronDown className="pfeil" aria-hidden />
      </summary>
      <div className="dd-inhalt"><Nennungen g={g} reg={reg} /></div>
    </details>
  );
}

function Matrix({ k, ag }: { k: KonsensGruppe[]; ag: Agent[] }) {
  return (
    <Card>
      <CardHead icon={Grid3x3} titel="Übereinstimmungsmatrix"><span className="klein leise">Zahl = Listenplatz beim jeweiligen Agenten</span></CardHead>
      <div className="tabelle-huelle">
        <table className="matrix">
          <thead>
            <tr>
              <th>Diagnose</th>
              {ag.map((a) => (
                <th key={a.nr}>
                  <span className="matrix-kopf"><AgentBadge nr={a.nr} modell={a.modell} /><AnbieterLogo modell={a.modell} /></span>
                  <small title={a.modell}>{kurz(a.modell)}</small>
                </th>
              ))}
              <th>Zustimmung</th>
            </tr>
          </thead>
          <tbody>
            {k.map((g, i) => (
              <tr key={g.name}>
                <td><span className="m-rang">{i + 1}</span>{g.name}</td>
                {ag.map((a) => {
                  const n = g.nennungen.find((x) => x.agent === a.nr);
                  if (!n) return <td key={a.nr}><span className="zelle ohne">–</span></td>;
                  const s = [100, 78, 60, 46, 36][Math.min(n.rang, 5) - 1];
                  return (
                    <td key={a.nr}>
                      <span className={`zelle${s < 60 ? " hell" : ""}`} style={{ "--c": agentFarbe(a.nr), "--s": `${s}%` } as CSSProperties}
                        title={`${modellName(a.modell)}: Platz ${n.rang}${n.name !== g.name ? ` als „${n.name}“` : ""}`}>{n.rang}</span>
                    </td>
                  );
                })}
                <td className="tnum"><b>{g.stimmen}</b>/{g.agenten_gesamt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
