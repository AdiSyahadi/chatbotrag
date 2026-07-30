from app.config import get_api_key, get_setting
from app.modules.vectorstore import get_retriever
from app.modules.conversation import format_history_for_prompt
from app.routes.system_prompt import DEFAULT_SYSTEM_PROMPT

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def get_prompt_template() -> str:
    """Baca system prompt dari database, fallback ke default."""
    custom = get_setting("system_prompt", "")
    return custom if custom else DEFAULT_SYSTEM_PROMPT


def build_question_with_history(question: str, history: list[dict]) -> str:
    """Sisipkan conversation history ke dalam question agar LLM punya konteks percakapan."""
    history_text = format_history_for_prompt(history)
    if not history_text:
        return question
    return f"Riwayat percakapan sebelumnya:\n{history_text}\n\nPertanyaan terbaru: {question}"


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def build_rag_chain():
    """Build RAG pipeline using LCEL: Retriever + Prompt + DeepSeek/Gemini LLM."""
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough

    api_key = get_api_key()
    if not api_key:
        raise ValueError("API key belum diatur. Silakan set di halaman Settings.")

    if api_key.startswith("AIzaSy"):
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.3,
        )
    else:
        llm = ChatOpenAI(
            model="deepseek-v4-flash",
            openai_api_key=api_key,
            openai_api_base=DEEPSEEK_BASE_URL,
            temperature=0.3,
        )

    prompt = ChatPromptTemplate.from_template(get_prompt_template())
    retriever = get_retriever()

    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain, retriever

def get_langfuse_handler(session_id: str = None):
    import os
    public_key = get_setting("langfuse_public_key")
    secret_key = get_setting("langfuse_secret_key")
    host = get_setting("langfuse_host", "https://cloud.langfuse.com")
    
    if public_key and secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
        os.environ["LANGFUSE_SECRET_KEY"] = secret_key
        os.environ["LANGFUSE_HOST"] = host
        try:
            from langfuse.langchain import CallbackHandler
            handler = CallbackHandler()
            return handler
        except Exception:
            return None
    return None
