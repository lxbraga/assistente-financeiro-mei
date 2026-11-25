"""Ferramenta de correção pelo IPCA (Banco Central, série 433)."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from langchain_core.tools import ToolException, tool

from app.tools.comum import NaoEncontrado, arredondar, buscar_json, formatar_numero, formatar_reais, ler_campos, ler_mes, ler_valor

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados"


def corrigir(valor: Decimal, indices: list[Decimal]) -> tuple[Decimal, Decimal]:
    """Devolve (variação acumulada em %, valor corrigido)."""
    fator = Decimal(1)
    for indice in indices:
        fator *= 1 + indice / 100
    return arredondar((fator - 1) * 100), arredondar(valor * fator)


@tool
def corrigir_pelo_ipca(entrada: str) -> str:
    """Corrige um valor pela inflação (IPCA), incluindo os meses inicial e final. Entrada: valor=N; inicio=AAAA-MM; fim=AAAA-MM"""
    campos = ler_campos(entrada, ["valor", "inicio", "fim"])
    valor, inicio, fim = ler_valor(campos["valor"]), ler_mes(campos["inicio"]), ler_mes(campos["fim"])
    if inicio > fim:
        raise ToolException("O mês inicial deve ser anterior ou igual ao final.")
    try:
        dados = buscar_json(URL, {"formato": "json", "dataInicial": f"{inicio:%d/%m/%Y}", "dataFinal": f"{fim:%d/%m/%Y}"})
        indices = [Decimal(item["valor"]) for item in dados]
        ultimo = datetime.strptime(dados[-1]["data"], "%d/%m/%Y").date()
    except NaoEncontrado as exc:
        raise ToolException("IPCA ainda não publicado para o período.") from exc
    except (KeyError, IndexError, TypeError, ValueError, InvalidOperation) as exc:
        raise ToolException("Resposta inesperada do Banco Central.") from exc

    variacao, corrigido = corrigir(valor, indices)
    aviso = f" Aviso: último IPCA publicado é {ultimo:%m/%Y}." if ultimo < fim else ""
    return f"IPCA de {inicio:%m/%Y} a {ultimo:%m/%Y}: {formatar_numero(variacao)}%. Valor corrigido: {formatar_reais(corrigido)}.{aviso}"


corrigir_pelo_ipca.handle_tool_error = True
