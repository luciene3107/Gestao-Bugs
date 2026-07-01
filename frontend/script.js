// ============================================================
// TRIAGEM — lógica de frontend
// Responsável por: upload de log, chamadas à API, renderização
// de clusters, gráficos e histórico.
// ============================================================

const API_BASE = ""; // mesmo host (FastAPI serve o frontend)

const els = {
  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("fileInput"),
  browseBtn: document.getElementById("browseBtn"),
  loadSampleBtn: document.getElementById("loadSampleBtn"),
  fileStatus: document.getElementById("fileStatus"),
  loadingState: document.getElementById("loadingState"),
  loadingText: document.getElementById("loadingText"),
  errorBanner: document.getElementById("errorBanner"),
  newAnalysisBtn: document.getElementById("newAnalysisBtn"),
  resultsFilename: document.getElementById("resultsFilename"),
  statTotal: document.getElementById("statTotal"),
  statClusters: document.getElementById("statClusters"),
  statBugs: document.getElementById("statBugs"),
  statFlaky: document.getElementById("statFlaky"),
  statEnv: document.getElementById("statEnv"),
  clustersList: document.getElementById("clustersList"),
  metricsBars: document.getElementById("metricsBars"),
  historyList: document.getElementById("historyList"),
  modal: document.getElementById("clusterModal"),
  modalBody: document.getElementById("modalBody"),
  modalClose: document.getElementById("modalClose"),
};

let classificationChartInstance = null;

// ---------- Navegação entre views ----------
function showView(viewId) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.getElementById(viewId).classList.add("active");

  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  const map = { "view-upload": "upload", "view-results": "upload", "view-history": "history" };
  const navKey = map[viewId];
  const btn = document.querySelector(`.nav-btn[data-view="${navKey}"]`);
  if (btn) btn.classList.add("active");
}

document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const view = btn.dataset.view;
    if (view === "upload") showView("view-upload");
    if (view === "history") { loadHistory(); showView("view-history"); }
  });
});

els.newAnalysisBtn.addEventListener("click", () => {
  resetUploadUI();
  showView("view-upload");
});

// ---------- Upload: drag & drop / seleção ----------
els.browseBtn.addEventListener("click", () => els.fileInput.click());
els.dropzone.addEventListener("click", (e) => {
  if (e.target === els.browseBtn) return;
  els.fileInput.click();
});

els.fileInput.addEventListener("change", () => {
  if (els.fileInput.files.length > 0) {
    handleFile(els.fileInput.files[0]);
  }
});

["dragenter", "dragover"].forEach(evt => {
  els.dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    els.dropzone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach(evt => {
  els.dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    els.dropzone.classList.remove("dragover");
  });
});
els.dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

els.loadSampleBtn.addEventListener("click", async () => {
  try {
    setLoading(true, "Carregando log de exemplo…");
    const resp = await fetch("/static/sample_data/sample_logs.json");
    if (!resp.ok) throw new Error("Não foi possível carregar o exemplo.");
    const blob = await resp.blob();
    const file = new File([blob], "sample_logs.json", { type: "application/json" });
    await uploadFile(file);
  } catch (err) {
    showError(err.message);
    setLoading(false);
  }
});

function handleFile(file) {
  if (!file.name.endsWith(".json")) {
    showError("Por favor envie um arquivo .json");
    return;
  }
  els.fileStatus.textContent = file.name;
  els.fileStatus.classList.add("ok");
  uploadFile(file);
}

async function uploadFile(file) {
  hideError();
  setLoading(true, "Analisando falhas… agrupando por similaridade");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const resp = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      body: formData,
    });

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || "Erro ao processar o arquivo.");
    }

    const data = await resp.json();
    setLoading(false);
    renderResults(data);
    showView("view-results");
  } catch (err) {
    setLoading(false);
    showError(err.message || "Erro inesperado ao enviar o arquivo.");
  }
}

function setLoading(isLoading, text) {
  if (isLoading) {
    els.loadingText.textContent = text || "Processando…";
    els.loadingState.classList.remove("hidden");
  } else {
    els.loadingState.classList.add("hidden");
  }
}

