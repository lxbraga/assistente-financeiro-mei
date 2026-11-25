from streamlit.testing.v1 import AppTest

from app.agent import AssistenteFinanceiro
from langchain_core.language_models import FakeListChatModel


def test_sem_chave_mostra_erro(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    tela = AppTest.from_file("../streamlit_app.py").run(timeout=20)
    assert "OPENAI_API_KEY" in tela.error[0].value


def test_conversa():
    llm = FakeListChatModel(
        responses=[
            "Thought: calcular\nAction: calcular_encargos_atraso\n"
            "Action Input: valor=1200; vencimento=2026-11-03; pagamento=2026-11-25",
            "Thought: ok\nFinal Answer: Deve R$ 1.232,80",
        ]
    )
    tela = AppTest.from_file("../streamlit_app.py")
    tela.session_state.assistente = AssistenteFinanceiro(llm)
    tela.session_state.conversa = []
    tela.run(timeout=20)
    tela.chat_input[0].set_value("Quanto devo?").run(timeout=20)
    assert not tela.exception
    assert any("1.232,80" in m.value for m in tela.markdown)
    assert any("Observation: Atraso: 22 dias" in t.value for t in tela.text)
