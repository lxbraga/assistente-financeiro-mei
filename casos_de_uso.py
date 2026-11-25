"""Roda os casos de uso com o LLM real e grava docs/resultados.md."""

from datetime import date
from pathlib import Path

from app.agent import AssistenteFinanceiro, ErroAssistente, criar_llm

HOJE = date(2026, 11, 25)  # data fixa para o resultado ser comparável

# (caso, sessão, pergunta, trechos esperados na resposta)
CASOS = [
    ("1. Situação de CNPJ", "cnpj", "Qual a situação do CNPJ 00.000.000/0001-91?", ["ativa"]),
    ("2. Boleto atrasado", "boleto", "Um boleto de R$ 1.200 venceu em 03/11/2026. Quanto devo hoje?", ["1.232,80"]),
    ("3. Memória", "boleto", "E se eu pagar só na sexta?", ["1.233,60"]),
    ("4. Correção pelo IPCA", "ipca", "Corrija R$ 5.000 pelo IPCA de janeiro a outubro de 2026.", ["5.204,84"]),
    (
        "5. Encadeamento",
        "cadeia",
        "Emiti uma cobrança de R$ 1.000 em 30/10/2026 com prazo de 1 dia útil. Quanto o cliente deve se pagar hoje?",
        ["1.027,33"],  # vence em 03/11: 22 dias, multa 20,00 e juros 7,33
    ),
    ("6. CNPJ inválido", "erro", "Consulte o CNPJ 11.111.111/1111-11.", ["inválido"]),
    ("7. CNPJ não cadastrado", "erro2", "Consulte o CNPJ 99.999.999/0001-91.", ["não", "encontrado"]),
]


def main() -> None:
    assistente = AssistenteFinanceiro(criar_llm(), hoje=lambda: HOJE)
    linhas, aprovados = ["# Resultados dos casos de uso\n"], 0
    for caso, sessao, pergunta, esperados in CASOS:
        try:
            resposta = assistente.perguntar(pergunta, sessao)
            texto, passos = resposta.texto, resposta.passos
        except ErroAssistente as exc:
            texto, passos = f"ERRO: {exc}", []
        ok = all(trecho in texto.lower() for trecho in esperados)
        aprovados += ok
        print(f"{'OK   ' if ok else 'FALHA'} {caso}: {texto}")

        linhas += [f"## {caso}: {'OK' if ok else 'FALHA'}\n", f"**Pergunta:** {pergunta}\n", "```"]
        for p in passos:
            linhas += [f"Thought: {p.pensamento}", f"Action: {p.ferramenta}", f"Action Input: {p.entrada}", f"Observation: {p.observacao}"]
        linhas += ["```\n", f"**Resposta:** {texto}\n"]

    linhas.insert(1, f"{aprovados} de {len(CASOS)} casos OK. Data usada como hoje: {HOJE:%d/%m/%Y}.\n")
    Path("docs").mkdir(exist_ok=True)
    Path("docs/resultados.md").write_text("\n".join(linhas), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except ErroAssistente as exc:
        raise SystemExit(str(exc))
