# NOTES — Métricas e Painel Administrativo

> Atualizado em 20/08/2026. Cobre a coleta de métricas no aplicativo (`SOURCE/`) e o painel
> Streamlit (`admin_py/` + `run_admin_streamlit.py`).

---

## 1. Onde as métricas são gravadas

Todo evento de métrica vai para a **coleção unificada** `user_metrics/{user_id}/metrics`, um
documento por evento, com ID cronológico (`YYYYMMDDHHMMSSmmm_{event_type}_{sufixo}`), gerado por
`FirebaseClientFirestore.save_metrics_client`.

| `event_type` | Emitido por | Quando |
|---|---|---|
| `pdf_analysis_completed` | `save_analysis_metrics` | Fim de uma análise de PDF |
| `chat_request_completed` | `save_chat_request_metrics` | Cada mensagem respondida no chat |
| `llm_feedback` | `save_feedback_data` | Confirmação do diálogo de avaliação |

Os três estão em `SOURCE/services/firebase_client.py`.

O painel sincroniza essa coleção para `admin_data/metrics/{user_id}/*.json`
(`local_data_manager.sync_cloud_data_to_local`) e a lê a partir do disco.

### Histórico: o chat ficava fora dos relatórios

Até 20/08/2026, `chat_view._log_single_metric_to_firestore_static` acumulava as métricas de cada
requisição no mapa `requests` do documento de sessão
(`user_metrics/{user_id}/chat_sessions/{chat_session_id}`). O sync do painel só varre
`.../metrics` — logo **todo o consumo do chat era invisível** nos indicadores, e o documento de
sessão crescia indefinidamente rumo ao limite de 1 MB do Firestore.

A gravação por requisição foi redirecionada para a coleção unificada, como
`chat_request_completed`, espelhando a estrutura de `pdf_analysis_completed` (mesmo bloco
`llm_analysis_metadata`) para que o analisador leia ambos com as mesmas colunas. O documento de
sessão continua registrando o contexto (arquivos carregados) e o resumo de encerramento.

**Consequência:** métricas de chat anteriores a essa data não aparecem no painel; elas seguem em
`chat_sessions` e precisariam de um sync/normalização próprios se houver interesse retroativo.

---

## 2. Política de privacidade do feedback

`save_feedback_data` recebe, para cada campo avaliado, o valor original da LLM e o valor final na
UI. **Nem todos podem ser persistidos.**

A regra está em `FEEDBACK_VALUE_SAFE_FIELD_TYPES` (`SOURCE/services/firebase_client.py`):

| Tipo de campo | `valor_original_llm` / `valor_atual_ui` | Motivo |
|---|---|---|
| `dropdown`, `radio_button`, `checkbox`, `textfield_valor` | **preservados** | Taxonomia fechada ou numérico — não transcrevem o documento |
| `textfield_multiline`, `textfield_lista`, `textfield` | **descartados** | Contêm trechos da peça analisada (nomes, CPFs, teor sigiloso) |

Para os campos descartados restam `llm_acertou` e, quando aplicável, `similaridade_pos_edicao`
(ROUGE-L) — suficiente para medir taxa de acerto, insuficiente para saber *o que* foi corrigido.

### Histórico: os valores foram apagados por um período

Entre a v0.5 e 20/08/2026 o código removia os valores **incondicionalmente**. Efeito nos dados
sincronizados:

| Versão do app | Feedbacks | Com valores antes/depois |
|---|---|---|
| 0.2 | 84 | 82 |
| 0.5.2 | 57 | **0** |

Nesse intervalo era possível saber que um campo foi corrigido, mas não para qual valor — o que
inviabiliza a matriz de confusão e a leitura de erros recorrentes. A restauração seletiva
recuperou essa capacidade **daqui para a frente**; os registros de 0.5.2 permanecem sem valores.

Por isso as visões que dependem desse par exibem um aviso explicativo quando o recorte não tem
dados, em vez de aparecerem vazias sem explicação.

---

## 3. Estrutura do painel (`admin_py/`)

```
admin_py/
├── dashboard_analyzer.py   # Carga, filtro global e agregações de uso
├── feedback_analyzer.py    # Normalização e análise dos eventos de feedback
├── dashboard_plotter.py    # Somente figuras Plotly
└── local_data_manager.py   # Sync Firestore/Storage -> admin_data/
```

### Convenção: filtro único, agregações puras

`dashboard_analyzer.apply_filters` é o **único** ponto de recorte (período, usuário, modelo,
provedor). Todas as funções de agregação recebem o DataFrame já filtrado.

