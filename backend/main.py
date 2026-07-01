"""
Plataforma de Gestão Inteligente de Falhas de Testes Automatizados
API principal (FastAPI).
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from collections import defaultdict
import os

from . import database as db
from . import parser
from . import similarity
from . import groq_client

app = FastAPI(title="Gestão Inteligente de Falhas de Testes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


@app.post("/api/upload")
async def upload_log(file: UploadFile = File(...)):
    raw_content = await file.read()

    try:
        failures = parser.parse_log_file(raw_content)
    except parser.LogParseError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1. Clusterização via TF-IDF + Cosine + DBSCAN
    cluster_labels = similarity.cluster_failures(failures)

    # 2. Métricas comparativas (TF-IDF vs Levenshtein vs Jaccard) para o relatório
    comparison_metrics = similarity.compute_pairwise_metrics(failures)

    # 3. Agrupar falhas por cluster
    clusters_map = defaultdict(list)
    for failure, label in zip(failures, cluster_labels):
        clusters_map[int(label)].append(failure)

    # 4. Salvar run
    run_id = failures[0].get("run_id", "run-manual")
    run_db_id = db.save_run(run_id=run_id, filename=file.filename, total_failures=len(failures))

    clusters_result = []
    for label, cluster_failures_list in clusters_map.items():
        heuristic_class = similarity.classify_cluster_heuristic(cluster_failures_list)
        ai_result = groq_client.summarize_cluster(cluster_failures_list, heuristic_class)

        cluster_db_id = db.save_cluster(
            run_db_id=run_db_id,
            cluster_label=label,
            representative_error=cluster_failures_list[0]["error_message"],
            failure_count=len(cluster_failures_list),
            classification=ai_result["classification"],
            ai_summary=ai_result["summary"],
        )

        for f in cluster_failures_list:
            db.save_failure(run_db_id, f, cluster_id=label)

        clusters_result.append({
            "cluster_id": cluster_db_id,
            "cluster_label": label,
            "classification": ai_result["classification"],
            "summary": ai_result["summary"],
            "failure_count": len(cluster_failures_list),
            "failures": cluster_failures_list,
        })

    # Ordenar por quantidade de falhas (maior impacto primeiro)
    clusters_result.sort(key=lambda c: c["failure_count"], reverse=True)

    return {
        "run_db_id": run_db_id,
        "run_id": run_id,
        "filename": file.filename,
        "total_failures": len(failures),
        "total_clusters": len(clusters_result),
        "comparison_metrics": comparison_metrics,
        "clusters": clusters_result,
    }


@app.get("/api/history")
def get_history():
    return db.get_run_history()


@app.get("/api/runs/{run_db_id}")
def get_run(run_db_id: int):
    details = db.get_run_details(run_db_id)
    if not details["run"]:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return details


# Servir o frontend estático
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
