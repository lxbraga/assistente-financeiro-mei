# Assistente Financeiro para MEI

Agente ReAct em LangChain que responde dúvidas financeiras com dados oficiais e cálculos feitos por ferramentas.

## Problema e solução

**Problema:** o MEI precisa conferir fornecedores, calcular atrasos, prazos e correções, consultando vários sites e fazendo contas à mão. Um LLM sozinho inventaria números e não tem dados atuais.

**Objetivo:** responder em linguagem natural, com todo valor vindo de uma ferramenta.

**Público-alvo:** MEIs e pequenos negócios sem departamento financeiro.

**Funcionalidades**

| Ferramenta | Função | Fonte |
|---|---|---|
| `consultar_cnpj` | Situação cadastral de uma empresa | BrasilAPI |
| `calcular_dias_uteis` | Prazo em dias úteis | BrasilAPI (feriados) |
| `calcular_encargos_atraso` | Multa, juros e total de conta atrasada | Cálculo local |
| `corrigir_pelo_ipca` | Correção pela inflação | Banco Central |

**Como funciona**
- **LLM:** OpenAI `gpt-4o-mini`, temperatura 0. Boa relação entre custo e capacidade de seguir o formato ReAct.
- **ReAct:** `create_react_agent` + `AgentExecutor` alternam Thought, Action e Observation, com até 8 iterações.
- **Memória:** últimas 10 mensagens por sessão, enviadas no prompt.
- **Erros:** falhas de entrada ou API voltam ao agente como Observation; falhas da OpenAI viram mensagem na tela.

**Regras:** multa de 2% e juros simples de 1% ao mês (alteráveis na pergunta); só feriados nacionais; IPCA inclui os meses inicial e final; sócios e contatos do CNPJ não são enviados ao LLM.

```
app/agent.py       # agente ReAct
app/memory.py      # memória por sessão
app/prompts.py     # prompt ReAct
app/config.py      # configurações do .env
app/tools/         # ferramentas
streamlit_app.py   # interface
casos_de_uso.py    # casos de uso com o LLM real
tests/             # testes sem rede e sem chave
```

## Execução

Requer Python 3.11+ e uma chave da OpenAI.

```bash
python3 -m venv .venv          # confira com python3 --version: 3.11 ou superior
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # preencha OPENAI_API_KEY
streamlit run streamlit_app.py
```

Testes automáticos: `pytest`. Casos de uso com o LLM real: `python casos_de_uso.py`.

## Casos de uso e resultados

| Caso | Esperado | Observado |
|---|---|---|
| 1. Situação do CNPJ 00.000.000/0001-91 | Ativa | Pendente |
| 2. Boleto de R$ 1.200 vencido em 03/11/2026, pago em 25/11 | R$ 1.232,80 | Pendente |
| 3. "E se eu pagar só na sexta?" (memória) | R$ 1.233,60 | Pendente |
| 4. R$ 5.000 pelo IPCA de jan. a out./2026 | R$ 5.204,84 | Pendente |
| 5. Prazo em dia útil + encargos (encadeamento) | R$ 1.027,33 | Pendente |
| 6. CNPJ inválido | Avisa que é inválido | Pendente |
| 7. CNPJ não cadastrado | Avisa que não encontrou | Pendente |

O raciocínio completo de cada caso fica em [docs/resultados.md](docs/resultados.md). API fora do ar e erros da OpenAI são cobertos pelo `pytest`.

## Reflexão: agente x abordagem manual

| Tarefa | Sem o agente | Com o agente |
|---|---|---|
| Conferir CNPJ | Abrir o site da Receita e resolver o captcha | Uma pergunta |
| Boleto atrasado | Contar dias, checar feriados e calcular multa e juros | Uma pergunta |
| Novo cenário | Refazer a conta | "E se eu pagar na sexta?" |
| Correção pelo IPCA | Baixar a série e multiplicar mês a mês | Uma pergunta |

O agente **facilita** ao reunir fontes e cálculos em uma conversa e **possibilita** perguntas que combinam etapas, escolhendo as ferramentas e a ordem. O cálculo em código evita erros aritméticos do LLM, e o raciocínio visível permite conferir a resposta.

**Limitações:** feriados locais não entram, as APIs públicas podem falhar e o LLM pode interpretar mal uma pergunta ambígua. Não substitui um contador.
