"""
Módulo de similaridade textual e clusterização de falhas de teste.

Implementa três métricas de similaridade (comparadas entre si):
- TF-IDF + Cosine Similarity: usada como base para o clustering (captura similaridade
  semântica/lexical geral entre mensagens de erro)
- Levenshtein (edit distance): captura o quão "perto" duas strings estão caractere a
  caractere — útil para detectar mensagens quase idênticas (ex: só muda o seletor CSS)
- Jaccard: captura sobreposição de tokens (palavras) entre duas mensagens, ignorando
  ordem e repetição

O clustering final usa TF-IDF + Cosine (via DBSCAN), e as métricas de Levenshtein e
Jaccard são calculadas para fins de comparação/relatório.
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
import numpy as np


def _normalize_error_message(msg: str) -> str:
    """Remove partes muito variáveis (números, hex, timestamps) para melhorar a similaridade."""
    msg = re.sub(r"\d+ms", "Nms", msg)
    msg = re.sub(r"\$[\d,.]+", "$VALOR", msg)
    msg = re.sub(r"0x[0-9a-fA-F]+", "0xHEX", msg)
    msg = re.sub(r"\b\d+\b", "N", msg)
    return msg


def levenshtein_distance(a: str, b: str) -> int:
    """Distância de edição clássica (programação dinâmica)."""
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        current_row = [i + 1]
        for j, cb in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (ca != cb)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def levenshtein_similarity(a: str, b: str) -> float:
    """Normaliza a distância de Levenshtein em uma similaridade de 0 a 1."""
    if not a and not b:
        return 1.0
    dist = levenshtein_distance(a, b)
    max_len = max(len(a), len(b))
    return 1 - (dist / max_len) if max_len > 0 else 1.0


def jaccard_similarity(a: str, b: str) -> float:
    """Similaridade de Jaccard sobre o conjunto de tokens (palavras) das duas strings."""
    tokens_a = set(re.findall(r"\w+", a.lower()))
    tokens_b = set(re.findall(r"\w+", b.lower()))
    if not tokens_a and not tokens_b:
        return 1.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def cluster_failures(failures: list[dict], eps: float = 0.45, min_samples: int = 1) -> list[int]:
    """
    Agrupa falhas por similaridade de mensagem de erro usando TF-IDF + Cosine + DBSCAN.
    Retorna uma lista de cluster_id (mesmo tamanho de `failures`, na mesma ordem).
    """
    messages = [_normalize_error_message(f["error_message"]) for f in failures]

    if len(messages) == 1:
        return [0]

    vectorizer = TfidfVectorizer(stop_words=None, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(messages)

    similarity_matrix = cosine_similarity(tfidf_matrix)
    distance_matrix = 1 - similarity_matrix
    distance_matrix = np.clip(distance_matrix, 0, None)  # evitar negativos por arredondamento

    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    labels = clustering.fit_predict(distance_matrix)

    return labels.tolist()


def compute_pairwise_metrics(failures: list[dict]) -> dict:
    """
    Calcula métricas agregadas de comparação entre as três técnicas de similaridade,
    usando a primeira falha de cada cluster como referência (amostra representativa).
    Retorna um resumo útil para exibir no dashboard/relatório.
    """
    messages = [f["error_message"] for f in failures]
    n = len(messages)

    if n < 2:
        return {"pairs_compared": 0, "avg_tfidf_cosine": 0, "avg_levenshtein": 0, "avg_jaccard": 0}

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([_normalize_error_message(m) for m in messages])
    cosine_matrix = cosine_similarity(tfidf_matrix)

    lev_scores = []
    jac_scores = []
    cos_scores = []

    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            lev_scores.append(levenshtein_similarity(messages[i], messages[j]))
            jac_scores.append(jaccard_similarity(messages[i], messages[j]))
            cos_scores.append(cosine_matrix[i][j])
            pairs += 1

    return {
        "pairs_compared": pairs,
        "avg_tfidf_cosine": round(float(np.mean(cos_scores)), 3),
        "avg_levenshtein": round(float(np.mean(lev_scores)), 3),
        "avg_jaccard": round(float(np.mean(jac_scores)), 3),
    }


def classify_cluster_heuristic(failures_in_cluster: list[dict]) -> str:
    """
    Classificação heurística simples (fallback caso a IA não esteja disponível ou
    como sinal complementar): Flaky Test, Bug Real ou Problema de Ambiente.
    """
    count = len(failures_in_cluster)
    combined_text = " ".join(f["error_message"].lower() + " " + f.get("stack_trace", "").lower()
                              for f in failures_in_cluster)

    env_keywords = ["etimedout", "econnrefused", "network error", "connect", "dns", "socket hang up"]
    flaky_keywords = ["timed out retrying", "detached from the dom", "cy.wait()", "element is not visible"]

    if any(k in combined_text for k in env_keywords):
        return "Problema de Ambiente"
    if any(k in combined_text for k in flaky_keywords) and count >= 2:
        return "Flaky Test"
    return "Bug Real"
