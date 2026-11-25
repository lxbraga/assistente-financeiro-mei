"""Agente ReAct: une LLM, ferramentas e memória."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

import openai
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.memory import Memoria
from app.prompts import PROMPT
from app.tools import TOOLS
from app.tools.comum import ler_numero
from app.tools.dias_uteis import DIAS_SEMANA

MAX_ITERACOES = 8
FORMATO_INVALIDO = (
    "Formato inválido. Se já sabe a resposta, escreva 'Final Answer:' seguido dela. "
    "Senão, escreva 'Action:' e 'Action Input:'."
)
EXIGIR_TOOL = "(Obtenha os valores com uma ferramenta antes de responder.)"
NUMERO = r"\d{1,9}(?:\.\d{3})*(?:[.,]\d{1,2})?(?!\d)"


def _descrever_tools(tools: list[BaseTool]) -> str:
    # Sem a assinatura: o LLM confundia o parâmetro interno com um campo da entrada.
    return "\n".join(f"{t.name}: {t.description}" for t in tools)


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
            agent=create_react_agent(llm, TOOLS, PROMPT, tools_renderer=_descrever_tools),
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
        saida = self._executar(pergunta, historico.messages)
        if self._tem_valor_sem_fonte(saida, pergunta, historico.messages):
            saida = self._executar(f"{pergunta}\n\n{EXIGIR_TOOL}", historico.messages)
            if self._tem_valor_sem_fonte(saida, pergunta, historico.messages):
                raise ErroAssistente("Não consegui confirmar os valores. Reformule a pergunta.")

        # Guarda o ciclo ReAct inteiro: se visse só respostas prontas, o LLM as
        # imitaria, deixando de usar ferramentas e o formato.
        ciclo = [f"{a.log.strip()}\nObservation: {o}" for a, o in saida["intermediate_steps"] if a.tool != "_Exception"]
        resposta = "\n".join([*ciclo, f"Final Answer: {saida['output']}"])
        historico.add_messages([HumanMessage(pergunta), AIMessage(resposta)])
        passos = [self._passo(acao, obs) for acao, obs in saida["intermediate_steps"]]
        return Resposta(saida["output"], passos)

    def _executar(self, pergunta: str, mensagens: list[BaseMessage]) -> dict:
        try:
            saida = self._agente.invoke(
                {"pergunta": pergunta, "historico": mensagens, "calendario": self._calendario()}
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
        return saida

    @staticmethod
    def _tem_valor_sem_fonte(saida: dict, pergunta: str, mensagens: list[BaseMessage]) -> bool:
        """Todo valor em R$ da resposta deve vir de uma ferramenta ou do usuário."""
        observacoes = [str(obs) for _, obs in saida["intermediate_steps"]]
        fontes = " ".join([pergunta, *observacoes, *(str(m.content) for m in mensagens)])
        conhecidos = {ler_numero(n) for n in re.findall(NUMERO, fontes)}
        citados = re.findall(rf"R\$\s*({NUMERO})", saida["output"])
        return any(ler_numero(n) not in conhecidos for n in citados)

    def limpar(self, sessao: str) -> None:
        self._memoria.limpar(sessao)

    def _calendario(self) -> str:
        # Evita que o LLM calcule datas como "sexta-feira".
        dias = [self._hoje() + timedelta(days=i) for i in range(8)]
        return ", ".join(f"{dia} ({DIAS_SEMANA[dia.weekday()]})" for dia in dias)

    @staticmethod
    def _passo(acao, observacao) -> Passo:
        if acao.tool == "_Exception":  # o LLM saiu do formato ReAct e foi avisado
            texto = acao.log.removeprefix("Could not parse LLM output: `").split("`\nFor troubleshooting")[0]
            return Passo(texto, "(formato inválido)", "-", str(observacao))
        pensamento = acao.log.split("Action:")[0].replace("Thought:", "").strip()
        return Passo(pensamento, acao.tool, str(acao.tool_input), str(observacao))