function showError(msg) {
  els.errorBanner.textContent = msg;
  els.errorBanner.classList.remove("hidden");
}
function hideError() {
  els.errorBanner.classList.add("hidden");
}

function resetUploadUI() {
  els.fileInput.value = "";
  els.fileStatus.textContent = "";
  els.fileStatus.classList.remove("ok");
  hideError();
  setLoading(false);
}

// ---------- Classificação: helpers visuais ----------
function classSlug(classification) {
  if (classification === "Bug Real") return "bug";
  if (classification === "Flaky Test") return "flaky";
  return "env";
}

// ---------- Renderização dos resultados ----------
function renderResults(data) {
  els.resultsFilename.textContent = data.filename;
  animateCounter(els.statTotal, data.total_failures);
  animateCounter(els.statClusters, data.total_clusters);

  const counts = { bug: 0, flaky: 0, env: 0 };
  data.clusters.forEach(c => {
    counts[classSlug(c.classification)] += c.failure_count;
  });
  animateCounter(els.statBugs, counts.bug);
  animateCounter(els.statFlaky, counts.flaky);
  animateCounter(els.statEnv, counts.env);

  renderClusters(data.clusters);
  renderClassificationChart(counts);
  renderMetrics(data.comparison_metrics);
}

function animateCounter(el, target, duration = 600) {
  const start = 0;
  const startTime = performance.now();
  function tick(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    el.textContent = Math.round(start + (target - start) * eased);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function renderClusters(clusters) {
  els.clustersList.innerHTML = "";

  clusters.forEach((cluster, index) => {
    const slug = classSlug(cluster.classification);
    const card = document.createElement("div");
    card.className = `cluster-card class-${slug}`;
    card.style.animationDelay = `${Math.min(index * 0.05, 0.4)}s`;
    card.innerHTML = `
      <div class="cluster-top">
        <span class="cluster-badge class-${slug}">${cluster.classification}</span>
        <span class="cluster-count">${cluster.failure_count} teste(s)</span>
      </div>
      <p class="cluster-error">${escapeHtml(cluster.failures[0].error_message)}</p>
      <p class="cluster-summary">${escapeHtml(cluster.summary)}</p>
    `;
    card.addEventListener("click", () => openClusterModal(cluster));
    els.clustersList.appendChild(card);
  });
}

function renderClassificationChart(counts) {
  const ctx = document.getElementById("classificationChart");
  if (typeof Chart === "undefined") {
    ctx.replaceWith(Object.assign(document.createElement("p"), {
      textContent: "Gráfico indisponível (biblioteca não carregou).",
      style: "color:var(--text-dim); font-size:12px;"
    }));
    return;
  }
  if (classificationChartInstance) classificationChartInstance.destroy();

  classificationChartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Bug Real", "Flaky Test", "Problema de Ambiente"],
      datasets: [{
        data: [counts.bug, counts.flaky, counts.env],
        backgroundColor: ["#e5484d", "#d98a1a", "#3b82f6"],
        borderColor: "#ffffff",
        borderWidth: 3,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true,
      animation: { animateRotate: true, animateScale: true, duration: 700, easing: "easeOutCubic" },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#6b7280", font: { family: "Inter", size: 11.5, weight: 500 }, padding: 14, boxWidth: 10, usePointStyle: true, pointStyle: "circle" }
        }
      },
      cutout: "68%"
    }
  });
}

function renderMetrics(metrics) {
  if (!metrics || metrics.pairs_compared === 0) {
    els.metricsBars.innerHTML = `<p style="color:var(--text-dim); font-size:12px;">Falhas insuficientes para comparação (mínimo 2).</p>`;
    return;
  }

  const rows = [
    { label: "TF-IDF + Cosine", value: metrics.avg_tfidf_cosine, cls: "tfidf" },
    { label: "Levenshtein", value: metrics.avg_levenshtein, cls: "lev" },
    { label: "Jaccard", value: metrics.avg_jaccard, cls: "jaccard" },
  ];

  els.metricsBars.innerHTML = rows.map(r => `
    <div class="metric-row">
      <div class="metric-label"><span>${r.label}</span><span>${r.value.toFixed(3)}</span></div>
      <div class="metric-track"><div class="metric-fill ${r.cls}" data-width="${r.value * 100}" style="width:0%"></div></div>
    </div>
  `).join("") + `<p style="font-size:11px; color:var(--text-dim); margin-top:4px;">Média sobre ${metrics.pairs_compared} par(es) de mensagens de erro.</p>`;

  // Anima as barras após o primeiro paint, pra disparar a transição CSS
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.querySelectorAll(".metric-fill").forEach(bar => {
        bar.style.width = bar.dataset.width + "%";
      });
    });
  });
}

