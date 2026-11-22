import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import {
  Activity, Cpu, LayoutDashboard, Monitor, Moon, Plus, RefreshCw, Search, ShieldAlert, ShieldCheck, SlidersHorizontal,
  Sun, Users,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { schluessel, useEinstellungen, useModelle, usePatienten } from "../../api/hooks";
import { relativ, uhrzeit } from "../../lib/format";
import { useThema } from "../../lib/thema";
import { Button } from "../ui";
import { Schnellsuche } from "./Schnellsuche";

const TITEL: [RegExp, string][] = [
  [/^\/$/, "Übersicht"],
  [/^\/patienten\/neu/, "Neuer Patient"],
  [/^\/patienten\/\d+\/akte/, "Patientenakte"],
  [/^\/patienten\/\d+/, "Diagnose"],
  [/^\/patienten/, "Patienten"],
  [/^\/admin/, "Adminbereich"],
  [/^\/technik/, "Modelle & Technik"],
];

export function AppRahmen() {
  const { data: patienten = [] } = usePatienten();
  const laufend = patienten.filter((p) => p.zustand === "laufend").length;
  const [suche, setSuche] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    const taste = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSuche((s) => !s); }
    };
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, []);

  const titel = TITEL.find(([r]) => r.test(pathname))?.[1] ?? "Hippokrates";
  useEffect(() => { document.title = `${titel} · Hippokrates`; }, [titel]);

  return (
    <div className="shell">
      <nav className="rail" aria-label="Hauptnavigation">
        <div className="marke">
          <span className="logo"><Activity aria-hidden /></span>
          <div><b>Hippokrates</b><small>Diagnose-Konsens</small></div>
        </div>
        <NavLink to="/" end><LayoutDashboard aria-hidden /><span>Übersicht</span></NavLink>
        <NavLink to="/patienten"><Users aria-hidden /><span>Patienten</span>
          {laufend > 0 && <em className="rail-zahl" title={`${laufend} Abgleiche laufen`}>{laufend}</em>}</NavLink>
        <div className="rail-gruppe">Verwaltung</div>
        <NavLink to="/admin"><SlidersHorizontal aria-hidden /><span>Adminbereich</span></NavLink>
        <NavLink to="/technik"><Cpu aria-hidden /><span>Modelle & Technik</span></NavLink>
        <RailFuss />
      </nav>

      <div className="inhalt">
        <header className="topbar">
          <h1 className="topbar-titel">{titel}</h1>
          <button type="button" className="suchfeld-knopf" onClick={() => setSuche(true)}>
            <Search aria-hidden /><span>Patient oder Bereich suchen …</span><kbd>Strg K</kbd>
          </button>
          <div className="topbar-rechts">
            <ModellStatus />
            <ThemaKnopf />
            <Button variante="primary" icon={Plus} onClick={() => navigate("/patienten/neu")}>
              <span className="nur-breit">Neuer Patient</span>
            </Button>
          </div>
        </header>
        <Outlet />
      </div>
      <Schnellsuche offen={suche} schliessen={() => setSuche(false)} />
    </div>
  );
}

function ModellStatus() {
  const { data, isFetching, dataUpdatedAt } = useModelle();
  const { data: einst } = useEinstellungen();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const ollama = data?.quellen.find((q) => q.art === "ollama");
  const chat = data?.modelle.filter((m) => !m.embedding) ?? [];
  const cloudAgent = einst?.einstellungen.agenten_modus === "auswahl"
    && einst.einstellungen.agenten.some((id) => data?.modelle.find((m) => m.id === id)?.cloud);
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick((x) => x + 1), 10_000); return () => clearInterval(t); }, []);

  return (
    <div className="modellstatus">
      <button type="button" className={`modellstatus-chip ${!ollama ? "" : ollama.erreichbar ? "ok" : "fehler"}`}
        onClick={() => navigate("/technik")}
        title={data ? `Zuletzt geprüft ${uhrzeit(data.geprueft)} – ${data.quellen.map((q) => `${q.name}: ${q.erreichbar ? `${q.anzahl} Modelle` : "nicht erreichbar"}`).join(", ")}` : "Prüfe Modelle …"}>
        <span className={`dot ${!ollama ? "" : ollama.erreichbar ? "dot-ok" : "dot-danger"}`} />
        <span className="nur-breit">
          {!data ? "Prüfe Modelle …" : ollama?.erreichbar ? `${chat.length} Sprachmodelle verfügbar` : "Ollama nicht erreichbar"}
        </span>
        <small className="leise nur-breit">{dataUpdatedAt ? relativ(new Date(dataUpdatedAt).toISOString()) : ""}</small>
      </button>
      <button type="button" className="icon-btn flach" aria-label="Modelle neu prüfen" title="Modelle neu prüfen"
        onClick={() => qc.invalidateQueries({ queryKey: schluessel.modelle })}>
        <RefreshCw aria-hidden className={isFetching ? "dreht" : ""} />
      </button>
      {cloudAgent
        ? <span className="datenschutz warn" title="Mindestens ein Agent nutzt ein Cloud- oder Netzwerkmodell – Patientendaten verlassen den Rechner."><ShieldAlert aria-hidden /></span>
        : <span className="datenschutz" title="Alle Agenten arbeiten mit Modellen auf diesem Rechner."><ShieldCheck aria-hidden /></span>}
    </div>
  );
}

function ThemaKnopf() {
  const [thema, weiter] = useThema();
  const Icon = thema === "hell" ? Sun : thema === "dunkel" ? Moon : Monitor;
  const text = { system: "Farbschema: wie System", hell: "Farbschema: hell", dunkel: "Farbschema: dunkel" }[thema];
  return <button type="button" className="icon-btn flach" onClick={weiter} title={text} aria-label={text}><Icon aria-hidden /></button>;
}

function RailFuss() {
  const { data } = useEinstellungen();
  if (!data) return <div className="rail-fuss" />;
  const e = data.einstellungen;
  const anzahl = e.agenten_modus === "alle"
    ? data.modelle.filter((m) => !m.embedding && !m.cloud && !e.ausgeschlossene_modelle.includes(m.id)).length
    : e.agenten.length;
  return (
    <div className="rail-fuss">
      <b>{anzahl} {anzahl === 1 ? "Agent" : "Agenten"}{e.agenten_modus === "alle" ? " · alle lokalen" : ""}</b>
      <span>{e.internet ? "mit" : "ohne"} PubMed · {e.netze_aktiv.length} {e.netze_aktiv.length === 1 ? "Netz" : "Netze"}</span>
      <span>{data.umgebung.docker ? "Docker · Modelle vom Host" : "Lokal · 127.0.0.1"}</span>
    </div>
  );
}
