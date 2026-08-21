import os
import logging
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

def get_llm(provider: str = None, model: str = None, temperature: float = 0.0) -> BaseChatModel:
    """
    Factory function to get the appropriate LLM based on environment configuration.
    Supports: groq, gemini, openai, anthropic, huggingface.
    """
    provider = provider or os.getenv("LLM_PROVIDER", "groq").lower()
    
    if provider == "groq":
        from langchain_groq import ChatGroq
        model = model or os.getenv("LLM_MODEL", "llama3-70b-8192")
        return ChatGroq(model=model, temperature=temperature)
        
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = model or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        return ChatGoogleGenerativeAI(model=model, temperature=temperature)
        
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        model = model or os.getenv("LLM_MODEL", "gpt-4o")
        return ChatOpenAI(model=model, temperature=temperature)
        
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        model = model or os.getenv("LLM_MODEL", "claude-3-5-sonnet-latest")
        return ChatAnthropic(model=model, temperature=temperature)
        
    elif provider == "nvidia":
        from langchain_nvidia_ai_endpoints import ChatNVIDIA
        model = model or os.getenv("LLM_MODEL", "meta/llama3-70b-instruct")
        return ChatNVIDIA(model=model, temperature=temperature)

    elif provider == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        model = model or os.getenv("LLM_MODEL", "meta-llama/Meta-Llama-3-70B-Instruct")
        llm = HuggingFaceEndpoint(repo_id=model, temperature=temperature)
        return ChatHuggingFace(llm=llm)
        
    else:
        logger.warning(f"Unknown LLM provider '{provider}', falling back to Groq.")
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama3-70b-8192", temperature=temperature)
