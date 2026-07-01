# TRIAGEM — Gestão Inteligente de Falhas de Testes Automatizados

Site que recebe logs de execução de testes automatizados (Cypress/Tosca em formato
JSON), agrupa falhas semelhantes por similaridade textual, classifica cada grupo
(Bug Real / Flaky Test / Problema de Ambiente) e gera um resumo em linguagem natural
usando IA (LLaMA via Groq).

## Como rodar

### 1. Instalar dependências

```bash
cd backend
pip install -r requirements.txt --break-system-packages
```

### 2. (Opcional) Configurar a chave da Groq API

Sem a chave, o sistema funciona normalmente usando um resumo heurístico (fallback).
Com a chave, os resumos ficam mais ricos e a classificação é validada pela IA.

```bash
export GROQ_API_KEY="sua_chave_aqui"
```

Chave gratuita em: https://console.groq.com

### 3. Rodar o servidor

A partir da pasta raiz do projeto (não da pasta `backend`):

```bash
python3 -m uvicorn backend.main:app --reload --port 8000
```

### 4. Acessar

Abra o navegador em **http://localhost:8000**

Use o botão **"Usar log de exemplo"** para testar rapidamente com o dataset incluso
em `sample_data/sample_logs.json` (15 falhas simuladas de Cypress).

## Estrutura do projeto

```
bugmanager/
├── backend/
│   ├── main.py           # API FastAPI (rotas /api/upload, /api/history, /api/runs/{id})
│   ├── parser.py         # Normaliza o JSON de log enviado
│   ├── similarity.py     # TF-IDF+Cosine (clustering), Levenshtein, Jaccard
│   ├── groq_client.py    # Integração com LLaMA via Groq (resumo + classificação)
│   ├── database.py       # Persistência em SQLite (runs, clusters, failures)
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── sample_data/
    └── sample_logs.json  # Dataset de exemplo (15 falhas, 7 causas distintas)
```

## Dataset de exemplo

`sample_data/sample_logs.json` simula uma execução real de Cypress com 15 falhas
que, ao serem agrupadas, revelam **7 causas raiz distintas** — por exemplo, os
testes de login e busca que falham pelo mesmo motivo (timeout de elemento) caem
automaticamente no mesmo cluster, mesmo estando em arquivos de teste diferentes.
