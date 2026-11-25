"""Ferramenta de prazo em dias úteis (feriados da BrasilAPI)."""

from datetime import date, timedelta
from functools import lru_cache

from langchain_core.tools import ToolException, tool

from app.tools.comum import buscar_json, ler_campos, ler_data

URL = "https://brasilapi.com.br/api/feriados/v1/{ano}"
DIAS_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@lru_cache
def feriados(ano: int) -> dict[date, str]:
    try:
        return {date.fromisoformat(f["date"]): f["name"] for f in buscar_json(URL.format(ano=ano))}
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolException("Resposta inesperada da BrasilAPI.") from exc


def eh_dia_util(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in feriados(dia.year)


def proximo_dia_util(dia: date) -> date:
    """Retorna o próprio dia, se útil, ou o próximo dia útil."""
    while not eh_dia_util(dia):
        dia += timedelta(days=1)
    return dia


def somar_dias_uteis(inicio: date, dias: int) -> tuple[date, list[str]]:
    """Conta a partir do dia seguinte; devolve a data final e os feriados pulados."""
    if not 1 <= dias <= 365:
        raise ToolException("A quantidade de dias deve estar entre 1 e 365.")
    dia, pulados = inicio, []
    while dias:
        dia += timedelta(days=1)
        if eh_dia_util(dia):
            dias -= 1
        elif dia.weekday() < 5:
            pulados.append(f"{dia:%d/%m/%Y} ({feriados(dia.year)[dia]})")
    return dia, pulados


@tool
def calcular_dias_uteis(entrada: str) -> str:
    """Soma dias úteis a uma data. Entrada: inicio=AAAA-MM-DD; dias=N"""
    campos = ler_campos(entrada, ["inicio", "dias"])
    try:
        dias = int(campos["dias"])
    except ValueError as exc:
        raise ToolException("'dias' deve ser um número inteiro.") from exc
    fim, pulados = somar_dias_uteis(ler_data(campos["inicio"]), dias)
    return (
        f"Data final: {fim:%d/%m/%Y} ({DIAS_SEMANA[fim.weekday()]}). "
        f"Feriados nacionais pulados: {', '.join(pulados) or 'nenhum'}. "
        "Feriados locais não são considerados."
    )


calcular_dias_uteis.handle_tool_error = True
