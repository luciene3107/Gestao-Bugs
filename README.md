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

## Como funciona (para o relatório/apresentação)

1. **Upload**: usuário envia um JSON com a lista de falhas de teste (nome do
   teste, mensagem de erro, stack trace, ambiente etc.)

2. **Clusterização (TF-IDF + Cosine Similarity + DBSCAN)**: as mensagens de erro
   são vetorizadas com TF-IDF (unigramas + bigramas) e agrupadas por similaridade
   de cosseno usando DBSCAN — falhas com mensagens parecidas caem no mesmo cluster,
   mesmo que os testes/arquivos sejam diferentes.

3. **Métricas comparativas**: além do TF-IDF, o sistema calcula a similaridade
   média de **Levenshtein** (distância de edição normalizada) e **Jaccard**
   (sobreposição de tokens) entre todos os pares de mensagens, para fins de
   comparação técnica entre as três abordagens — isso é mostrado no dashboard.

4. **Classificação heurística**: cada cluster recebe uma classificação inicial
   com base em palavras-chave típicas:
   - *Problema de Ambiente*: erros de rede/timeout de infraestrutura (ETIMEDOUT, connection refused...)
   - *Flaky Test*: erros de timing/renderização que tendem a ser instáveis (elemento não encontrado, detached from DOM...)
   - *Bug Real*: os demais casos (asserções de valor incorreto, TypeError, etc.)

5. **Resumo com IA (LLaMA/Groq)**: o cluster é enviado ao modelo LLaMA, que
   confirma/ajusta a classificação heurística e escreve um resumo em português
   explicando a provável causa raiz e recomendação. Se a chave da API não estiver
   configurada, um resumo heurístico local é usado no lugar (o app nunca quebra
   por falta de IA).

6. **Persistência**: cada análise é salva em SQLite (runs, clusters e falhas
   individuais), disponível na aba "Histórico".

## Dataset de exemplo

`sample_data/sample_logs.json` simula uma execução real de Cypress com 15 falhas
que, ao serem agrupadas, revelam **7 causas raiz distintas** — por exemplo, os
testes de login e busca que falham pelo mesmo motivo (timeout de elemento) caem
automaticamente no mesmo cluster, mesmo estando em arquivos de teste diferentes.
