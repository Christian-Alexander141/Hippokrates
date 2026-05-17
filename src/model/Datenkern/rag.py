import os
from langchain_ollama import ChatOllama
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


class RAG:  
    # === Technische Konstanten ===
    EMBEDDING_MODEL = "snowflake-arctic-embed:335m"
    RERANKING_MODEL = "fed"
    MODEL           = "gpt-oss"
    CHROMA_PFAD     =  "chroma_db"

    # === Patienteninformationen ===
    Patientname = "Max Mustermann"
    PatienID    = "123456789"

    # === user input ===
    Symptome = "Ich habe seit 12 Stunden starke Bauchschmerzen, die im rechten Unterbauch lokalisiert sind. Was könnte das sein?"


    def __init__(self, Patientname: str, PatienID: str):
        self._rag = {}
        self.Patientname = Patientname
        self.PatienID = PatienID
 
        # === Initialisierung der ChromaDB ===
        if self.is_chroma_db_existing(self.CHROMA_PFAD):
            print("ChromaDB existiert bereits.")
        else:
            print("ChromaDB existiert nicht.")
            print("Erstelle ChromaDB...")
            self.create_chroma_db()
        
        #=== Initialisierung des LLMs ===
        self.llm = ChatOllama(
            model=self.MODEL,
            temperature=0
        )


    # === Hilfsfunktionen ===
    def is_chroma_db_existing(db_path: str = "./chroma_db") -> bool:
    #Prüft, ob eine ChromaDB-Datenbank im angegebenen Pfad existiert.
        return os.path.exists(db_path) and os.path.isdir(db_path)
    
    def create_chroma_db(self) -> None:
    # Erstellt eine ChromaDB-Datenbank mit dem angegebenen Pfad 
        try:        
            embedding = self.EMBEDDING_MODEL
            Chroma(
                collection_name="medizinische_fakten",
                embedding_function=self.EMBEDDING_MODEL,
                persist_directory=self.CHROMA_PFAD
            )
        except (ValueError, FileNotFoundError):
            print("Fehler: Ungültiges Embedding-Modell oder Pfad nicht gefunden.")
        
    # === Hauptfunktionen ===
    def send_msg(self) -> str:  
        messages = [
            ("system", "Du bist ein Medizinischer Assistent und unterstützt beim Finden der richtigen Diagnose. Du beantwortest die Fragen so kurz wie möglich und gibst nur die Informationen weiter, die für die Diagnose relevant sind. Du stellst keine Fragen, sondern beantwortest nur die Fragen, die dir gestellt werden."),
            ("user", self.Symptome),
        ]

        ai_msg = self.llm(messages)  
        return ai_msg
    
    
    
