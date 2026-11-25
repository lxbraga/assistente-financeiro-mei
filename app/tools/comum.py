"""Leitura de entradas, formatação e acesso HTTP usados pelas ferramentas.

Toda falha prevista vira ToolException: o LangChain a devolve ao agente como
Observation, permitindo que ele corrija a entrada ou avise o usuário.
"""

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import requests
from langchain_core.tools import ToolException

TIMEOUT_SEGUNDOS = 10
# A BrasilAPI responde 429 ao User-Agent padrão do requests.
CABECALHOS = {"User-Agent": "python-api-client/1.0"}


class NaoEncontrado(ToolException):
    """A API respondeu 404."""


def buscar_json(url: str, params: dict | None = None):
    try:
        resposta = requests.get(url, params=params, headers=CABECALHOS, timeout=TIMEOUT_SEGUNDOS)
        if resposta.status_code == 404:
            raise NaoEncontrado("Registro não encontrado.")
        resposta.raise_for_status()
        return resposta.json()
    except (requests.RequestException, ValueError) as exc:
        raise ToolException("Serviço externo indisponível. Tente mais tarde.") from exc


def ler_campos(texto: str, obrigatorios: list[str], opcionais: tuple = ()) -> dict[str, str]:
    """Converte 'chave=valor; chave=valor' em dicionário."""
    linha = (texto.strip().splitlines() or [""])[0].strip("\"'` ")
    pares = (parte.split("=", 1) for parte in linha.split(";") if "=" in parte)
    campos = {chave.strip().lower(): valor.strip() for chave, valor in pares}

    faltando = [nome for nome in obrigatorios if not campos.get(nome)]
    if faltando:
        raise ToolException(f"Campos obrigatórios ausentes: {', '.join(faltando)}. Use 'chave=valor; chave=valor'.")
    desconhecidos = set(campos) - set(obrigatorios) - set(opcionais)
    if desconhecidos:
        raise ToolException(f"Campos desconhecidos: {', '.join(sorted(desconhecidos))}.")
    return campos


def _ler_decimal(texto: str) -> Decimal:
    numero = re.sub(r"[R$%\s]", "", texto)
    if "," in numero:  # formato brasileiro: 1.200,50
        numero = numero.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", numero):  # só milhar: 1.200
        numero = numero.replace(".", "")
    try:
        valor = Decimal(numero)
    except InvalidOperation as exc:
        raise ToolException(f"Número inválido: '{texto}'.") from exc
    if not valor.is_finite():
        raise ToolException(f"Número inválido: '{texto}'.")
    return valor


def ler_valor(texto: str) -> Decimal:
    valor = _ler_decimal(texto)
    if not 0 < valor <= 10**9:
        raise ToolException("O valor deve ser maior que zero e até 1 bilhão.")
    return valor


def ler_percentual(texto: str) -> Decimal:
    valor = _ler_decimal(texto)
    if not 0 <= valor <= 100:
        raise ToolException("Percentual deve estar entre 0 e 100.")
    return valor


def _ler_formatos(texto: str, formatos: tuple, exemplo: str) -> date:
    for formato in formatos:
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    raise ToolException(f"Data inválida: '{texto}'. Use {exemplo}.")


def ler_data(texto: str) -> date:
    return _ler_formatos(texto, ("%Y-%m-%d", "%d/%m/%Y"), "AAAA-MM-DD")


def ler_mes(texto: str) -> date:
    return _ler_formatos(texto, ("%Y-%m", "%m/%Y", "%Y-%m-%d"), "AAAA-MM").replace(day=1)


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), ROUND_HALF_UP)


def formatar_numero(valor: Decimal) -> str:
    return f"{valor:,f}".translate(str.maketrans(",.", ".,"))


def formatar_reais(valor: Decimal) -> str:
    return f"R$ {formatar_numero(arredondar(valor))}"
