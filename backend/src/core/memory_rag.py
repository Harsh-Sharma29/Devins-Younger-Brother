import os
import logging
from typing import Dict, List, Optional
import chromadb
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Try to initialize the embeddings. Fallback or disable RAG if not configured.
_embeddings = None
_chroma_client = None
_collection = None

def _get_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings
    
    api_key = os.getenv("HUGGINGFACEHUB_API_TOKEN", "").strip()
    if not api_key:
        logger.warning("HUGGINGFACEHUB_API_TOKEN not found. RAG memory will be disabled.")
        return None
    
    try:
        _embeddings = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            huggingfacehub_api_token=api_key,
        )
        return _embeddings
    except Exception as e:
        logger.error(f"Failed to initialize HuggingFace Embeddings: {e}")
        return None

def _get_collection():
    global _chroma_client, _collection
    if _collection is not None:
        return _collection
    
    embeddings = _get_embeddings()
    if not embeddings:
        return None
        
    try:
        # Use PersistentClient to save data to the mounted docker volume
        chroma_path = "/app/chroma_data"
        _chroma_client = chromadb.PersistentClient(path=chroma_path)
        
        # We need a custom embedding function adapter for Chroma since it expects a specific interface,
        # but LangChain embeddings can be adapted easily.
        class LangchainEmbeddingAdapter(chromadb.EmbeddingFunction):
            def __init__(self, lc_embeddings):
                self.lc_embeddings = lc_embeddings
                
            def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
                return self.lc_embeddings.embed_documents(input)
                
        adapter = LangchainEmbeddingAdapter(embeddings)
        _collection = _chroma_client.get_or_create_collection(
            name="autoforge_workspace",
            embedding_function=adapter
        )
        return _collection
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB collection: {e}")
        return None


def index_workspace(workspace_files: Dict[str, str], thread_id: str) -> None:
    """
    Chunks and stores the given workspace files into ChromaDB.
    """
    collection = _get_collection()
    if not collection:
        return
        
    if not workspace_files:
        return
        
    logger.info(f"Indexing {len(workspace_files)} files into RAG memory for thread {thread_id}...")
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    
    documents = []
    metadatas = []
    ids = []
    
    for filename, content in workspace_files.items():
        if not content.strip():
            continue
            
        chunks = splitter.split_text(content)
        for i, chunk in enumerate(chunks):
            chunk_text = f"File: {filename}\n\n{chunk}"
            documents.append(chunk_text)
            metadatas.append({
                "filename": filename,
                "thread_id": thread_id,
                "chunk_index": i
            })
            ids.append(f"{thread_id}_{filename}_{i}")
            
    if documents:
        try:
            # We upsert to overwrite existing chunks if the file was updated
            collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info("RAG indexing complete.")
        except Exception as e:
            logger.error(f"Failed to upsert chunks into ChromaDB: {e}")


def retrieve_context(query: str, thread_id: str, k: int = 5) -> str:
    """
    Retrieves the top-k most relevant code chunks for the given query.
    Filters by thread_id to keep sessions isolated (or you can remove the filter for global memory).
    """
    collection = _get_collection()
    if not collection:
        return ""
        
    if not query.strip():
        return ""
        
    try:
        # Search the vector database
        results = collection.query(
            query_texts=[query],
            n_results=k,
            where={"thread_id": thread_id}
        )
        
        if not results or not results["documents"] or not results["documents"][0]:
            return ""
            
        retrieved_chunks = results["documents"][0]
        
        context_str = "--- PREVIOUS KNOWLEDGE & CONTEXT (RAG MEMORY) ---\n"
        for i, chunk in enumerate(retrieved_chunks):
            context_str += f"[Chunk {i+1}]\n{chunk}\n\n"
            
        return context_str.strip()
        
    except Exception as e:
        logger.error(f"Failed to retrieve context from ChromaDB: {e}")
        return ""
