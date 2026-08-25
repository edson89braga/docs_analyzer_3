# NOTES — Endpoint LLM da PF (`provider = "llm_pf"`)

Comportamento observado do endpoint interno que serve o modelo do ÓPERA. Tudo aqui foi **medido
diretamente contra o endpoint**, não inferido da documentação do vLLM ou do Qwen.

- **Endpoint:** `http://llm.pf.gov.br:31893/v1` (desktop / `is_local_mode()`) e
  `http://10.2.2.10:31893/v1` (servidor Docker na VM).
- **Modelo:** `Qwen3.5-35B-A3B-FP8`, servido por vLLM (`owned_by: "vllm"`, `root: "/model"`).
- **Data das medições:** 13/08/2026.

---

## 1. Janela de contexto

`GET /v1/models` informa `max_model_len = 131072`.

`SOURCE/settings.py` usa `LLM_PF_CONTEXT_WINDOW = 128_000` — 3.072 tokens **abaixo** do real. É
conservador e seguro (nunca gera 400 por otimismo); mantido assim de propósito, mas registre-se que
a folga existe caso um dia seja preciso recuperá-la.

---

## 2. Modo de raciocínio (thinking)

### Como se liga

Somente por `extra_body={"chat_template_kwargs": {"enable_thinking": True}}`.

- O **default do servidor é thinking DESLIGADO** (requisição sem `chat_template_kwargs` responde
  direto, sem raciocínio).
- O soft switch `/no_think` no texto **não funciona mais** no Qwen3.5.

### Como NÃO se limita

Testado e **ignorado pelo modelo** (aceito pela API, sem erro, sem efeito):

| Tentativa | Resultado |
|---|---|
| `chat_template_kwargs: {"thinking_budget": 512}` | raciocínio *cresceu* para 14.427 chars |
| `reasoning_effort: "low"` (top-level) | 10.261 chars de raciocínio |
| `reasoning_effort: "minimal"` (top-level) | 11.687 chars de raciocínio |

Ou seja: **o raciocínio é liga/desliga, sem graduação**. O campo `reasoning_effort` da UI do ÓPERA
(`low`/`medium`/`high`/`minimal`) é convertido em booleano no código justamente por isso — apenas
`minimal` desliga o raciocínio (`ai_orchestrator.py`, `chat_llm_orchestrator.py`).

### Quanto custa

Para um prompt trivial de 48 tokens, o raciocínio consumiu **~2.700 tokens** antes da resposta
final. Não há teto natural: o custo escala com a complexidade do documento e do schema pedido.

### Onde vem o raciocínio na resposta

No campo **`message.reasoning`** — **não** em `message.reasoning_content` (nome usado pela DeepSeek
e por outros provedores compatíveis com a API OpenAI), e **não** em `<think>...</think>` dentro de
`content` (o servidor tem reasoning parser configurado e já entrega `content` limpo).

Chaves presentes em `message`: `role`, `content`, `refusal`, `annotations`, `audio`,
`function_call`, `reasoning`.

> Este foi o bug de 13/08/2026: o fallback lia `reasoning_content`, sempre obtinha `None`, e a tela
> de análise ficava vazia. Corrigido lendo `reasoning` com `reasoning_content` como alternativa.

### A falha clássica: `content` vazio com `finish_reason='length'`

Se `max_tokens` acabar durante o raciocínio, a API devolve `content = ""` (string vazia, não `None`)
e `finish_reason = "length"` — **sem nenhum JSON**. Medições com prompt trivial:

| `max_tokens` | thinking | `finish_reason` | `content` |
|---|---|---|---|
| 2.000 | ON | `length` | vazio |
| 8.000 | ON | `stop` | JSON completo (2.985 tokens usados) |
| 2.000 | OFF | `stop` | JSON completo (113 tokens usados) |

**Não é culpa do `response_format`/`json_schema` strict** — o mesmo ocorre sem schema algum. É o
raciocínio consumindo o orçamento inteiro.

Por isso `LLM_PF_MAX_OUTPUT_TOKENS_THINKING = 24_000` é aplicado quando o raciocínio está ativo
(ver `compute_llm_pf_max_output_tokens`), contra `LLM_PF_MAX_OUTPUT_TOKENS = 8_000` do modo direto.
Validado: com thinking + schema strict o teto alto retorna `finish_reason=stop` e JSON completo.

