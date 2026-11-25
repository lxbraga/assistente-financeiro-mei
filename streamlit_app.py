"""Interface web do assistente."""

import streamlit as st

from app.agent import AssistenteFinanceiro, ErroAssistente, Passo, criar_llm

EXEMPLOS = [
    "Qual a situação do CNPJ 00.000.000/0001-91?",
    "Um boleto de R$ 1.200 venceu em 03/11/2026. Quanto devo hoje?",
    "Corrija R$ 5.000 pelo IPCA de janeiro a outubro de 2026.",
]
SESSAO = "streamlit"  # cada aba tem seu próprio assistente


def mostrar(texto: str, passos: list[Passo]) -> None:
    if passos:
        with st.expander("Raciocínio (ReAct)"):
            for passo in passos:
                st.text(
                    f"Thought: {passo.pensamento}\nAction: {passo.ferramenta}\n"
                    f"Action Input: {passo.entrada}\nObservation: {passo.observacao}"
                )
    st.markdown(texto.replace("$", r"\$"))  # evita que "R$" vire fórmula LaTeX


st.set_page_config(page_title="Assistente Financeiro para MEI", page_icon="💰")
st.title("Assistente Financeiro para MEI")

if "assistente" not in st.session_state:
    try:
        st.session_state.assistente = AssistenteFinanceiro(criar_llm())
    except ErroAssistente as exc:
        st.error(str(exc))
        st.stop()
    st.session_state.conversa = []

pergunta = st.chat_input("Digite sua pergunta")
with st.sidebar:
    st.subheader("Exemplos")
    for exemplo in EXEMPLOS:
        if st.button(exemplo.replace("$", r"\$")):
            pergunta = exemplo
    if st.button("Nova conversa", type="primary"):
        st.session_state.assistente.limpar(SESSAO)
        st.session_state.conversa = []

for autor, texto, passos in st.session_state.conversa:
    with st.chat_message(autor):
        mostrar(texto, passos)

if pergunta:
    st.session_state.conversa.append(("user", pergunta, []))
    with st.chat_message("user"):
        mostrar(pergunta, [])
    with st.chat_message("assistant"):
        try:
            with st.spinner("Pensando..."):
                resposta = st.session_state.assistente.perguntar(pergunta, SESSAO)
            mostrar(resposta.texto, resposta.passos)
            st.session_state.conversa.append(("assistant", resposta.texto, resposta.passos))
        except ErroAssistente as exc:
            st.error(str(exc))
