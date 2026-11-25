from datetime import date
from decimal import Decimal as D

import pytest
import requests
from langchain_core.tools import ToolException

from app.tools import cnpj, comum, ipca
from app.tools.dias_uteis import calcular_dias_uteis, somar_dias_uteis
from app.tools.encargos import calcular, calcular_encargos_atraso


# --- Entrada e HTTP ---
@pytest.mark.parametrize(
    "texto, esperado",
    [("R$ 1.200,00", "1200"), ("1200", "1200"), ("1200.50", "1200.50"), ("1.200", "1200")],
)
def test_ler_valor(texto, esperado):
    assert comum.ler_valor(texto) == D(esperado)


@pytest.mark.parametrize("texto", ["", "abc", "0", "-10", "NaN", "Infinity"])
def test_ler_valor_recusa(texto):
    with pytest.raises(ToolException):
        comum.ler_valor(texto)


@pytest.mark.parametrize("texto", ["2026-11-03", "03/11/2026"])
def test_ler_data(texto):
    assert comum.ler_data(texto) == date(2026, 11, 3)


@pytest.mark.parametrize("erro", [requests.Timeout(), requests.ConnectionError()])
def test_falha_de_rede_vira_tool_exception(monkeypatch, erro):
    def get(*args, **kwargs):
        raise erro

    monkeypatch.setattr(requests, "get", get)
    with pytest.raises(ToolException, match="indisponível"):
        comum.buscar_json("http://x")


# --- CNPJ ---
@pytest.mark.parametrize("texto", ["00.000.000/0001-91", "cnpj=00000000000191"])
def test_cnpj_consulta_descarta_dados_pessoais(monkeypatch, texto):
    dados = {
        "razao_social": "BANCO DO BRASIL SA",
        "descricao_situacao_cadastral": "ATIVA",
        "opcao_pelo_mei": False,
        "ddd_telefone_1": "6134939002",
        "qsa": [{"nome_socio": "FULANO"}],
    }
    monkeypatch.setattr(cnpj, "buscar_json", lambda url: dados)
    saida = cnpj.consultar_cnpj.run(texto)
    assert "ATIVA" in saida and "MEI: não" in saida
    assert "FULANO" not in saida and "6134939002" not in saida


def test_cnpj_alfanumerico():
    assert cnpj.normalizar_cnpj("12.ABC.345/01DE-35") == "12ABC34501DE35"


@pytest.mark.parametrize("texto", ["11.111.111/1111-11", "123", "12ABC34501DE36"])
def test_cnpj_invalido_vira_observacao(texto):
    assert "inválido" in cnpj.consultar_cnpj.run(texto)


# --- Dias úteis ---
@pytest.mark.parametrize(
    "inicio, dias, fim",
    [
        (date(2026, 10, 30), 1, date(2026, 11, 3)),  # fim de semana + Finados
        (date(2026, 12, 30), 2, date(2027, 1, 4)),  # cruza o ano
    ],
)
def test_somar_dias_uteis(inicio, dias, fim):
    assert somar_dias_uteis(inicio, dias)[0] == fim


def test_dias_uteis_informa_feriado():
    saida = calcular_dias_uteis.run("inicio=30/10/2026; dias=1")
    assert "03/11/2026" in saida and "Finados" in saida


def test_dias_uteis_quantidade_invalida():
    assert "inteiro" in calcular_dias_uteis.run("inicio=30/10/2026; dias=dez")


# --- Encargos ---
@pytest.mark.parametrize(
    "vencimento, pagamento, dias, total",
    [
        (date(2026, 11, 3), date(2026, 11, 25), 22, "1232.80"),
        (date(2026, 11, 3), date(2026, 11, 27), 24, "1233.60"),
        (date(2026, 11, 3), date(2026, 11, 1), 0, "1200.00"),
        (date(2026, 11, 1), date(2026, 11, 3), 0, "1200.00"),  # domingo + feriado
        (date(2026, 11, 1), date(2026, 11, 4), 3, "1225.20"),
    ],
)
def test_encargos(vencimento, pagamento, dias, total):
    resultado = calcular(D("1200"), vencimento, pagamento)
    assert (resultado.dias, resultado.total) == (dias, D(total))


def test_encargos_tool():
    saida = calcular_encargos_atraso.run("valor=R$ 1.200,00; vencimento=03/11/2026; pagamento=2026-11-25")
    for trecho in ["22 dias", "R$ 24,00", "R$ 8,80", "R$ 1.232,80"]:
        assert trecho in saida


@pytest.mark.parametrize("entrada, erro", [("valor=1200", "vencimento"), ("valor=1; vencimento=2026-11-03; pagamento=2026-11-25; multa=-1", "ercentual")])
def test_encargos_erro_vira_observacao(entrada, erro):
    assert erro in calcular_encargos_atraso.run(entrada)


# --- IPCA ---
INDICES = [{"data": "01/01/2026", "valor": "1.00"}, {"data": "01/02/2026", "valor": "2.00"}]


def test_ipca(monkeypatch):
    monkeypatch.setattr(ipca, "buscar_json", lambda url, params: INDICES)
    saida = ipca.corrigir_pelo_ipca.run("valor=1000; inicio=01/2026; fim=2026-02")
    assert "3,02%" in saida and "R$ 1.030,20" in saida and "Aviso" not in saida


def test_ipca_mes_final_nao_publicado(monkeypatch):
    monkeypatch.setattr(ipca, "buscar_json", lambda url, params: INDICES)
    assert "Aviso" in ipca.corrigir_pelo_ipca.run("valor=1000; inicio=2026-01; fim=2026-03")


def test_ipca_periodo_invertido():
    assert "anterior" in ipca.corrigir_pelo_ipca.run("valor=1000; inicio=2026-03; fim=2026-01")
