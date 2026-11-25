"""Ferramenta de multa e juros por atraso."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from langchain_core.tools import tool

from app.tools.comum import arredondar, formatar_numero, formatar_reais, ler_campos, ler_data, ler_percentual, ler_valor
from app.tools.dias_uteis import proximo_dia_util

MULTA_PADRAO = Decimal("2")  # % sobre o valor
JUROS_PADRAO = Decimal("1")  # % ao mês, simples, mês de 30 dias


@dataclass(frozen=True)
class Encargos:
    dias: int
    multa: Decimal
    juros: Decimal
    total: Decimal


def calcular(
    valor: Decimal,
    vencimento: date,
    pagamento: date,
    multa: Decimal = MULTA_PADRAO,
    juros: Decimal = JUROS_PADRAO,
) -> Encargos:
    # Vencimento em dia não útil pode ser pago no próximo dia útil (Lei 7.089/1983).
    if pagamento <= vencimento or pagamento <= proximo_dia_util(vencimento):
        return Encargos(0, Decimal("0.00"), Decimal("0.00"), arredondar(valor))
    dias = (pagamento - vencimento).days
    valor_multa = arredondar(valor * multa / 100)
    valor_juros = arredondar(valor * juros / 100 * dias / 30)
    return Encargos(dias, valor_multa, valor_juros, arredondar(valor + valor_multa + valor_juros))


@tool
def calcular_encargos_atraso(entrada: str) -> str:
    """Calcula multa, juros e total de uma conta atrasada. Entrada: valor=N; vencimento=AAAA-MM-DD; pagamento=AAAA-MM-DD (opcionais: multa=% e juros=% ao mês)"""
    campos = ler_campos(entrada, ["valor", "vencimento", "pagamento"], ("multa", "juros"))
    multa = ler_percentual(campos.get("multa", str(MULTA_PADRAO)))
    juros = ler_percentual(campos.get("juros", str(JUROS_PADRAO)))
    r = calcular(ler_valor(campos["valor"]), ler_data(campos["vencimento"]), ler_data(campos["pagamento"]), multa, juros)
    if not r.dias:
        return f"Pagamento em dia, sem encargos. Total: {formatar_reais(r.total)}."
    return (
        f"Atraso: {r.dias} dias. Multa ({formatar_numero(multa)}%): {formatar_reais(r.multa)}. "
        f"Juros ({formatar_numero(juros)}% ao mês): {formatar_reais(r.juros)}. "
        f"Total: {formatar_reais(r.total)}."
    )


calcular_encargos_atraso.handle_tool_error = True
