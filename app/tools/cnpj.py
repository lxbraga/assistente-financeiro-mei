"""Ferramenta de consulta de CNPJ (BrasilAPI)."""

import re

from langchain_core.tools import ToolException, tool

from app.tools.comum import NaoEncontrado, buscar_json

URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
PESOS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _digito(base: str) -> str:
    # ord - 48 mantém 0-9 e converte as letras do CNPJ alfanumérico (2026).
    soma = sum((ord(c) - 48) * peso for c, peso in zip(base, PESOS[-len(base):]))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def normalizar_cnpj(texto: str) -> str:
    """Remove a pontuação e confere os dígitos verificadores."""
    cnpj = re.sub(r"[^0-9A-Z]", "", re.sub(r"^\W*cnpj\W*", "", texto, flags=re.I).upper())
    if re.fullmatch(r"[0-9A-Z]{12}\d{2}", cnpj) and len(set(cnpj)) > 1:
        primeiro = _digito(cnpj[:12])
        if cnpj[12:] == primeiro + _digito(cnpj[:12] + primeiro):
            return cnpj
    raise ToolException("CNPJ inválido: confira os caracteres.")


def _sim_nao(valor) -> str:
    return {True: "sim", False: "não"}.get(valor, "não informado")


@tool
def consultar_cnpj(cnpj: str) -> str:
    """Consulta a situação cadastral de uma empresa. Entrada: o CNPJ. Exemplo: 00.000.000/0001-91"""
    numero = normalizar_cnpj(cnpj)
    try:
        dados = buscar_json(URL.format(cnpj=numero))
    except NaoEncontrado as exc:
        raise ToolException("CNPJ não encontrado na base da Receita.") from exc
    if not isinstance(dados, dict):
        raise ToolException("Resposta inesperada da BrasilAPI.")

    # Só campos da empresa: sócios, telefone e e-mail não chegam ao LLM.
    return "; ".join(
        [
            f"Razão social: {dados.get('razao_social')}",
            f"Situação: {dados.get('descricao_situacao_cadastral')}",
            f"Atividade: {dados.get('cnae_fiscal_descricao')}",
            f"Abertura: {dados.get('data_inicio_atividade')}",
            f"Cidade: {dados.get('municipio')}/{dados.get('uf')}",
            f"MEI: {_sim_nao(dados.get('opcao_pelo_mei'))}",
            f"Simples: {_sim_nao(dados.get('opcao_pelo_simples'))}",
        ]
    )


consultar_cnpj.handle_tool_error = True
