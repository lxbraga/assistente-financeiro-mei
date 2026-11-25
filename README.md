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
- **Memória:** últimas 10 mensagens por sessão, com o ciclo ReAct completo.
- **Trava contra invenção:** valor em R$ que não veio de ferramenta ou do usuário gera nova tentativa e, persistindo, erro.
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

Cada caso foi executado 5 vezes com `gpt-4o-mini`, em 25/11/2026: **40 de 40 execuções OK** na versão final.

| Caso | Esperado | Observado | OK |
|---|---|---|---|
| 1. Situação do CNPJ 00.000.000/0001-91 | Ativa | Ativa, Banco do Brasil | 5/5 |
| 2. Boleto de R$ 1.200 vencido em 03/11/2026, pago em 25/11 | R$ 1.232,80 | R$ 1.232,80 | 5/5 |
| 3. "E se eu pagar só na sexta?" (memória) | R$ 1.233,60 | R$ 1.233,60 | 5/5 |
| 4. "E se a multa for de 10%?" (memória) | R$ 1.329,60 | R$ 1.329,60 | 5/5 |
| 5. R$ 5.000 pelo IPCA de jan. a out./2026 | R$ 5.204,84 | R$ 5.204,84 | 5/5 |
| 6. Cobrança de R$ 1.000, prazo em dia útil + encargos (encadeamento) | R$ 1.027,33 | R$ 1.027,33 | 5/5 |
| 7. CNPJ inválido | Avisa que é inválido | CNPJ inválido | 5/5 |
| 8. CNPJ não cadastrado | Avisa que não encontrou | Não encontrado | 5/5 |

O raciocínio da última rodada está em [docs/resultados.md](docs/resultados.md). API fora do ar e erros da OpenAI são cobertos pelo `pytest` (57 testes).

**Falhas encontradas nos testes e corrigidas**

| Falha | Causa | Correção |
|---|---|---|
| Caso 6 não concluía | LLM saía do formato ReAct | Aviso de formato e prompt mais claros |
| Caso 3 falhava na interface | LLM imitava as respostas prontas do histórico | Memória guarda o ciclo ReAct completo |
| Caso 4 dava valor inventado (R$ 1.236,00) | LLM respondia sem usar ferramenta | Todo valor em R$ é conferido com as ferramentas |

## Reflexão: agente x abordagem manual

| Tarefa | Sem o agente | Com o agente |
|---|---|---|
| Conferir CNPJ | Abrir o site da Receita e resolver o captcha | Uma pergunta |
| Boleto atrasado | Contar dias, checar feriados e calcular multa e juros | Uma pergunta |
| Novo cenário | Refazer a conta | "E se eu pagar na sexta?" |
| Correção pelo IPCA | Baixar a série e multiplicar mês a mês | Uma pergunta |

O agente **facilita** ao reunir fontes e cálculos em uma conversa e **possibilita** perguntas que combinam etapas, escolhendo as ferramentas e a ordem. O cálculo em código evita erros aritméticos do LLM, e o raciocínio visível permite conferir a resposta.

**Limitações:** feriados locais não entram, as APIs públicas podem falhar o LLM pode omitir um aviso da ferramenta e a trava cobre só valores em R$ (não datas e percentuais). Não substitui um contador.