Antes, cada função refazia internamente o corte de período enquanto o filtro de usuário era
aplicado por fora, no `run_admin_streamlit.py` — não havia garantia de que dois gráficos lado a
lado estivessem olhando para o mesmo recorte. **Não reintroduzir filtragem dentro das
agregações.**

### `feedback_analyzer` e a tabela longa

O evento `llm_feedback` é aninhado: `details.feedback_fields` traz uma entrada por campo (19 por
submissão, tipicamente). `build_feedback_long_table` converte tudo em **uma linha por (submissão,
campo)** e enriquece com modelo/provedor.

Essa tabela é a base única da visão gerencial, da visão de detalhe e da matriz de confusão. Toda
nova análise de feedback deve partir dela, não do JSON aninhado.

### Cruzamento feedback ↔ análise

`details.analysis_timestamp_ref` casa com `llm_analysis_metadata.event_timestamp_iso` da análise
que originou o feedback, dentro do mesmo usuário. **Cobertura medida: 139 de 141 (99%)** nos dados
históricos. É o que permite atribuir taxa de acerto por modelo.

---

## 4. Decisões de exibição

**Custo é condicional.** `has_cost_data()` decide se os indicadores e gráficos de custo aparecem.
O uso migrou para o provedor interno `LLM_PF`, cujo custo é sempre zero: em 20/08/2026, as 108
requisições mais recentes custaram $0,00, contra $12,43 acumulados nas 716 análises OpenAI
históricas. Manter painéis de custo visíveis nesse cenário ocupava metade da tela com "$0.00".
Quando ocultos, o espaço vai para o **consumo de tokens**, que é a métrica de capacidade relevante
com o provedor interno.

**Taxa de acerto no lugar de contagem absoluta.** O gráfico anterior ("Top 5 campos mais
corrigidos") mostrava contagens brutas; um campo com 34 correções em 141 avaliações e outro com 34
em 40 são problemas de magnitudes diferentes, indistinguíveis assim. A visão atual normaliza e
expõe o número de avaliações no hover.

**Custo por modelo no lugar de "Embeddings × Análise LLM".** `calculated_embedding_cost_usd`
existe em **2 de 824** análises, então aquela pizza mostrava ~100%/0% sempre.

**Granularidade selecionável.** O filtro anterior oferecia 7/30/"desde o início"; a última opção
gerava ~10.000 pontos diários no eixo X. Agora o eixo agrupa por dia, semana ou mês.

**"Usuários ativos" no lugar de "total de usuários".** O indicador anterior contava diretórios em
`admin_data/` e não reagia a nenhum filtro — exibia 27 fixo. Agora conta usuários distintos com
requisição no recorte.

---

## 5. Armadilhas conhecidas

**`pd.to_datetime` precisa de `format='ISO8601'`.** Sem ele, o pandas (2.x) infere um único
formato a partir do primeiro registro e converte para `NaT` todos os que não casarem — que são
então descartados por `dropna`. Como praticamente todos os timestamps gravados têm microssegundos,
um evento cujo `isoformat()` os omita (microssegundos exatamente zero) sumiria **em silêncio**.
Detectado ao injetar eventos de chat sintéticos: 966 arquivos em disco, 965 carregados.
`load_all_metrics_to_dataframe` agora loga quantos eventos foram descartados.

**Valores de campo são heterogêneos.** Os dropdowns trazem `str` e `valor_apuracao` traz `float`.
Uma coluna pandas com essa mistura é `object`, e o Arrow — usado pelo Streamlit para serializar
tabelas — a rejeita com *"Expected bytes, got a 'float' object"*, derrubando a renderização.
`feedback_analyzer._as_text` uniformiza na construção da tabela longa; não reintroduzir os valores
brutos nas colunas exibidas.

**Colunas de métrica podem não existir.** O schema evoluiu entre versões do app. Acessar colunas
numéricas sempre via `dashboard_analyzer._col()`, que devolve uma série de zeros quando a coluna
está ausente do recorte.

**`openpyxl` é obrigatório para a exportação.** Está declarado em `pyproject.toml` e no
`poetry.lock`, mas se faltar no virtualenv os botões "Exportar para Excel" falham silenciosamente
(o helper captura a exceção, loga e devolve um buffer vazio). Sintoma: download de arquivo vazio,
com `ERROR Falha ao exportar para Excel: No module named 'openpyxl'` no log.

---

## 6. Como rodar o painel

```
streamlit run run_admin_streamlit.py --logger.level INFO
```

Roda **exclusivamente local** — o serviço `opera-admin` está comentado no `docker-compose.yml`
desde a migração para a VM. Requer as credenciais Firebase locais e o diretório `admin_data/`
populado (botão "Sincronizar Dados da Nuvem Agora", na aba *Dados & Logs*).
