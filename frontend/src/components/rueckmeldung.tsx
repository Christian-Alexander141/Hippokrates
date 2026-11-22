import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, HelpCircle, XCircle } from "lucide-react";
import { Button } from "./ui";

// ── Toasts ───────────────────────────────────────────────────────────────────

interface Toast { id: number; text: string; fehler?: boolean; aktion?: { text: string; fn: () => void } }
type ToastFn = (text: string, optionen?: { fehler?: boolean; aktion?: Toast["aktion"] }) => void;

const ToastKontext = createContext<ToastFn>(() => {});
export const useToast = () => useContext(ToastKontext);

// ── Bestätigung ──────────────────────────────────────────────────────────────

interface Frage { titel: string; text?: ReactNode; ok?: string; gefahr?: boolean }
type BestaetigenFn = (frage: Frage) => Promise<boolean>;

const DialogKontext = createContext<BestaetigenFn>(async () => false);
export const useBestaetigen = () => useContext(DialogKontext);

export function RueckmeldungProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [frage, setFrage] = useState<(Frage & { antwort: (ja: boolean) => void }) | null>(null);
  const zaehler = useRef(0);

  const toast = useCallback<ToastFn>((text, optionen = {}) => {
    const id = ++zaehler.current;
    setToasts((t) => [...t.slice(-2), { id, text, ...optionen }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), optionen.aktion ? 6500 : 3800);
  }, []);

  const bestaetigen = useCallback<BestaetigenFn>(
    (f) => new Promise((resolve) => setFrage({ ...f, antwort: (ja) => { setFrage(null); resolve(ja); } })), []);

  return (
    <ToastKontext.Provider value={toast}>
      <DialogKontext.Provider value={bestaetigen}>
        {children}
        <div className="toasts" role="status" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className={`toast${t.fehler ? " fehler" : ""}`}>
              {t.fehler ? <XCircle aria-hidden /> : <CheckCircle2 aria-hidden />}
              <span>{t.text}</span>
              {t.aktion && (
                <button type="button" onClick={() => { setToasts((x) => x.filter((y) => y.id !== t.id)); t.aktion!.fn(); }}>
                  {t.aktion.text}
                </button>
              )}
            </div>
          ))}
        </div>
        {frage && <Dialog frage={frage} />}
      </DialogKontext.Provider>
    </ToastKontext.Provider>
  );
}

function Dialog({ frage }: { frage: Frage & { antwort: (ja: boolean) => void } }) {
  const okRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    okRef.current?.focus();
    const taste = (e: KeyboardEvent) => { if (e.key === "Escape") frage.antwort(false); };
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, [frage]);
  const Icon = frage.gefahr ? AlertTriangle : HelpCircle;
  return (
    <div className="dialog-hintergrund" onMouseDown={(e) => e.target === e.currentTarget && frage.antwort(false)}>
      <div className="dialog" role="alertdialog" aria-modal="true" aria-labelledby="dialog-titel">
        <div className="dialog-inhalt">
          <span className={`dialog-icon${frage.gefahr ? " gefahr" : ""}`}><Icon aria-hidden /></span>
          <div>
            <h2 id="dialog-titel">{frage.titel}</h2>
            {frage.text && <p>{frage.text}</p>}
          </div>
        </div>
        <div className="dialog-aktionen">
          <Button variante="ghost" onClick={() => frage.antwort(false)}>Abbrechen</Button>
          <button ref={okRef} type="button" className={`btn ${frage.gefahr ? "btn-danger" : "btn-primary"}`}
            onClick={() => frage.antwort(true)}>
            {frage.ok ?? "OK"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Fehler einer Mutation als Toast zeigen. */
export function useFehlerToast() {
  const toast = useToast();
  return useCallback((e: unknown) => toast(e instanceof Error ? e.message : String(e), { fehler: true }), [toast]);
}
