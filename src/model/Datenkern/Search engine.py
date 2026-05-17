import os
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.chat_models import init_chat_model


# === Variablen ===
FILE_PATH = "/home/alex/Dokumente/Github/Hippokrates/src/Docs/Max Mustermann/Max Mustermann_Skorbut.pdf"
LLM_MODEL = "gpt-oss"
EMBEDDING_MODEL = "snowflake-arctic-embed:335m"

file_path = FILE_PATH
loader = PyPDFLoader(file_path)

docs = loader.load()

print(len(docs))
print(f"{docs[0].page_content[:200]}\n")
print(docs[0].metadata)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000, chunk_overlap=200, add_start_index=True
)
all_splits = text_splitter.split_documents(docs)

print(len(all_splits))



embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL,
    encode_kwargs={"normalize_embeddings": True},
)

os.environ["HUGGINGFACEHUB_API_TOKEN"] = "hf_..."

model = init_chat_model(
    LLM_MODEL,
    model_provider="huggingface",
    temperature=0.7,
    max_tokens=1024,
)


vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_langchain_db",  # Where to save data locally, remove if not necessary
)