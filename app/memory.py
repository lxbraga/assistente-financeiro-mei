"""Memória conversacional: um histórico por sessão."""

from langchain_core.chat_history import InMemoryChatMessageHistory

MAX_MENSAGENS = 10


class HistoricoLimitado(InMemoryChatMessageHistory):
    """Guarda só as últimas mensagens, para o prompt não crescer sem limite."""

    def add_messages(self, messages) -> None:
        super().add_messages(messages)
        self.messages = self.messages[-MAX_MENSAGENS:]


class Memoria:
    def __init__(self) -> None:
        self._sessoes: dict[str, HistoricoLimitado] = {}

    def obter(self, sessao: str) -> HistoricoLimitado:
        return self._sessoes.setdefault(sessao, HistoricoLimitado())

    def limpar(self, sessao: str) -> None:
        self._sessoes.pop(sessao, None)
