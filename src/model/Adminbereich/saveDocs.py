from pathlib import Path
import shutil

# Pfad zum Skript-Verzeichnis
SKRIPT_PFAD = Path(__file__).parent  

# Pfade relativ zum Skript
DOCS_PFAD = SKRIPT_PFAD / "Docs"
TEST_PFAD = SKRIPT_PFAD / "TEST"

def save_docs(docs: list[Path], Patientenname: str, PatienID: str) -> None:
    unterordner = DOCS_PFAD / Patientenname
    unterordner.mkdir(parents=True, exist_ok=True)

    for doc in docs:
        ziel_pfad = unterordner / f"{Patientenname}_{doc.name}"
        shutil.copy2(doc, ziel_pfad)
        print(f"Kopiert: {doc} -> {ziel_pfad}")

def main():
    docs = [datei for datei in TEST_PFAD.iterdir() if datei.is_file()]
    if not docs:
        print(f"Keine Dateien in {TEST_PFAD} gefunden!")
        return
    save_docs(docs, "Max Mustermann", "123456789")

if __name__ == "__main__":
    main()