> **Revisão de 14/08/2026:** os valores eram 32k/16k e a truncagem de entrada reservava sempre os
> 16k. Foram reduzidos para 24k/8k **e** passaram a ser reservados conforme o modo (ver seção 3):
> o dimensionamento anterior era generoso frente ao consumo observado (~8,8k de saída num lote real
> com raciocínio, ~2,3k sem) e a reserva fixa em 16k deixava o modo pensante depender de folga.

---

## 3. Contagem de tokens — tiktoken subestima muito

`SOURCE/core/ai_orchestrator.py` estima os tokens de entrada com **tiktoken**, que usa o tokenizer da
OpenAI, não o do Qwen. O desvio medido é **muito maior** que a margem configurada
(`LLM_PF_TOKEN_SAFETY_MARGIN = 0.10`):

| Amostra | tiktoken | real (Qwen) | desvio |
|---|---|---|---|
| Lote real de 200 páginas (log de produção 13/08/2026) | 78.321 | 94.861 | **+21,1%** |
| Texto jurídico sintético (ofício, CPFs, valores, nº de processo) | 63.001 | 82.224 | **+30,5%** |

A causa é o perfil do texto: português com muitos números, CPFs, matrículas e nomes próprios
fragmenta mal no vocabulário da OpenAI.

**Consequência:** num lote que *encha* o orçamento automático de entrada, o input real pode passar
de 110k tokens e comer a folga da janela que o modo pensante precisa — a truncagem "cabe" no papel e
não cabe na prática.

### `POST /tokenize` — o tokenizer exato, sem baixar nada

O endpoint expõe `/tokenize` (fora do prefixo `/v1`), que usa **o tokenizer do próprio modelo
carregado**:

```jsonc
// POST http://llm.pf.gov.br:31893/tokenize
{"model": "Qwen3.5-35B-A3B-FP8", "prompt": "texto..."}
// ou, aplicando o chat template (conta o overhead das tags de papel):
{"model": "Qwen3.5-35B-A3B-FP8", "messages": [{"role": "user", "content": "..."}]}

// Resposta:
{"count": 82224, "max_model_len": 131072, "tokens": [...], "token_strs": null}
```

Com `messages`, o template é aplicado e o `count` inclui o overhead das tags (16 tokens para uma
mensagem de 3 palavras) — é exatamente o número que a API valida contra a janela.

**Latência medida: 0,54 s para um payload de 199 KB (~82k tokens).** Uma chamada por análise é
irrelevante diante dos ~2 min da inferência.

Vantagens sobre baixar o tokenizer do HuggingFace: sem dependência nova (`transformers`/
`tokenizers`), sem arquivo para embutir no PyInstaller, sem depender de acesso ao HF pelo proxy da
PF, e sem risco de divergência entre o tokenizer baixado e o que o servidor de fato usa.

Limitação: é uma chamada de rede, então não serve para contagem página a página dentro do loop de
truncagem do `pdf_processor` (200 chamadas).

### Como está implementado

Duas chamadas ao `/tokenize` por análise, ambas com fallback silencioso para tiktoken + margem fixa
se o endpoint não responder (`count_tokens_llm_pf` devolve `None` e ninguém propaga o erro):

1. **`compute_llm_pf_max_output_tokens`** conta o prompt já montado (`messages`, com chat template)
   e calcula `max_tokens = janela - contagem_exata - LLM_PF_EXACT_COUNT_BUFFER`. Elimina o chute no
   ponto em que ele custa 400 ou resposta truncada.
2. **`measure_llm_pf_token_drift`** mede a razão `tokens_reais / tokens_tiktoken` sobre o texto
   extraído **daquele documento** e a passa como `drift_ratio` para
   `compute_llm_pf_auto_token_limit`, que converte a capacidade real da janela em unidades de
   tiktoken — que é como o `pdf_processor` conta as páginas. Chamado em `nc_analyze_view` e
   `chat_view`, sempre **depois** da extração (antes não há texto para medir).

Efeito medido num lote sintético de texto jurídico (desvio 1,305x): orçamento de entrada cai de
85.817 para 69.844 tokens (−18,6%) — menos páginas, porém páginas que **de fato cabem**. E o
`max_tokens` com raciocínio ficou em 29.251 em vez dos 32.000 nominais: sem a contagem exata, os
32.000 teriam estourado a janela (98.237 + 32.000 > 128.000) e gerado um 400.

