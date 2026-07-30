import json
from app.config import get_db_connection, get_api_key

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

def run_ragas_evaluation(limit: int = 10) -> dict:
    """Run RAGAS evaluation on the latest N evaluations from the database."""
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_openai import ChatOpenAI
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_huggingface import HuggingFaceEmbeddings
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT question, answer, source_documents FROM evaluations ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    
    if not rows:
        conn.close()
        return {"error": "Tidak ada data evaluasi yang tersedia untuk diuji."}

    questions = []
    answers = []
    contexts_list = []

    for row in rows:
        questions.append(row["question"])
        answers.append(row["answer"])
        
        # Parse source_documents JSON
        try:
            sources = json.loads(row["source_documents"])
            contexts = [src["content"] for src in sources]
        except Exception:
            contexts = []
            
        contexts_list.append(contexts)

    # Create HuggingFace Dataset
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts_list
    }
    dataset = Dataset.from_dict(data)

    # Setup LLM and Embeddings for RAGAS (LLM-as-a-Judge)
    api_key = get_api_key()
    if not api_key:
        conn.close()
        return {"error": "API key belum diatur."}

    if api_key.startswith("AIzaSy"):
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
    else:
        # Wrap ChatOpenAI to remove 'n' parameter because DeepSeek API rejects n > 1
        class DeepSeekChatOpenAI(ChatOpenAI):
            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                n = kwargs.pop('n', 1)
                res = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                if n > 1 and res.generations:
                    res.generations = res.generations * n
                return res
            
            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                n = kwargs.pop('n', 1)
                res = await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
                if n > 1 and res.generations:
                    res.generations = res.generations * n
                return res

        llm = DeepSeekChatOpenAI(
            model="deepseek-v4-flash",
            openai_api_key=api_key, 
            openai_api_base=DEEPSEEK_BASE_URL
        )
        # Fallback to local embeddings if using DeepSeek since it doesn't have an embedding API mapped here by default
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Setup RAGAS metrics constraints for DeepSeek
    answer_relevancy.strictness = 1
    
    # Run evaluation
    try:
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=llm,
            embeddings=embeddings,
        )
        
        # Extract mean scores (handling EvaluationResult which doesn't have .get())
        try:
            f_score = float(result["faithfulness"])
        except Exception:
            f_score = 0.0
            
        try:
            ar_score = float(result["answer_relevancy"])
        except Exception:
            ar_score = 0.0
            
        if f_score != f_score: f_score = 0.0 # Check for NaN
        if ar_score != ar_score: ar_score = 0.0
        
        # Save to database
        cursor.execute(
            "INSERT INTO ragas_evaluations (faithfulness, answer_relevancy, samples_count) VALUES (?, ?, ?)",
            (f_score, ar_score, len(rows))
        )
        conn.commit()
        
        res = {
            "faithfulness": round(f_score, 4),
            "answer_relevancy": round(ar_score, 4),
            "samples_count": len(rows)
        }
    except Exception as e:
        res = {"error": str(e)}
        
    conn.close()
    return res

def get_ragas_history():
    """Retrieve historical RAGAS evaluation scores for the dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT evaluated_at, faithfulness, answer_relevancy, samples_count FROM ragas_evaluations ORDER BY id ASC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
