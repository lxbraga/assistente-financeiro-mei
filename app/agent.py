"""Agente ReAct: une LLM, ferramentas e memória."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

import openai
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.memory import Memoria
from app.prompts import PROMPT
from app.tools import TOOLS
from app.tools.dias_uteis import DIAS_SEMANA

MAX_ITERACOES = 8
FORMATO_INVALIDO = "Formato inválido. Use 'Action' e 'Action Input', ou 'Final Answer'."


class ErroAssistente(Exception):
    """Erro com mensagem pronta para o usuário."""


@dataclass(frozen=True)
class Passo:
    pensamento: str
    ferramenta: str
    entrada: str
    observacao: str


@dataclass(frozen=True)
class Resposta:
    texto: str
    passos: list[Passo]


def criar_llm() -> BaseChatModel:
    settings = Settings()
    if not settings.openai_api_key:
        raise ErroAssistente("Preencha OPENAI_API_KEY no arquivo .env.")
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,  # respostas mais previsíveis
        timeout=30,
        max_retries=2,
    )


class AssistenteFinanceiro:
    def __init__(self, llm: BaseChatModel, hoje: Callable[[], date] = date.today) -> None:
        self._hoje = hoje
        self._memoria = Memoria()
        self._agente = AgentExecutor(
            agent=create_react_agent(llm, TOOLS, PROMPT),
            tools=TOOLS,
            max_iterations=MAX_ITERACOES,
            handle_parsing_errors=FORMATO_INVALIDO,  # o LLM recebe o aviso e tenta de novo
            return_intermediate_steps=True,  # expõe o raciocínio para a interface
            stream_runnable=False,
        )

    def perguntar(self, pergunta: str, sessao: str) -> Resposta:
        if not pergunta.strip():
            raise ErroAssistente("Digite uma pergunta.")
        historico = self._memoria.obter(sessao)
        try:
            saida = self._agente.invoke(
                {"pergunta": pergunta, "historico": historico.messages, "calendario": self._calendario()}
            )
        except openai.AuthenticationError as exc:
            raise ErroAssistente("Chave da OpenAI inválida.") from exc
        except openai.RateLimitError as exc:
            raise ErroAssistente("Limite de uso ou crédito da OpenAI esgotado.") from exc
        except openai.APITimeoutError as exc:
            raise ErroAssistente("A OpenAI demorou demais para responder.") from exc
        except openai.APIError as exc:
            raise ErroAssistente("Erro ao chamar a OpenAI.") from exc

        if saida["output"].startswith("Agent stopped"):
            raise ErroAssistente("Não consegui concluir. Reformule a pergunta.")
        # Só trocas concluídas entram na memória.
        historico.add_messages([HumanMessage(pergunta), AIMessage(saida["output"])])
        passos = [self._passo(acao, obs) for acao, obs in saida["intermediate_steps"]]
        return Resposta(saida["output"], passos)

    def limpar(self, sessao: str) -> None:
        self._memoria.limpar(sessao)

    def _calendario(self) -> str:
        # Evita que o LLM calcule datas como "sexta-feira".
        dias = [self._hoje() + timedelta(days=i) for i in range(8)]
        return ", ".join(f"{dia} ({DIAS_SEMANA[dia.weekday()]})" for dia in dias)

    @staticmethod
    def _passo(acao, observacao) -> Passo:
        pensamento = acao.log.split("Action:")[0].replace("Thought:", "").strip()
        return Passo(pensamento, acao.tool, str(acao.tool_input), str(observacao))