3. **Painel 'Dados do Processamento'** (`nc_analyze_view` e `chat_view`): os três totais de tokens
   (`total_tokens_before_filter`, `total_tokens_before_truncation`, `final_aggregated_tokens`) são
   contados pelo `pdf_processor` em tiktoken e convertidos por `scale_tokens_to_real` antes de
   irem para a UI — sem isso o painel mostrava ~25% a menos do que o modelo enxerga, e divergia das
   métricas pós-análise, que já vinham reais do `usage` da API. O "Percentual de Tokens Suprimidos"
   é razão entre duas contagens, então independe da unidade. Por isso o desvio é medido sempre que
   o provider é `llm_pf`, e não apenas no modo de truncagem automática.

   > Os mesmos campos são persistidos no Firestore (`firebase_client._log_*`), então registros
   > anteriores a 13/08/2026 estão em unidades de tiktoken e os posteriores no tokenizer real —
   > comparações históricas dessas séries precisam considerar o degrau de ~25%.

### Reserva de saída por modo de raciocínio (14/08/2026)

Até 13/08/2026 a truncagem reservava sempre `LLM_PF_MAX_OUTPUT_TOKENS`, e o modo pensante contava
com a folga que sobrasse na janela. Num lote real de 222 páginas isso produziu `max_tokens = 18.803`
contra os 32k nominais — a reserva de 16k foi respeitada, mas os 32k do modo pensante nunca haviam
sido reservados. `compute_llm_pf_auto_token_limit` passou a receber `enable_thinking` e a reservar o
teto do modo em vigor, descontando também `LLM_PF_EXACT_COUNT_BUFFER` (sem isso o `min` de
`compute_llm_pf_max_output_tokens` cortava 512 tokens do nominal justo nos lotes cheios).

O modo considerado é o selecionado na etapa **'Processar Conteúdo'** (ou na otimização do chat).
Trocar o nível de reflexão depois, antes de 'Solicitar Análise', deixa a reserva dimensionada para o
modo anterior — situação detectada pelo aviso `[MAX_OUTPUT_TOKENS]`, cuja saída agora recomenda
reprocessar o conteúdo. `is_thinking_enabled` centraliza a regra `!= "minimal"`, antes duplicada em
`ai_orchestrator` e `chat_llm_orchestrator`, para que reserva e requisição nunca divirjam.

Orçamentos resultantes com overhead de prompt de ~11k e desvio 1,217x (lote de 222 páginas):

| Modo | Reserva | Orçamento de entrada | `max_tokens` obtido |
|---|---|---|---|
| Antes (qualquer) | 16.000 | 81.058 tiktoken (~98,6k reais) | 18.803 (truncou) |
| Sem raciocínio | 8.000 | 87.211 tiktoken (~106k reais) | 8.000 (íntegro) |
| Com raciocínio | 24.000 | 74.064 tiktoken (~90k reais) | 24.000 (íntegro) |

> O log `[AUTO_TOKEN_LIMIT]` imprime o orçamento em **tiktoken** (unidade em que o `pdf_processor`
> trunca), enquanto o painel 'Dados do Processamento' mostra o equivalente em tokens reais — a
> diferença entre os dois números é exatamente o `drift_ratio`, não uma violação do orçamento. Para
> evitar a confusão, a linha de log passou a trazer as duas unidades.

---

## 4. Resiliência já implementada

- `create_llm_pf_completion` detecta erro 400 de contexto excedido, extrai a contagem **real** de
  entrada da mensagem de erro e repete a chamada uma vez com `max_tokens` recalculado. Isso protege
  contra a subestimação do tiktoken descrita acima — ao custo de uma requisição perdida.
- Formatos de erro cobertos por `parse_context_length_error` (vLLM antigo, vLLM atual e OpenAI).

## 5. Uso de tokens reportado

`usage` traz apenas `prompt_tokens`, `completion_tokens` e `total_tokens`
(`prompt_tokens_details: None`, sem `completion_tokens_details`).

**Os tokens de raciocínio estão embutidos em `completion_tokens`** — confirmado: uma resposta com
~500 chars de `content` e 9.629 chars de `reasoning` reportou `completion_tokens = 2843`. Logo, o
campo `reasoning_tokens` do `token_usage_info` fica em 0 por falta de dado do servidor, mas o total
de saída registrado no Firestore **não perde** os tokens gastos pensando.
