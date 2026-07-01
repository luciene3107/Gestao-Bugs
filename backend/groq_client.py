"""
Integração com a Groq API (modelos LLaMA) para gerar resumos e classificação
das falhas de teste em linguagem natural.

A chave da API deve ser definida na variável de ambiente GROQ_API_KEY.
Caso não esteja configurada, o sistema usa um resumo heurístico simples
como fallback (o app continua funcionando sem IA generativa).
"""
import os
import json
from groq import Groq

GROQ_MODEL = "openai/gpt-oss-120b"

_client = None


def _get_client():
    global _client
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    if _client is None:
        _client = Groq(api_key=api_key)
    return _client


def summarize_cluster(failures_in_cluster: list[dict], heuristic_classification: str) -> dict:
    """
    Usa a LLaMA (via Groq) para gerar um resumo em português e confirmar/ajustar
    a classificação do cluster de falhas. Retorna dict com 'summary' e 'classification'.
    """
    client = _get_client()

    if client is None:
        return {
            "summary": _fallback_summary(failures_in_cluster, heuristic_classification),
            "classification": heuristic_classification,
        }

    error_samples = "\n".join(f"- {f['test_name']}: {f['error_message']}" for f in failures_in_cluster[:5])

    prompt = f"""Você é um assistente de QA que analisa falhas de testes automatizados (Cypress/Tosca).

Abaixo estão {len(failures_in_cluster)} falhas de teste agrupadas por similaridade de mensagem de erro:

{error_samples}

Classificação heurística preliminar: {heuristic_classification}

Responda APENAS com um JSON válido, sem markdown, sem texto adicional, no formato:
{{"classification": "Bug Real" | "Flaky Test" | "Problema de Ambiente", "summary": "resumo curto em português (1-2 frases) explicando a provável causa raiz e recomendação"}}
"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        return {
            "summary": parsed.get("summary", _fallback_summary(failures_in_cluster, heuristic_classification)),
            "classification": parsed.get("classification", heuristic_classification),
        }
    except Exception:
        return {
            "summary": _fallback_summary(failures_in_cluster, heuristic_classification),
            "classification": heuristic_classification,
        }


def _fallback_summary(failures_in_cluster: list[dict], classification: str) -> str:
    count = len(failures_in_cluster)
    suites = {f.get("suite", "N/A") for f in failures_in_cluster}
    suite_txt = ", ".join(suites)
    sample_error = failures_in_cluster[0]["error_message"]
    return (
        f"{count} falha(s) na(s) suíte(s) {suite_txt}, provavelmente com a mesma causa raiz. "
        f"Mensagem representativa: \"{sample_error[:120]}\". Classificação sugerida: {classification}."
    )
