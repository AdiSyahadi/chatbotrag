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

    valid_rows = []
    questions = []
    answers = []
    contexts_list = []

    for row in rows:
        # Parse source_documents JSON
        try:
            sources = json.loads(row["source_documents"])
            contexts = [src["content"] for src in sources]
        except Exception:
            contexts = []
            
        if not contexts:
            continue # Skip invalid evaluation data without references
            
        questions.append(row["question"])
        answers.append(row["answer"])
        contexts_list.append(contexts)
        valid_rows.append(row)
        
    if not valid_rows:
        conn.close()
        return {"error": "Tidak ada data evaluasi valid dengan referensi dokumen (contexts) yang ditemukan."}

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
        # Fallback to local embeddings for non-Google LLMs
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        if api_key.startswith("gsk_"):
            llm = ChatOpenAI(model="llama3-8b-8192", openai_api_key=api_key, openai_api_base="https://api.groq.com/openai/v1")
        elif api_key.startswith("sk-") and len(api_key) == 35:
            # Wrap ChatOpenAI to support n > 1 for DeepSeek API using parallel asyncio tasks
            class DeepSeekChatOpenAI(ChatOpenAI):
                def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                    n = kwargs.pop('n', 1)
                    if n == 1:
                        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                    
                    final_res = None
                    generations = []
                    for _ in range(n):
                        res = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                        if final_res is None: 
                            final_res = res
                        generations.extend(res.generations)
                    
                    if final_res:
                        final_res.generations = generations
                    return final_res
                
                async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                    n = kwargs.pop('n', 1)
                    if n == 1:
                        return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
                    
                    import asyncio
                    _super_agenerate = super()._agenerate
                    tasks = [_super_agenerate(messages, stop=stop, run_manager=run_manager, **kwargs) for _ in range(n)]
                    results = await asyncio.gather(*tasks)
                    
                    final_res = results[0]
                    generations = []
                    for res in results:
                        generations.extend(res.generations)
                    
                    final_res.generations = generations
                    return final_res
                    
            llm = DeepSeekChatOpenAI(
                model="deepseek-chat",
                openai_api_key=api_key, 
                openai_api_base=DEEPSEEK_BASE_URL
            )
        else:
            llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=api_key)

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
            (f_score, ar_score, len(valid_rows))
        )
        conn.commit()
        
        res = {
            "faithfulness": round(f_score, 4),
            "answer_relevancy": round(ar_score, 4),
            "samples_count": len(valid_rows)
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
