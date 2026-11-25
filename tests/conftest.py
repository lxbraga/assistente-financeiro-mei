"""Nenhum teste acessa a rede."""

from datetime import date

import pytest
import requests

FERIADOS = {
    2026: {date(2026, 11, 2): "Finados", date(2026, 12, 25): "Natal"},
    2027: {date(2027, 1, 1): "Ano novo"},
}


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    def bloquear(*args, **kwargs):
        raise AssertionError("Teste tentou acessar a rede.")

    monkeypatch.setattr(requests, "get", bloquear)
    monkeypatch.setattr("app.tools.dias_uteis.feriados", lambda ano: FERIADOS.get(ano, {}))