// ---------- Modal de detalhes do cluster ----------
function openClusterModal(cluster) {
  const slug = classSlug(cluster.classification);
  els.modalBody.innerHTML = `
    <div class="modal-body">
      <h3>Grupo de ${cluster.failure_count} falha(s)</h3>
      <span class="cluster-badge modal-badge class-${slug}">${cluster.classification}</span>
      <p class="modal-summary">${escapeHtml(cluster.summary)}</p>
      ${cluster.failures.map(f => `
        <div class="modal-failure">
          <p class="modal-failure-name">${escapeHtml(f.test_name)}</p>
          <p class="modal-failure-meta">suíte: ${escapeHtml(f.suite)} · ambiente: ${escapeHtml(f.environment)} · ${f.duration_ms}ms</p>
          <pre class="modal-failure-stack">${escapeHtml(f.stack_trace || f.error_message)}</pre>
        </div>
      `).join("")}
    </div>
  `;
  els.modal.classList.remove("hidden");
}

els.modalClose.addEventListener("click", () => els.modal.classList.add("hidden"));
document.querySelector(".modal-backdrop").addEventListener("click", () => els.modal.classList.add("hidden"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") els.modal.classList.add("hidden");
});

// ---------- Histórico ----------
async function loadHistory() {
  els.historyList.innerHTML = `<p class="history-empty">Carregando…</p>`;
  try {
    const resp = await fetch(`${API_BASE}/api/history`);
    const runs = await resp.json();

    if (runs.length === 0) {
      els.historyList.innerHTML = `<p class="history-empty">Nenhuma análise realizada ainda.</p>`;
      return;
    }

    els.historyList.innerHTML = runs.map(run => `
      <div class="history-item" data-run-id="${run.id}">
        <div class="history-main">
          <span class="history-filename">${escapeHtml(run.filename)}</span>
          <span class="history-meta">${formatDate(run.created_at)} · run: ${escapeHtml(run.run_id || "—")}</span>
        </div>
        <span class="history-count">${run.total_failures} falha(s)</span>
      </div>
    `).join("");

    document.querySelectorAll(".history-item").forEach(item => {
      item.addEventListener("click", () => loadRunDetail(item.dataset.runId));
    });
  } catch (err) {
    els.historyList.innerHTML = `<p class="history-empty">Erro ao carregar histórico.</p>`;
  }
}

async function loadRunDetail(runDbId) {
  try {
    setLoading(true, "Carregando execução…");
    const resp = await fetch(`${API_BASE}/api/runs/${runDbId}`);
    const details = await resp.json();

    const clustersMap = {};
    details.failures.forEach(f => {
      const key = f.cluster_id;
      if (!clustersMap[key]) clustersMap[key] = [];
      clustersMap[key].push(f);
    });

    const clusters = details.clusters.map(c => ({
      cluster_id: c.id,
      classification: c.classification,
      summary: c.ai_summary,
      failure_count: c.failure_count,
      failures: clustersMap[c.cluster_label] || [{
        test_name: "—", error_message: c.representative_error, stack_trace: "", suite: "—", environment: "—", duration_ms: 0
      }],
    }));

    renderResults({
      filename: details.run.filename,
      total_failures: details.run.total_failures,
      total_clusters: clusters.length,
      comparison_metrics: { pairs_compared: 0 },
      clusters,
    });

    setLoading(false);
    showView("view-results");
  } catch (err) {
    setLoading(false);
    showError("Erro ao carregar detalhes da execução.");
  }
}

// ---------- Utils ----------
function escapeHtml(str) {
  if (str === undefined || str === null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDate(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr.includes("Z") ? isoStr : isoStr + "Z");
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
