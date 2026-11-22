// Datentypen der Python-Schnittstelle (src/main.py). Namen bleiben deutsch wie im Backend.

export type Zustand = "aktuell" | "veraltet" | "laufend" | "fehler" | "abgebrochen" | "ohne" | "leer";
export type AgentStatus = "wartend" | "laufend" | "fertig" | "fehler" | "abgebrochen";
export type Schritt = "startet" | "plant" | "bibliothek" | "internet" | "netze" | "diagnose" | "";

export interface PatientDaten {
  name: string;
  geburtsdatum: string;
  geschlecht: string;
  anamnese: string;
  befunde: string;
  vorerkrankungen: string;
  medikation: string;
  allergien: string;
  familienanamnese: string;
  sozialanamnese: string;
  ergaenzungen: string;
}

export interface Patient extends PatientDaten {
  id: number;
  geaendert: string;
}

export interface KurzDiagnose {
  name: string;
  icd10: string;
  stimmen: number;
  agenten_gesamt: number;
}

export interface PatientEintrag {
  id: number;
  name: string;
  geburtsdatum: string;
  geschlecht: string;
  alter: number | null;
  geaendert: string;
  zustand: Zustand;
  abgeglichen: string | null;
  diagnosen: KurzDiagnose[];
}

export interface Quelle {
  nr: number;
  art: "buch" | "web" | "netz";
  id?: number | string;
  text: string;
  // Fachbuch
  datei?: string;
  seite?: number | null;
  aehnlichkeit?: number;
  // PubMed
  titel?: string;
  fundstelle?: string;
  url?: string;
  // eigenes Netz
  netz?: string;
  eingabe?: Record<string, unknown>;
  netz_art?: "klassifikation" | "regression" | "frei";
  vorhersagen?: { bezeichnung: string; wert: number; einheit: string }[];
  hinweis?: string;
  version?: string;
}

export interface AgentDiagnose {
  name: string;
  icd10: string;
  begruendung: string;
  quellen: number[];
}

export interface Agent {
  id: number;
  nr: number;
  modell: string;
  status: AgentStatus;
  schritt: Schritt;
  suchanfragen: { art: "buch" | "web" | "netz"; text: string }[];
  quellen: Quelle[];
  diagnosen: AgentDiagnose[];
  rueckfragen: string[];
  hinweise: string[];
  fehler: string | null;
  dauer: number | null;
}

export interface Nennung {
  agent: number;
  modell: string;
  rang: number;
  name: string;
  icd10: string;
  begruendung: string;
  quellen: number[];
}

export interface KonsensGruppe {
  name: string;
  icd10: string;
  stimmen: number;
  agenten_gesamt: number;
  mittlerer_rang: number;
  nennungen: Nennung[];
}

export interface Rahmen {
  agenten: string[];
  agenten_modus?: "auswahl" | "alle";
  buecher: string[];
  internet: boolean;
  rueckfragen: boolean;
  max_diagnosen: number;
  netze?: string[];
}

export interface Lauf {
  id: number;
  patient_id: number;
  daten_hash: string;
  status: "laufend" | "fertig" | "fehler" | "abgebrochen";
  meldung: string;
  gestartet: string;
  beendet: string | null;
  konsens: KonsensGruppe[];
  rahmen: Rahmen | null;
  agenten: Agent[];
  rueckfragen: { frage: string; agenten: number[] }[];
  aktuell: boolean;
}

export interface AbgleichStand {
  patient: Patient & { alter: number | null; hat_daten: boolean };
  lauf: Lauf | null;
  ergebnis: Lauf | null;
}

export interface Modell {
  id: string;
  name: string;
  quelle: string;
  quelle_name: string;
  standort: "lokal" | "netzwerk" | "cloud";
  cloud: boolean;
  embedding: boolean;
  faehigkeiten: string[];
  groesse: number;
  parameter: string;
  quantisierung: string;
  familie: string;
}

export interface ModellQuelle {
  schluessel: string;
  name: string;
  art: "ollama" | "openai" | "netz";
  url: string;
  auto: boolean;
  erreichbar: boolean;
  fehler: string;
  anzahl: number;
}

export interface ModellListe {
  modelle: Modell[];
  quellen: ModellQuelle[];
  geprueft: string;
}

export interface ZusatzServer {
  name: string;
  url: string;
  api_schluessel: string;
}

export interface Einstellungen {
  ollama_url: string;
  agenten: string[];
  agenten_modus: "auswahl" | "alle";
  ausgeschlossene_modelle: string[];
  server_suchen: boolean;
  zusatz_server: ZusatzServer[];
  embedding_modell: string;
  top_k: number;
  parallel: number;
  icd_abgleich: boolean;
  denken: boolean;
  max_diagnosen: number;
  deaktivierte_buecher: string[];
  internet: boolean;
  rueckfragen: boolean;
  auto_abgleich: boolean;
  einzelnennungen_einklappen: boolean;
  netze_aktiv: string[];
}

export interface Umgebung {
  ollama_url_fest: boolean;
  docker: boolean;
  modell_host: string;
}

export interface EinstellungenAntwort extends ModellListe {
  einstellungen: Einstellungen;
  ollama_fehler: string;
  umgebung: Umgebung;
}

export interface Buch {
  name: string;
  groesse: number;
  abschnitte: number;
  indexiert: boolean;
  aktiv: boolean;
  fehler: string;
}

export interface Bibliothek {
  dateien: Buch[];
  status: { laeuft: boolean; datei: string; fertig: number; gesamt: number; fehler: string[] };
  ordner: string;
  embedding_modell: string;
}

export interface NetzInfo {
  name: string;
  beschreibung: string;
  quelle: string;
  art: "klassifikation" | "regression" | "frei";
  klassen: string[];
  ausgaben: string[];
  version: string;
  hinweis: string;
  eingaben: { name: string; typ: string; beschreibung: string }[];
}

export interface NetzUebersicht {
  verfuegbar: boolean;
  ordner: string;
  werkzeuge: NetzInfo[];
  chatmodelle: { name: string; quelle: string }[];
  fehler: string[];
}
