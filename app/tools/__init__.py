"""Ferramentas disponíveis para o agente."""

from app.tools.cnpj import consultar_cnpj
from app.tools.dias_uteis import calcular_dias_uteis
from app.tools.encargos import calcular_encargos_atraso
from app.tools.ipca import corrigir_pelo_ipca

TOOLS = [consultar_cnpj, calcular_dias_uteis, calcular_encargos_atraso, corrigir_pelo_ipca]
