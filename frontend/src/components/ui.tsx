import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import type { Zustand } from "../api/types";
import { agentFarbe, farbton, initialen, modellName, ZUSTAND } from "../lib/format";

type Variante = "primary" | "secondary" | "ghost" | "danger";

export function Button({ variante = "secondary", klein, block, icon: Icon, children, className = "", ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; klein?: boolean; block?: boolean; icon?: LucideIcon }) {
  const k = ["btn", variante !== "secondary" && `btn-${variante}`, klein && "btn-sm", block && "btn-block", className]
    .filter(Boolean).join(" ");
  return (
    <button type="button" className={k} {...rest}>
      {Icon && <Icon aria-hidden />}
      {children}
    </button>
  );
}

export function IconButton({ label, icon: Icon, gefahr, flach, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { label: string; icon: LucideIcon; gefahr?: boolean; flach?: boolean }) {
  return (
    <button type="button" className={`icon-btn${gefahr ? " gefahr" : ""}${flach ? " flach" : ""}`} title={label}
      aria-label={label} {...rest}>
      <Icon aria-hidden />
    </button>
  );
}

export function Badge({ ton = "neutral", icon: Icon, children, title, umriss }:
  { ton?: string; icon?: LucideIcon; children: ReactNode; title?: string; umriss?: boolean }) {
  return (
    <span className={`badge badge-${ton}${umriss ? " badge-umriss" : ""}`} title={title}>
      {Icon && <Icon aria-hidden />}
      {children}
    </span>
  );
}

export function ZustandBadge({ zustand }: { zustand: Zustand }) {
  const z = ZUSTAND[zustand] ?? { ton: "neutral", text: zustand };
  return (
    <span className={`badge badge-${z.ton}`}>
      {zustand === "laufend" && <span className="spinner klein" />}
      {z.text}
    </span>
  );
}

export function ZustandPunkt({ zustand }: { zustand: Zustand }) {
  const k = { aktuell: "ok", veraltet: "warn", fehler: "danger", laufend: "primary", leer: "leer" }[zustand as string] ?? "";
  return <span className={`dot ${k ? `dot-${k}` : ""}`} title={ZUSTAND[zustand]?.text} />;
}

export function Spinner({ groesse }: { groesse?: "klein" | "gross" }) {
  return <span className={`spinner ${groesse ?? ""}`} role="status" aria-label="lädt" />;
}

export function Avatar({ name, gross }: { name: string; gross?: boolean }) {
  return (
    <span className={`avatar${gross ? " gross" : ""}`} style={{ "--h": farbton(name) } as CSSProperties} aria-hidden>
      {initialen(name)}
    </span>
  );
}

export function AgentBadge({ nr, modell }: { nr: number; modell?: string }) {
  return (
    <span className="agent-badge" style={{ "--c": agentFarbe(nr) } as CSSProperties}
      title={`Agent ${nr}${modell ? ` · ${modellName(modell)}` : ""}`}>
      A{nr}
    </span>
  );
}

export function Icd({ code }: { code: string }) {
  return code ? <span className="icd">{code}</span> : null;
}

export function Card({ children, className = "", ...rest }: { children: ReactNode; className?: string; id?: string }) {
  return <section className={`card ${className}`} {...rest}>{children}</section>;
}

export function CardHead({ icon: Icon, titel, zaehler, children }:
  { icon?: LucideIcon; titel: ReactNode; zaehler?: number; children?: ReactNode }) {
  return (
    <header className="card-head">
      <h3>{Icon && <Icon aria-hidden />}{titel}</h3>
      {zaehler ? <span className="zaehler">{zaehler}</span> : null}
      {children && <div className="rechts">{children}</div>}
    </header>
  );
}

export function Switch({ an, onChange, label, disabled }:
  { an: boolean; onChange: (an: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <label className="switch" title={label}>
      <input type="checkbox" role="switch" checked={an} disabled={disabled} aria-label={label}
        onChange={(e) => onChange(e.target.checked)} />
      <span />
    </label>
  );
}

export function Segmented<T extends string | number>({ werte, wert, onChange, label }:
  { werte: { wert: T; text: ReactNode; icon?: LucideIcon }[]; wert: T; onChange: (w: T) => void; label: string }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {werte.map(({ wert: w, text, icon: Icon }) => (
        <button key={String(w)} type="button" role="radio" aria-checked={w === wert} className={w === wert ? "an" : ""}
          onClick={() => onChange(w)}>
          {Icon && <Icon aria-hidden />}{text}
        </button>
      ))}
    </div>
  );
}

export function Banner({ ton, icon: Icon, children, aktion }:
  { ton: "warn" | "danger" | "info" | "ok"; icon: LucideIcon; children: ReactNode; aktion?: ReactNode }) {
  return (
    <div className={`banner banner-${ton}`} role={ton === "danger" ? "alert" : undefined}>
      <Icon aria-hidden />
      <div className="banner-text">{children}</div>
      {aktion && <div className="banner-aktion">{aktion}</div>}
    </div>
  );
}

export function Leer({ icon: Icon, titel, text, aktion }:
  { icon: LucideIcon; titel: string; text: ReactNode; aktion?: ReactNode }) {
  return (
    <div className="leer">
      <div className="leer-icon"><Icon aria-hidden /></div>
      <h3>{titel}</h3>
      <p>{text}</p>
      {aktion}
    </div>
  );
}

export function Einstellung({ icon: Icon, titel, text, warnung, children }:
  { icon?: LucideIcon; titel: string; text?: ReactNode; warnung?: ReactNode; children: ReactNode }) {
  return (
    <div className="setting">
      {Icon && <span className="setting-icon"><Icon aria-hidden /></span>}
      <div className="setting-text">
        <b>{titel}</b>
        {text && <p>{text}</p>}
        {warnung}
      </div>
      {children}
    </div>
  );
}

export function Feld({ label, hinweis, children, breit, htmlFor }:
  { label: string; hinweis?: ReactNode; children: ReactNode; breit?: boolean; htmlFor?: string }) {
  return (
    <div className={`feld${breit ? " breit" : ""}`}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hinweis && <span className="feld-hinweis">{hinweis}</span>}
    </div>
  );
}

export function Segmente({ agenten, genannt }: { agenten: { nr: number; modell: string }[]; genannt: Set<number> }) {
  return (
    <span className="segmente" style={{ "--w": agenten.length > 6 ? "9px" : "14px" } as CSSProperties}>
      {agenten.map((a) => (
        <i key={a.nr} className={genannt.has(a.nr) ? "ja" : ""} style={{ "--c": agentFarbe(a.nr) } as CSSProperties}
          title={`A${a.nr} ${modellName(a.modell)}${genannt.has(a.nr) ? "" : " – nicht genannt"}`} />
      ))}
    </span>
  );
}
