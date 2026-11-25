from datetime import date

import httpx
import openai
import pytest
from langchain_core.language_models import FakeListChatModel

from app.agent import AssistenteFinanceiro, ErroAssistente

USAR_TOOL = (
    "Thought: preciso calcular\nAction: calcular_encargos_atraso\n"
    "Action Input: valor=1200; vencimento=2026-11-03; pagamento=2026-11-25"
)
FINAL = "Thought: já sei\nFinal Answer: "


class LLMEspiao(FakeListChatModel):
    """LLM falso que guarda os prompts recebidos."""

    prompts: list = []

    def _call(self, messages, *args, **kwargs):
        self.prompts.append("\n".join(str(m.content) for m in messages))
        return super()._call(messages, *args, **kwargs)


def criar(*respostas):
    llm = LLMEspiao(responses=list(respostas), prompts=[])
    return AssistenteFinanceiro(llm, hoje=lambda: date(2026, 11, 25)), llm


def test_ciclo_react():
    assistente, llm = criar(USAR_TOOL, FINAL + "R$ 1.232,80")
    resposta = assistente.perguntar("Quanto devo?", "s1")
    assert resposta.texto == "R$ 1.232,80"
    passo = resposta.passos[0]
    assert passo.pensamento == "preciso calcular"
    assert passo.ferramenta == "calcular_encargos_atraso"
    assert "R$ 1.232,80" in passo.observacao
    assert "Observation: Atraso: 22 dias" in llm.prompts[1]


def test_prompt_informa_datas():
    assistente, llm = criar(FINAL + "ok")
    assistente.perguntar("oi", "s1")
    assert "2026-11-25 (quarta)" in llm.prompts[0]
    assert "2026-11-27 (sexta)" in llm.prompts[0]


def test_memoria_por_sessao():
    assistente, llm = criar(FINAL + "a", FINAL + "b", FINAL + "c")
    assistente.perguntar("boleto de 1200", "s1")
    assistente.perguntar("e na sexta?", "s1")
    assistente.perguntar("outra", "s2")
    assert "boleto de 1200" in llm.prompts[1]
    assert "boleto de 1200" not in llm.prompts[2]


def test_memoria_limita_mensagens_e_limpa():
    assistente, llm = criar(*[FINAL + "ok"] * 8)
    for i in range(7):
        assistente.perguntar(f"pergunta-{i}", "s1")
    assert "pergunta-0" not in llm.prompts[6] and "pergunta-1" in llm.prompts[6]
    assistente.limpar("s1")
    assistente.perguntar("nova", "s1")
    assert "pergunta-6" not in llm.prompts[7]


def test_erro_de_ferramenta_vira_observacao():
    ruim = "Thought: t\nAction: calcular_encargos_atraso\nAction Input: valor=abc"
    assistente, _ = criar(ruim, FINAL + "faltam dados")
    assert "obrigatórios" in assistente.perguntar("x", "s1").passos[0].observacao


def test_formato_invalido_se_recupera():
    assistente, _ = criar("texto solto", FINAL + "ok")
    assert assistente.perguntar("x", "s1").texto == "ok"


def test_limite_de_iteracoes():
    assistente, _ = criar(USAR_TOOL)
    with pytest.raises(ErroAssistente, match="concluir"):
        assistente.perguntar("x", "s1")


def test_pergunta_vazia():
    assistente, _ = criar(FINAL + "ok")
    with pytest.raises(ErroAssistente, match="pergunta"):
        assistente.perguntar("  ", "s1")


REQ = httpx.Request("POST", "http://x")


@pytest.mark.parametrize(
    "erro, mensagem",
    [
        (openai.AuthenticationError("x", response=httpx.Response(401, request=REQ), body=None), "Chave"),
        (openai.RateLimitError("x", response=httpx.Response(429, request=REQ), body=None), "Limite"),
        (openai.APITimeoutError(request=REQ), "demorou"),
        (openai.APIConnectionError(request=REQ), "OpenAI"),
    ],
)
def test_erros_da_openai(erro, mensagem):
    class LLMComErro(LLMEspiao):
        def _call(self, *args, **kwargs):
            raise erro

    with pytest.raises(ErroAssistente, match=mensagem):
        AssistenteFinanceiro(LLMComErro(responses=["x"])).perguntar("x", "s1")


def test_prompt_nao_expoe_parametro_interno():
    assistente, llm = criar(FINAL + "ok")
    assistente.perguntar("oi", "s1")
    assert "entrada: str" not in llm.prompts[0]


def test_passo_de_formato_invalido_e_legivel():
    assistente, llm = criar("texto solto", FINAL + "ok")
    passo = assistente.perguntar("x", "s1").passos[0]
    assert passo.ferramenta == "(formato inválido)" and passo.pensamento == "texto solto"
    assert "Final Answer:" in llm.prompts[1].split("Observation:")[-1]


def test_memoria_preserva_formato_react():
    assistente, llm = criar(FINAL + "resposta-1", FINAL + "b")
    assistente.perguntar("a", "s1")
    assistente.perguntar("b", "s1")
    assert "Final Answer: resposta-1" in llm.prompts[1]


def test_memoria_guarda_observacoes():
    assistente, llm = criar(USAR_TOOL, FINAL + "R$ 1.232,80", FINAL + "ok")
    assistente.perguntar("a", "s1")
    assistente.perguntar("b", "s1")
    assert "Observation: Atraso: 22 dias" in llm.prompts[2]


def test_valor_inventado_gera_nova_tentativa():
    assistente, _ = criar(FINAL + "R$ 1.236,00", USAR_TOOL, FINAL + "R$ 1.232,80")
    assert assistente.perguntar("Quanto devo?", "s1").texto == "R$ 1.232,80"


def test_valor_inventado_persistente_vira_erro_e_nao_entra_na_memoria():
    assistente, llm = criar(FINAL + "R$ 1.236,00", FINAL + "R$ 1.236,00", FINAL + "ok")
    with pytest.raises(ErroAssistente, match="confirmar"):
        assistente.perguntar("Quanto devo?", "s1")
    assistente.perguntar("oi", "s1")
    assert "1.236,00" not in llm.prompts[2]


def test_valor_do_usuario_e_aceito():
    assistente, _ = criar(FINAL + "Quando venceu a conta de R$ 1.200,00?")
    assert "1.200,00" in assistente.perguntar("Tenho uma conta de 1200 reais", "s1").texto


def test_numero_enorme_na_pergunta_nao_quebra():
    assistente, _ = criar(FINAL + "Valor acima do limite.")
    assert assistente.perguntar("Corrija R$ 999.999.999.999,00", "s1").texto
