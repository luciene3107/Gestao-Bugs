"""
Parser de logs de falhas de testes automatizados (formato Cypress/Tosca simplificado).

Formato esperado: lista de objetos JSON com pelo menos:
- test_name
- error_message
Campos opcionais: suite, stack_trace, duration_ms, timestamp, environment, run_id
"""
import json


class LogParseError(Exception):
    pass


def parse_log_file(raw_content: bytes) -> list[dict]:
    """
    Recebe o conteúdo bruto do arquivo enviado e retorna uma lista
    normalizada de falhas de teste.
    """
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise LogParseError(f"Arquivo não é um JSON válido: {e}")

    if not isinstance(data, list):
        raise LogParseError("O arquivo deve conter uma lista de falhas de teste.")

    failures = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue

        test_name = item.get("test_name") or item.get("title") or f"teste_desconhecido_{i}"
        error_message = item.get("error_message") or item.get("error") or item.get("message") or ""

        if not error_message:
            # Sem mensagem de erro não há como analisar similaridade
            continue

        failures.append({
            "test_name": test_name,
            "suite": item.get("suite", "Não especificado"),
            "error_message": error_message,
            "stack_trace": item.get("stack_trace", ""),
            "duration_ms": item.get("duration_ms", 0),
            "timestamp": item.get("timestamp", ""),
            "environment": item.get("environment", "não especificado"),
            "run_id": item.get("run_id", "run-manual"),
        })

    if not failures:
        raise LogParseError("Nenhuma falha válida encontrada no arquivo (verifique o campo 'error_message').")

    return failures
