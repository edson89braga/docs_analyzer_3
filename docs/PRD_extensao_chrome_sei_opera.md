# PRD Técnico — Extensão Chrome "ÓPERA ⇄ SEI"

**Projeto:** ÓPERA — IA Assistente (`Sist_Opera`, v0.5.2) · Integração com SEI 4.0 (PF)
**Documento:** Product Requirements Document — especificação para implementação
**Data:** 27/08/2026
**Status:** Proposta técnica. Nenhum código implementado nesta etapa.

---

## Convenção de marcação

Cada afirmação relevante está marcada quanto à sua natureza:

| Marca | Significado |
|---|---|
| `[PROVADO]` | Verificado diretamente no código-fonte lido (arquivo/linha citados). |
| `[REQUISITO]` | Comportamento obrigatório da solução; precisa ser construído. |
| `[RECOMENDAÇÃO]` | Escolha de projeto sugerida, com alternativa registrada. |
| `[HIPÓTESE]` | Plausível, **não** verificado contra código ou HTML real. |
| `[A VALIDAR]` | Depende de teste em ambiente real (SEI de produção / VM PF). |

A seção 15 consolida todas as marcações.

**Fontes analisadas:**
- `SOURCE/flet_ui/views/nc_analyze_view.py` (3.970 linhas), `SOURCE/core/{pdf_processor,ai_orchestrator,doc_generator,prompts}.py`, `SOURCE/flet_ui/components/components.py` (`ManagedFilePicker`), `run_server.py`, `docker-compose.yml`, `SOURCE/settings.py`.
- `API_PF/scripts_epol/rotina_epol_1/SOURCE/clients/sei/{client.py,parser.py}` (2.582 + 1.416 linhas) e `docs/NOTES_Sei.md` (manual de implementação do scraper SEI).
- Pacote `flet 0.28.3` instalado (`flet/fastapi`, `flet_web/fastapi/*`).

---

## 1. Visão geral

### 1.1 Problema atual

O fluxo de análise de Notícia-Crime hoje é inteiramente manual e atravessa dois sistemas que não se conversam:

1. Abrir o processo no SEI e identificar as peças relevantes na árvore de documentos.
2. Baixar cada peça para o disco local (PDFs nativos, anexos, e documentos internos que exigem o fluxo "Gerar PDF").
3. Abrir o ÓPERA, clicar em "Carregar Arquivo(s)", selecionar os PDFs no diálogo do SO, aguardar o upload de cada um.
4. Clicar em "Processar Conteúdo" e em "Solicitar Análise".
5. Revisar e corrigir os campos estruturados devolvidos pela LLM.
6. Exportar o DOCX (download pelo navegador).
7. Voltar ao SEI e criar/anexar o documento no processo manualmente.

Custos concretos: proliferação de cópias de documentos sigilosos no disco do usuário; risco de omitir peça relevante ou trocar a ordem (a ordem é semanticamente relevante para a agregação de texto); tempo de operação dominado por transferência manual; e ausência de vínculo rastreável entre o NUP de origem e a peça produzida.

### 1.2 Objetivo da extensão

Reduzir as sete etapas a três interações humanas: **(a)** informar/confirmar o NUP; **(b)** revisar e corrigir a análise no ÓPERA; **(c)** confirmar a produção e o envio da peça ao SEI como rascunho.

Todo o transporte de arquivos (SEI → ÓPERA → SEI) deve ocorrer sem download intermediário no disco do usuário e sem manipulação do diálogo de arquivos do sistema operacional.

### 1.3 Usuários / personas

| Persona | Descrição | Necessidade dominante |
|---|---|---|
| **Analista de triagem** (primária) | Servidor(a) que recebe NCs/expedientes no SEI e produz a peça de análise. Usa o ÓPERA diariamente pelo navegador, na rede corporativa. | Velocidade; confiança de que nenhuma peça relevante ficou de fora. |
| **Chefe de unidade** (secundária) | Revisa a peça antes de assinar. | Garantia de que o documento chega ao SEI como **rascunho não assinado**. |
| **Administrador/TI** (suporte) | Mantém VM, containers e a distribuição da extensão/bridge. | Instalação previsível; sem portas novas expostas; sem credenciais persistidas. |

### 1.4 Benefícios esperados

- Eliminação do ciclo download → upload manual, a maior fatia de tempo ocioso do fluxo atual.
- Redução da superfície de exposição de documentos sigilosos: nenhuma cópia permanente no disco do usuário.
- Rastreabilidade: cada análise passa a ter NUP de origem, e cada peça produzida tem destino registrado.
- Padronização da seleção de peças, com regras explícitas em vez de julgamento ad hoc.
- Preservação da revisão humana: a extensão nunca assina documentos.

### 1.5 Escopo

**Dentro do escopo**

- Extensão Chrome MV3 com popup de operação.
- Obtenção das peças de um NUP a partir da árvore de documentos do SEI, reutilizando `SeiClient`/`SeiArvoreParser`.
- Transferência das peças para a sessão ÓPERA do usuário sem gravação em disco no cliente.
- Acionamento remoto do pipeline `processar + analisar` da view `nc_analyze_view.py`.
- Acompanhamento de progresso e erros pela extensão.
- Produção da peça a partir dos dados **já corrigidos pelo usuário** na UI.
- Inserção da peça no NUP como **rascunho, sem assinatura**.
- Novos endpoints REST no ÓPERA (a construir) e um serviço-ponte local (a construir).

**Fora do escopo (explicitamente)**

- Assinatura de documentos no SEI — nunca automática.
- Conclusão, tramitação ou andamento de processos.
- Marcadores e anotações (embora implementados no `SeiClient`, não serão expostos).
- Login automatizado no SEI; a extensão nunca coleta a senha do usuário.
- Alterações no fluxo de chat sobre documentos (`chat_view.py`).
- Suporte a navegadores fora da família Chromium.
- Reescrita do `pdf_processor.py` como pacote, adoção de LangChain ou qualquer padrão da refatoração apartada — ver `CLAUDE.md` §0.
- Processamento em lote de múltiplos NUPs numa mesma operação (uma análise = um NUP).
- OCR ou tratamento de mídia não-PDF trazida do SEI (ZIP, vídeo, planilhas): sinalizados, não processados.

---

## 2. Fluxo funcional completo

### 2.1 Diagrama do fluxo

```
┌─ PRÉ-CONDIÇÕES ──────────────────────────────────────────────────────────┐
│ P1. Aba do ÓPERA aberta, usuário autenticado, na view "Análise de NC"    │
│ P2. Aba do SEI aberta, sessão SIP/SEI válida (PHPSESSID ativo)           │
│ P3. Bridge local instalada e respondendo                                 │
│ P4. Extensão pareada com a sessão Flet do ÓPERA (código de pareamento)   │
└──────────────────────────────────────────────────────────────────────────┘
        │
        ▼
  [E1]  Usuário informa o NUP no popup (ou confirma o detectado na aba SEI)
        │
        ▼
  [E2]  Validação sintática do NUP (máscara + dígito verificador) ...... ERR-01
        │
        ▼
  [E3]  Obtenção do link_processo ORGÂNICO (§5.2) ............... ERR-02/03/04
        │
        ▼
  [E4]  Bridge: GET link_processo → frameset → GET ifrArvore
        SeiArvoreParser.extract_documentos()  ........................ ERR-05
        Expansão de pastas paginadas (POST frmArvore)
        │
        ▼
  [E5]  Classificação e pré-seleção das peças (§3.4) → lista no popup
        │
        ▼
  [E6]  Usuário confirma/ajusta a seleção → [ Enviar ao ÓPERA ]
        │
        ▼
  [E7]  Bridge: download peça a peça, em memória ............. ERR-06/07/08
        (nativos → link_download; internos → link_gerar_pdf)
        │
        ▼
  [E8]  Bridge → POST /api/v1/sessions/{code}/documents  ............ ERR-09
        ÓPERA grava em UPLOAD_TEMP_DIR e injeta em KEY_SESSION_PDF_FILES_ORDERED
        │
        ▼
  [E9]  Bridge → POST /api/v1/sessions/{code}/analysis:start .. ERR-10/11/12
        ÓPERA dispara start_full_analysis_pipeline()
        │
        ▼
  [E10] Extensão faz polling de /api/v1/sessions/{code}/status
        idle → uploading → processing → ocr → analyzing → review_ready
        │
        ▼
  [E11] USUÁRIO revisa e corrige os campos na aba do ÓPERA (fluxo inalterado)
        │
        ▼
  [E12] Usuário clica [ Produzir peça e enviar ao SEI ] no popup
        │
        ▼
  [E13] ÓPERA valida campos obrigatórios e gera o artefato a partir dos
        dados CORRIGIDOS na UI  ................................ ERR-13/14
        │
        ▼
  [E14] Bridge obtém o artefato e registra no NUP como RASCUNHO ... ERR-15..18
        SeiClient.registrar_documento(..., assinar=False)
        │
        ▼
  [E15] Confirmação: id_documento SEI + link; popup exibe "rascunho criado"
```

### 2.2 Estados da operação

Uma operação = um NUP + uma sessão ÓPERA pareada.

| Estado | Entrada | Saída normal | Saída de erro |
|---|---|---|---|
| `IDLE` | — | `NUP_VALIDATED` | — |
| `NUP_VALIDATED` | NUP válido informado | `TREE_LOADED` | ERR-01..04 |
| `TREE_LOADED` | árvore parseada, peças listadas | `TRANSFERRING` | ERR-05 |
| `TRANSFERRING` | usuário confirmou a seleção | `TRANSFERRED` | ERR-06..09 |
| `TRANSFERRED` | peças aceitas pelo ÓPERA | `PROCESSING` | — |
| `PROCESSING` | pipeline disparado | `ANALYZING` | ERR-10, ERR-11 |
| `ANALYZING` | extração concluída, LLM em curso | `REVIEW_READY` | ERR-12 |
| `REVIEW_READY` | resposta LLM disponível na UI | `PRODUCING` | — |
| `PRODUCING` | usuário acionou a produção | `UPLOADING_SEI` | ERR-13, ERR-14 |
| `UPLOADING_SEI` | artefato pronto | `DONE` | ERR-15..18 |
| `DONE` | rascunho criado no SEI | — | — |
| `FAILED` | erro terminal | retomada a partir do último checkpoint | — |

**Checkpoints:** `TREE_LOADED`, `TRANSFERRED` e `REVIEW_READY`. Uma falha posterior nunca deve exigir refazer as etapas caras já concluídas — novo download das peças, novo processamento de PDF/OCR ou nova chamada à LLM. Ver §10.

### 2.3 Eventos e resultados esperados

| Evento | Origem | Resultado observável |
|---|---|---|
| `nup:submitted` | popup | árvore carregada e peças listadas em ≤ 30 s (§11) |
| `docs:selected` | popup | seleção congelada; botão "Enviar ao ÓPERA" habilitado |
| `docs:transferred` | bridge | contador `N/N` no popup; arquivos visíveis na lista da view ÓPERA |
| `analysis:started` | ÓPERA | overlay de carregamento na UI do ÓPERA; status textual atualizado |
| `analysis:finished` | ÓPERA | campos estruturados preenchidos; popup em `REVIEW_READY` |
| `piece:requested` | popup | ÓPERA valida campos obrigatórios |
| `piece:registered` | bridge | `id_documento` retornado; nó rascunho visível na árvore |

### 2.4 Classes de falha

NUP/permissão · sessão SEI · parsing da árvore · download de peça · transporte para o ÓPERA · processamento/OCR · análise LLM · produção do artefato · escrita no SEI · infraestrutura (rede, proxy, timeout). Catálogo completo em §10.

---

## 3. Requisitos funcionais

Notação `RF-nn`; prioridade **M** (must), **S** (should), **C** (could).

### 3.1 Identificação do NUP

- **RF-01 (M)** — Campo de entrada de NUP no popup, com máscara `NNNNN.NNNNNN/AAAA-DD`.
- **RF-02 (M)** — Havendo aba do SEI com processo aberto, pré-preencher NUP e `link_processo` detectados, exibindo-os para confirmação. `[REQUISITO]`
- **RF-03 (S)** — Histórico local dos últimos 5 NUPs operados na sessão do navegador (apenas NUP e timestamp; jamais conteúdo de documento).

### 3.2 Validação do NUP

- **RF-04 (M)** — Validação sintática local (formato + dígito verificador, padrão CNJ/PEN) antes de qualquer requisição ao SEI.
- **RF-05 (M)** — Validação semântica: o NUP informado deve conferir com o NUP do processo efetivamente localizado no SEI. Divergência ⇒ abortar (ERR-01). Nunca operar sobre processo diferente do informado.

### 3.3 Obtenção das peças

- **RF-06 (M)** — A obtenção parte **exclusivamente** da árvore de documentos, fonte única de verdade para URLs. `[PROVADO]` (`NOTES_Sei.md` §0.1 e §2; `client.py:615`)
- **RF-07 (M)** — **Proibida** navegação especulativa para "descobrir" links de download. Ausência de `link_download` em anexo binário é erro de parsing irrecuperável (`ParsingError`), não motivo para tentar a página de visualização. `[PROVADO]` (`client.py:682`; `NOTES_Sei.md` §4-Fluxo B)
- **RF-08 (M)** — Pastas paginadas devem ser expandidas antes da listagem final (POST em `frmArvore` com `hdnPastaAtual`/`hdnProtocolos`). `[PROVADO]` (`client.py:474`)
- **RF-09 (M)** — Documentos com `status == 'rascunho'` (href `about:blank`) são listados como indisponíveis e nunca enviados ao analyzer. `[PROVADO]` (`parser.py`, campo `status`; `client.py:682`)
- **RF-10 (S)** — Processos apensados (nós `PROCESSO` com `index_arvore > 0`) exibidos como grupo separado, desmarcados por padrão.

### 3.4 Seleção dos documentos enviados ao analyzer

- **RF-11 (M)** — Classificação de cada nó em três categorias, a partir do campo `icone` do parser:
  - **Elegível, pré-selecionado:** `pdf`, `interno`, `email`, `imagem` — com link resolvido.
  - **Elegível, não pré-selecionado:** `zip`, `anexo`, `html`, `video` — fora do contrato atual do analyzer.
  - **Inelegível:** `cancelado`, `pasta`, `processo`, ou `status == 'rascunho'`.
- **RF-12 (M)** — O analyzer aceita **apenas PDF**. `[PROVADO]` (`ManagedFilePicker(..., allowed_extensions=["pdf"])`, `nc_analyze_view.py:497`; validação de extensão em `components.py:922`). Consequência: documentos internos entram como PDF gerado pelo SEI; anexos não-PDF ficam fora da seleção automática e são sinalizados.
- **RF-13 (M)** — A ordem enviada ao ÓPERA deve ser a ordem hierárquica achatada da árvore (mesma lógica de `acessar_processo`), pois a ordem é semanticamente relevante na agregação de texto. `[PROVADO]` (`client.py:474`, função `achatar`; `KEY_SESSION_PDF_FILES_ORDERED` com `original_index`)
- **RF-14 (S)** — Permitir reordenar/desmarcar peças no popup antes do envio.
- **RF-15 (M)** — Exibir por peça: título na árvore, tipo, tamanho estimado quando conhecido, e motivo de exclusão quando inelegível.

### 3.5 Transferência dos arquivos

- **RF-16 (M)** — As peças trafegam `SEI → bridge (memória) → endpoint do ÓPERA`, **sem gravação em disco no computador do usuário**. `[REQUISITO]`
- **RF-17 (M)** — No servidor, os arquivos são persistidos em `UPLOAD_TEMP_DIR`, exatamente como no upload manual: esse é o contrato de entrada do pipeline, que opera sobre caminhos. `[PROVADO]` (`_pdf_processing_thread_func(pdf_paths: List[str], ...)`, `nc_analyze_view.py:2451`; `PDFDocumentAnalyzer.analyze_pdf_documents(pdf_paths_ordered)`, `pdf_processor.py:953`)
- **RF-18 (M)** — Nomes sanitizados e prefixados com identificador de operação, evitando colisão no diretório de uploads compartilhado entre sessões concorrentes.
- **RF-19 (M)** — Ao final da operação (sucesso ou abandono), os temporários da operação são removidos por rotina de limpeza com TTL. `[REQUISITO]`
- **RF-20 (S)** — Progresso por peça (`k de N`), cancelável.

### 3.6 Acionamento automático do processamento

- **RF-21 (M)** — Após a transferência, a extensão dispara o pipeline completo sem interação na aba do ÓPERA.
- **RF-22 (M)** — O disparo reutiliza o mesmo caminho de código do clique em "Solicitar Análise" com arquivos não processados: `InternalAnalysisController.start_full_analysis_pipeline(pdf_paths, batch_name)`. `[PROVADO]` (`nc_analyze_view.py:3030`, chamado por `_handle_analyze_click` → `_initiate_analysis_step("process_and_analyze")`)
- **RF-23 (M)** — O disparo respeita a guarda de reentrância existente (`_is_action_in_progress`): havendo ação em curso, o endpoint responde `409 Conflict` e a extensão não reenvia. `[PROVADO]` (`nc_analyze_view.py:669`)
- **RF-24 (M)** — As configurações de análise (provedor, modelo, temperatura, OCR automático, limiar de similaridade, estrutura de prompt) permanecem sob controle exclusivo da UI do ÓPERA; a extensão não as define nem as sobrescreve. `[PROVADO]` que vivem em `KEY_SESSION_NC_ANALYZE_SETTINGS` (`_get_current_analysis_settings`, `nc_analyze_view.py:2338`).

### 3.7 Acompanhamento de progresso e status

- **RF-25 (M)** — O endpoint de status expõe: estado da máquina (§2.2), texto de status corrente, contagem de arquivos e, quando disponíveis, metadados de processamento e da resposta LLM.
- **RF-26 (M)** — Polling adaptativo pelo popup: 1 s em etapas ativas, 5 s em espera de revisão, encerrado ao fechar o popup. `[RECOMENDAÇÃO]`
- **RF-27 (S)** — Notificação do Chrome ao concluir a análise, para o caso de o usuário estar em outra aba.
- **RF-28 (M)** — O status deve refletir a etapa de OCR automático, que é a de maior duração e possui diálogo de cancelamento próprio na UI. `[PROVADO]` (`_run_auto_ocr_step`, `nc_analyze_view.py:2392`)

### 3.8 Tratamento de erros

- **RF-29 (M)** — Todo erro apresenta: causa em linguagem natural, se é retentável, e qual etapa será refeita no retry.
- **RF-30 (M)** — Erro de sessão SEI (`AuthError`) nunca dispara login automático pela extensão; o usuário é instruído a reautenticar na aba do SEI. `[REQUISITO]`
- **RF-31 (M)** — Erros do lado ÓPERA propagam a semântica das exceções existentes: `ContextLengthExceededError` e `LLMTruncatedResponseError`. `[PROVADO]` (`ai_orchestrator.py:788,796`; tratamento em `nc_analyze_view.py:~2960`)

### 3.9 Sincronização com a aba do ÓPERA

- **RF-32 (M)** — A extensão opera contra **uma** sessão Flet específica (pareamento), pois todo o estado da análise vive em `page.session` e no cache por usuário; não há estado global compartilhado entre sessões. `[PROVADO]` (uso pervasivo de `page.session` e `get_user_cache(page)`)
- **RF-33 (M)** — Pareamento explícito, revogável e com expiração por inatividade.
- **RF-34 (M)** — Se a sessão Flet pareada não existir mais (recarga da página, expiração), o endpoint responde `410 Gone` e a extensão solicita novo pareamento.
- **RF-35 (M)** — A extensão **não** automatiza a UI do ÓPERA por DOM. A interface Flet é renderizada em canvas (CanvasKit), sem DOM semântico manipulável. `[PROVADO]` (`flet_web/fastapi/app.py`: `web_renderer: WebRenderer = WebRenderer.CANVAS_KIT`; `run_server.py` não sobrescreve o parâmetro — a linha `web_renderer=ft.WebRenderer.HTML` está comentada)

### 3.10 Detecção de sessão inválida no SEI

- **RF-36 (M)** — A detecção reutiliza o mecanismo existente: presença de `frmLogin` no HTML ⇒ limpeza de cookies + `AuthError`. `[PROVADO]` (`client.py:152`, `_request`)
- **RF-37 (M)** — Antes de operação longa (lote de downloads, escrita), a bridge faz checagem barata de sessão e falha cedo. `[REQUISITO]`
- **RF-38 (M)** — Expiração no meio de um lote preserva as peças já obtidas e permite retomada sem perder progresso (ERR-04).

### 3.11 Produção do artefato final

- **RF-39 (M)** — O artefato é produzido a partir de `LLMStructuredResultDisplay.get_current_form_data(validate_for_export=True)` — dados **corrigidos pelo usuário**, com a mesma validação de obrigatórios da exportação manual. `[PROVADO]` (`nc_analyze_view.py:2184` e `_trigger_feedback_and_export`, `:3243`)
- **RF-40 (M)** — Havendo campos obrigatórios pendentes, a produção é recusada e a extensão lista os campos, remetendo o usuário à aba do ÓPERA.
- **RF-41 (M)** — O DOCX é gerado pelo `DocxExporter` existente (simples ou por template). `[PROVADO]` (`doc_generator.py:102` `export_simple_docx`, `:199` `export_from_template_docx`)
- **RF-42 (M)** — A escolha entre "DOCX simples" e "DOCX por template X" é oferecida na extensão, alimentada por `DocxExporter.get_available_templates()`. `[PROVADO]` (`doc_generator.py:179`)
- **RF-43 (M)** — O fluxo de coleta de feedback (`FeedbackWorkflowManager`), hoje acoplado à exportação manual, não pode ser silenciosamente suprimido. Decisão pendente em §15 (D-06).

### 3.12 Upload da peça ao NUP

- **RF-44 (M)** — A peça é registrada no processo de origem como documento **rascunho, não assinado**.
- **RF-45 (M)** — A extensão nunca invoca assinatura; `_assinar_documento` não é exposto pela API da bridge. `[REQUISITO]`
- **RF-46 (M)** — Tipo de documento SEI e nome na árvore configuráveis (padrão em §6.4).
- **RF-47 (M)** — Nível de acesso explícito na UI da extensão (público/restrito + hipótese legal), com padrão conservador definido pela unidade. `[PROVADO]` que ambos são suportados por `registrar_documento(nivel_acesso=..., hipotese_legal=...)` (`client.py:1374`).

### 3.13 Confirmação de criação como rascunho

- **RF-48 (M)** — Após a criação, confirmar por **releitura da árvore** que existe nó com o `id_sei` retornado e que ele não está assinado. `[REQUISITO]`
- **RF-49 (M)** — Exibir o número SEI do documento e um link que o abre na aba do SEI.

### 3.14 Prevenção de duplicidades

- **RF-50 (M)** — Antes de criar, verificar documento com o mesmo `nome_na_arvore` no processo; existindo, retornar o existente sem criar novo. `[PROVADO]` — idempotência já implementada (`client.py:1374`, bloco "CHECK DE DUPLICIDADE")
- **RF-51 (M)** — O `nome_na_arvore` deve conter discriminador estável da operação (ex.: `Análise ÓPERA — <NUP> — <AAAAMMDD>`), para que a idempotência seja significativa.
- **RF-52 (M)** — Documento já existente ⇒ informar claramente e oferecer: abrir o existente, ou criar nova versão com discriminador incrementado. Nunca duplicar silenciosamente.
- **RF-53 (M)** — Reenvio das mesmas peças não duplica entradas em `KEY_SESSION_PDF_FILES_ORDERED`; a deduplicação por `name` + `path_or_message` já existe. `[PROVADO]` (`nc_analyze_view.py:562`)

### 3.15 Cancelamento e repetição

- **RF-54 (M)** — Canceláveis: busca no SEI, download de peças, transferência ao ÓPERA.
- **RF-55 (M)** — Não cancelável pela extensão: análise LLM em curso. Não existe mecanismo de cancelamento em `_llm_analysis_thread_func`; o cancelamento do OCR permanece exclusivo da UI do ÓPERA. `[PROVADO]`
- **RF-56 (M)** — Reanalisar as mesmas peças já transferidas reutiliza o caminho `analyze_only` (`start_llm_analysis_only`), sem novo download nem novo processamento de PDF. `[PROVADO]` (`nc_analyze_view.py:3015`; pré-condição `_files_processed` em `:713`)
- **RF-57 (M)** — Toda operação pode ser abandonada, liberando os temporários do servidor.

---

## 4. Integração com o ÓPERA

### 4.1 Conclusão determinante: a UI do ÓPERA não é automatizável

`ft.app()`/`flet.fastapi.app()` usam `WebRenderer.CANVAS_KIT` por padrão, e `run_server.py` não sobrescreve esse parâmetro (a linha com `web_renderer=ft.WebRenderer.HTML` está comentada). `[PROVADO]`

Consequências, todas verificáveis:

- A página do ÓPERA renderiza em um único `<canvas>`. Não há botões, campos ou textos no DOM para um content script ler ou clicar.
- O `ft.FilePicker` em modo web abre o diálogo **nativo do sistema operacional**, fora do alcance de qualquer API de extensão.
- O upload web é feito por PUT em uma URL assinada por HMAC (`/upload?f=&e=&s=`), gerada server-side por `page.get_upload_url(...)` e verificada com `FLET_SECRET_KEY`. `[PROVADO]` (`components.py:911`; `flet_web/fastapi/flet_upload.py:52-68`). Uma extensão **não pode** forjar essa URL.

Portanto, qualquer automação baseada em UI do ÓPERA é inviável — não frágil, inviável. A integração precisa ser programática. Isso reforça, e não contraria, a diretriz do projeto de preferir APIs a acoplamento de interface.

### 4.2 O que precisa ser acionado (mapeamento funcional)

| Ação do fluxo | Ponto de entrada real no código | Assinatura |
|---|---|---|
| Injetar arquivos | `page.session[KEY_SESSION_PDF_FILES_ORDERED]` + `KEY_SESSION_SHARED_FILES_ORDERED` | lista de `{"name", "path_or_message", "original_index"}` `[PROVADO]` `nc_analyze_view.py:562` |
| Registrar nome do lote | `page.session[KEY_SESSION_CURRENT_BATCH_NAME]` | `str` `[PROVADO]` `:684` |
| Processar apenas | `InternalAnalysisController.start_pdf_processing_only(pdf_paths, batch_name)` | `:3003` `[PROVADO]` |
| Processar + analisar | `InternalAnalysisController.start_full_analysis_pipeline(pdf_paths, batch_name, is_reanalysis=False)` | `:3030` `[PROVADO]` |
| Reanalisar | `InternalAnalysisController.start_llm_analysis_only(aggregated_text, batch_name, is_reanalysis=True)` | `:3015` `[PROVADO]` |
| Ler dados corrigidos | `LLMStructuredResultDisplay.get_current_form_data(validate_for_export=True)` | retorna `formatted_initial_analysis` **ou** lista de erros `[PROVADO]` `:2184` |
| Gerar DOCX simples | `DocxExporter.export_simple_docx(data, output_path) -> bool` | `doc_generator.py:102` `[PROVADO]` |
| Gerar DOCX por template | `DocxExporter.export_from_template_docx(data, template_path, output_path) -> (bool, List[str])` | `doc_generator.py:199` `[PROVADO]` |
| Listar templates | `DocxExporter.get_available_templates() -> List[Tuple[str, str]]` | `doc_generator.py:179` `[PROVADO]` |
| Atualizar UI após injeção | `AnalyzePDFViewContent._update_gui_from_state()` | `:1385` `[PROVADO]` |
| Guarda de reentrância | `AnalyzePDFViewContent._is_action_in_progress` | `:150`, `:669` `[PROVADO]` |

### 4.3 Dados que precisam ser lidos da sessão (não da página)

| Dado | Chave | Onde vive |
|---|---|---|
| Arquivos do lote | `KEY_SESSION_PDF_FILES_ORDERED` | `page.session` `[PROVADO]` |
| Texto agregado | `KEY_SESSION_PDF_AGGREGATED_TEXT_INFO` | cache por usuário (`get_user_cache`) `[PROVADO]` |
| Resposta original da LLM | `KEY_SESSION_PDF_LLM_RESPONSE` | cache por usuário `[PROVADO]` |
| Resposta corrigida na GUI | `KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL` | cache por usuário `[PROVADO]` |
| Metadados de processamento | `KEY_SESSION_PROCESSING_METADATA` | `page.session` `[PROVADO]` |
| Metadados da LLM | `KEY_SESSION_LLM_METADATA` | `page.session` `[PROVADO]` |
| Identidade do usuário | `page.session["auth_user_id"]`, `auth_id_token` | `page.session`, espelhados em `client_storage` `[PROVADO]` (`app.py:295`) |

> **Atenção de projeto:** `KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL` é o *snapshot* do que está no formulário. A fonte autoritativa dos dados corrigidos no instante da produção é `get_current_form_data()`, que lê os controles. A produção acionada pela extensão **deve** chamar esse método, não ler o cache. `[REQUISITO]`

### 4.4 Como a extensão detecta que uma etapa terminou

Não por observação da tela. Os sinais confiáveis, todos server-side:

| Etapa | Sinal de conclusão | Base |
|---|---|---|
| Injeção dos arquivos | resposta 201 do endpoint de documentos, com a lista efetiva | `[REQUISITO]` |
| Extração/processamento | `AnalyzePDFViewContent._files_processed == True` e `KEY_SESSION_PDF_AGGREGATED_TEXT_INFO` presente | `[PROVADO]` (`:713`) |
| OCR | diálogo de OCR ativo ⇒ estado `ocr` (a bridge não interage com ele) | `[PROVADO]` (`:2392`) |
| Análise LLM | `_is_action_in_progress == False` **e** `KEY_SESSION_PDF_LLM_RESPONSE` presente | `[PROVADO]` (`:2725` `finally`, `:150`) |
| Falha na LLM | `_is_action_in_progress == False` **e** resposta ausente + status textual de erro | `[PROVADO]` |
| Produção do artefato | retorno do endpoint de produção com hash e tamanho do arquivo | `[REQUISITO]` |

A combinação `_is_action_in_progress == False` + presença/ausência de `KEY_SESSION_PDF_LLM_RESPONSE` é o discriminador definitivo entre "concluída com sucesso" e "concluída com erro", porque o bloco `finally` de `_llm_analysis_thread_func` libera a guarda incondicionalmente. `[PROVADO]`

### 4.5 Novos endpoints — proposta (não existem hoje)

**Não existe hoje qualquer API REST no ÓPERA.** `run_server.py` chama `ft.app(target=server_main, view=WEB_BROWSER, port, host, assets_dir, upload_dir)` — só isso. `[PROVADO]` O README lista "API REST (FastAPI)" como item **não concluído** do roadmap (`README.md:217`). `[PROVADO]`

**Viabilidade de adicionar endpoints sem reescrever o app:** `flet 0.28.3` expõe `flet.fastapi` (reexportando `flet_web.fastapi`), com `app(session_handler, assets_dir=..., upload_dir=..., secret_key=..., ...)` que monta todos os handlers Flet dentro de uma instância FastAPI própria. `[PROVADO]` (`flet_web/fastapi/app.py:20-56`) Isto permite servir o ÓPERA e a API no **mesmo host e porta**, eliminando CORS entre eles e preservando o deploy atual (uma imagem, uma porta).

Endpoints propostos — todos `[REQUISITO]`, nenhum existe:

| Método | Rota | Função |
|---|---|---|
| `POST` | `/api/v1/pairing` | Troca um código de pareamento por um token de operação de curta duração. |
| `GET` | `/api/v1/sessions/{code}/status` | Estado da máquina, texto de status, contagens, metadados. |
| `POST` | `/api/v1/sessions/{code}/documents` | Recebe as peças (multipart), grava em `UPLOAD_TEMP_DIR`, injeta na sessão. `201` com a lista efetiva. |
| `POST` | `/api/v1/sessions/{code}/analysis:start` | Dispara `start_full_analysis_pipeline`. `409` se `_is_action_in_progress`. |
| `POST` | `/api/v1/sessions/{code}/analysis:reanalyze` | Dispara `start_llm_analysis_only`. |
| `GET` | `/api/v1/sessions/{code}/result` | Dados corrigidos (`get_current_form_data`) ou lista de campos obrigatórios pendentes (`422`). |
| `GET` | `/api/v1/sessions/{code}/templates` | Lista de templates DOCX do usuário. |
| `POST` | `/api/v1/sessions/{code}/piece` | Produz o artefato (DOCX e/ou HTML) e devolve os bytes ou uma URL de uso único. |
| `DELETE` | `/api/v1/sessions/{code}` | Encerra a operação e limpa temporários. |

**Como o endpoint alcança a sessão Flet do usuário.** Um handler HTTP não tem referência a uma `Page`. Mecanismo proposto: um **registro em processo** (`dict` protegido por `Lock`) no qual `AnalyzePDFViewContent.did_mount()` registra `{codigo_pareamento: (page_ref, callbacks)}` e `will_unmount()` desregistra. O endpoint resolve o código, invoca os callbacks e retorna. `[REQUISITO]` / `[RECOMENDAÇÃO]`

Isso é seguro porque a view **já** é manipulada a partir de threads externas ao loop Flet: todo o pipeline roda em `threading.Thread` e atualiza a UI via `page.run_thread` e os helpers `safe_page_update`/`safe_control_update`, que são serializados por lock global. `[PROVADO]` (`:3003`, `:2369`, e o comentário explícito em `:2421` sobre thread-safety desses helpers) Um handler FastAPI é apenas mais uma thread externa e deve usar exatamente os mesmos helpers.

**Restrição de deploy:** o registro em processo funciona porque há **um único worker** servindo o app (`ft.app` single-process, um container). Se algum dia houver múltiplos workers/réplicas, o registro precisa migrar para armazenamento compartilhado. `[A VALIDAR]` na evolução da infra.

### 4.6 Partes que deveriam virar API (e por quê)

| Hoje acoplado à UI | Deveria ser | Justificativa |
|---|---|---|
| `_trigger_feedback_and_export` mistura validação, coleta de feedback e exportação | Separar em `validar()`, `coletar_feedback()`, `exportar()` | A extensão precisa de validação sem abrir diálogo modal. `[RECOMENDAÇÃO]` |
| `InternalExportManager.start_export` levanta `ValueError` em desktop e no modo web dispara `page.launch_url` | Extrair `gerar_artefato(data, tipo, template) -> caminho` sem efeito de UI | Hoje a geração está amarrada ao download do navegador. `[PROVADO]` (`:3074`, `:3138`) |
| Pipeline recebe caminhos de arquivo | Aceitar também objetos file-like | Permitiria transferência realmente em memória. **Fora do escopo deste repo** — pertence à refatoração apartada. `[RECOMENDAÇÃO]` |

---

## 5. Integração com o SEI

Toda esta seção deriva de `SOURCE/clients/sei/client.py`, `parser.py` e `docs/NOTES_Sei.md` do projeto ePol/RPA. Nada aqui é inventado; o que não existe está marcado como `[REQUISITO]` ou `[HIPÓTESE]`.

### 5.1 Autenticação e sessão

**O que existe.** `SeiClient.login()` executa o fluxo completo SIP → SEI → seleção de unidade, buscando a senha no `keyring` (`get_pwd`, `client.py:122`). O decorador `@require_session` dispara login automático quando `url_mesa_atual` é `None` ou não há `PHPSESSID` nos cookies (`client.py:42`). `[PROVADO]`

**O que a extensão deve fazer — e não fazer.** A extensão **não** faz login. O requisito do produto é reutilizar a sessão que o usuário já mantém no navegador. Mecanismo:

- **RF-S01 (M)** — A extensão lê os cookies do domínio do SEI via `chrome.cookies.getAll({domain})` e os entrega à bridge, que os injeta em `SeiClient.session.cookies`. `[REQUISITO]`
- **RF-S02 (M)** — Ao injetar cookies, a bridge deve também definir `client.url_mesa_atual` com uma URL válida da sessão corrente, **caso contrário `@require_session` fará login automático com a senha do keyring** — comportamento indesejado e potencialmente bloqueante. `[PROVADO]` que essa é a condição do decorador; a injeção é `[REQUISITO]`.
- **RF-S03 (M)** — Se a bridge não conseguir estabelecer sessão válida por cookies, ela falha com ERR-04 e instrui o usuário. Nunca cai para login por senha. `[REQUISITO]`
- **RF-S04 (M)** — Cookies mantidos apenas em memória do processo da bridge, com TTL curto; nunca persistidos, nunca logados. `[REQUISITO]`
- **RF-S05 (M)** — Todos os cabeçalhos de simulação de navegador já definidos no `SeiClient` (`User-Agent`, `Referer`) permanecem; o rate limit `SEI_RATE_LIMIT_SECONDS` (0,8 s) é preservado. `[PROVADO]` (`client.py:107`, `:152`; `infra/config.py:62`)

**Detecção de expiração.** Já implementada: qualquer resposta HTML contendo `id="frmLogin"` ou `name="frmLogin"` limpa cookies, zera `url_mesa_atual` e levanta `AuthError`. `[PROVADO]` (`client.py:152`)

### 5.2 Localização do NUP — ponto de atenção

**Fato relevante: o `SeiClient` não possui busca por NUP.** Os métodos existentes navegam pela *Mesa de Processos* filtrada por marcador (`listar_processos`, `_navegar_para_marcador`), e todo método de processo recebe um `link_processo` já obtido do DOM (`acessar_processo(nup, link_processo)`, `obter_arvore_documentos(nup, link_processo)`, `registrar_documento(nup, link_processo, ...)`). `[PROVADO]`

Além disso, `acessar_processo` remove `infra_hash` do link recebido para forçar o SEI a emitir um novo na sessão corrente — ou seja, o link precisa ser **orgânico**, extraído da interface, jamais construído. `[PROVADO]` (`client.py:474`)

Duas estratégias, em ordem de preferência:

**Estratégia A (recomendada) — capturar o link da própria aba do SEI.** `[RECOMENDAÇÃO]`
O usuário abre o processo no SEI (etapa que já faz hoje). Um content script na origem do SEI captura a URL do frameset do processo (`acao=procedimento_trabalhar`, com `id_procedimento`) e o NUP exibido, e os entrega à extensão. A bridge recebe esse `link_processo` orgânico e segue exatamente o caminho já validado do `SeiClient`.

Vantagens: zero navegação especulativa; zero código novo de busca; aderente à regra da árvore como fonte de verdade; o "NUP digitado" passa a ser apenas confirmação/validação cruzada (RF-05).
Custo: exige que o processo esteja aberto na aba do SEI. Na prática, é o estado natural do usuário.

**Estratégia B (complementar) — implementar busca por NUP no `SeiClient`.** `[REQUISITO]` + `[A VALIDAR]`
Adicionar um método `localizar_processo_por_nup(nup) -> link_processo` que submeta o formulário de pesquisa do SEI e extraia o link do resultado. **Nenhum detalhe desse formulário (ação, campos, hash) foi verificado nesta análise** — a rota, o nome dos campos e o comportamento com múltiplos resultados são `[HIPÓTESE]` e precisam ser levantados com DevTools contra o SEI real antes de qualquer implementação. Enquanto isso não for feito, a Estratégia A é a única com base comprovada.

> Regra de projeto: mesmo com a Estratégia B implementada, o link obtido da pesquisa deve ser tratado como orgânico e usado sem remontagem manual.

### 5.3 Navegação até a árvore

Fluxo já implementado e reutilizável sem alterações — `obter_arvore_documentos(nup, link_processo)` (`client.py:615`): `[PROVADO]`

1. Remove `infra_hash` antigo do `link_processo`.
2. `GET link_processo` → HTML do frameset.
3. Extrai `src` do frame `ifrArvore` (fallback `ifrArvoreHtml`) via `SeiMesaParser.get_frame_url`.
4. Define `Referer` = `link_processo` (o SEI recusa a navegação sem isso).
5. `GET url_arvore` → HTML da árvore. **A navegação termina aqui.**

`acessar_processo` (`client.py:474`) faz o mesmo e adiciona: expansão de pastas paginadas, reconstrução hierárquica (`achatar`) e leitura da capa/metadados. Para o caso de uso da extensão, a expansão e a ordenação hierárquica são necessárias; a leitura da capa é opcional (uma requisição a menos se dispensada, e ela levanta `BusinessError` quando o link da capa não é achado — comportamento indesejável aqui). `[PROVADO]`

- **RF-S06 (M)** — A bridge deve usar um caminho de leitura que inclua expansão de pastas e ordenação hierárquica, **sem** a obrigatoriedade da capa. Isso significa: ou um novo método no `SeiClient` que combine `obter_arvore_documentos` + expansão + `achatar`, ou parametrizar `acessar_processo` para tornar a capa opcional. `[REQUISITO]` — a segunda opção é uma mudança mínima e reversível no `SeiClient`.

### 5.4 Identificação das peças e obtenção das URLs

`SeiArvoreParser.extract_documentos()` faz parsing por blocos do JavaScript da árvore (`re.split` em `Nos[x] = new infraArvoreNo`) e devolve, por nó: `[PROVADO]` (`parser.py:306`)

| Campo | Conteúdo |
|---|---|
| `index_arvore` | índice `Nos[X]`, usado para ordenação dentro do nível |
| `id_sei`, `id_pai` | identificadores para reconstrução hierárquica |
| `tipo` | título exibido na árvore |
| `href` | `arvore_visualizar` (**não** serve para GET direto de conteúdo) |
| `icone` | `pdf`, `interno`, `email`, `zip`, `video`, `imagem`, `html`, `anexo`, `cancelado`, `pasta`, `processo` |
| `status` | `rascunho` (href `about:blank`) ou `disponivel` |
| `carregado` | `False` em pastas de paginação ainda não expandidas |
| `link_gerar_pdf` | URL de `procedimento_gerar_pdf` (documentos internos) |
| `link_download` | URL de `documento_download_anexo` (anexos binários) |
| `link_visualizar_documento` | URL de `documento_visualizar`, atribuída via `Nos[X].src` |

Regras de uso, todas já documentadas e implementadas:

- **RF-S07 (M)** — `href` **não** deve ser usado para obter conteúdo: acessado por GET direto devolve o frameset inteiro da árvore. Para conteúdo HTML de documento interno, usar `link_visualizar_documento` com `Referer` = URL da árvore. `[PROVADO]` (comentário extenso em `parser.py:~410` e `client.py:656`)
- **RF-S08 (M)** — Anexo binário sem `link_download` ⇒ `ParsingError`, sem fallback de navegação. `[PROVADO]`

### 5.5 Download dos documentos

`SeiClient.baixar_documento(nup, doc_metadata, pasta_destino)` orquestra três estratégias por tipo de ícone: `[PROVADO]` (`client.py:682`)

| Ícone | Estratégia | Método |
|---|---|---|
| `interno`, `email` | Gerar PDF: GET em `link_gerar_pdf`; se vier o formulário `frmProcedimentoPdf`, extrair link JS ou fazer POST (com `hdnFlagGerar=1`, `rdoTipo=A`, `hdnDocumentosApenas`) e então baixar o PDF gerado. Valida assinatura `%PDF`. | `_preparar_doc_interno` (`:768`) — **retorna bytes em memória** |
| `pdf`, `imagem`, `html` | GET direto em `link_download`; se ausente, tenta localizar o binário na página de visualização. | `_preparar_doc_nativo` (`:846`) — retorna URL **ou** bytes |
| `zip`, `video`, `anexo` | GET direto em `link_download`; ausência ⇒ `ParsingError`. | inline em `baixar_documento` — retorna URL |
| `processo` | ignorado (retorna `''`) | — |
| `cancelado`, `pasta` | não tratados ⇒ `NotImplementedError` | — |

**Limitação estrutural para o requisito "em memória".** `baixar_documento` termina sempre em `_salvar_arquivo_em_disco` (`client.py:911`), que grava em `pasta_destino` e aplica validações importantes que **só existem lá**: detecção da página-wrapper "Clique aqui para baixar" (com recuperação via `_recuperar_link_intermediario`), captura da extensão real pelo `Content-Disposition`, e verificação de tamanho. `[PROVADO]`

- **RF-S09 (M)** — A bridge precisa de um caminho de download que devolva `(nome, bytes)` sem persistir em disco, **preservando todas as validações de `_salvar_arquivo_em_disco`**. Isso é um `[REQUISITO]`: refatorar `_salvar_arquivo_em_disco` extraindo a validação para uma função pura sobre bytes (`validar_conteudo_baixado(nome, conteudo) -> (nome_corrigido, conteudo)`), reutilizada tanto pelo caminho em disco quanto pelo novo caminho em memória. Reimplementar essas validações do zero na bridge seria duplicação exatamente do tipo que este projeto quer evitar.
- **RF-S10 (M)** — O cache de disco de `baixar_documento` (`resolver_nome_fisico_existente`, pular download se o arquivo já existe) não se aplica ao caminho em memória; a deduplicação passa a ser por `id_sei` dentro da operação. `[PROVADO]` que o cache existe; a substituição é `[REQUISITO]`.
- **RF-S11 (S)** — Limite de tamanho por peça e por operação, configurável, com recusa explícita acima do limite (proteção de memória — ver §11).

### 5.6 Documentos nativos versus anexos

| Situação | Tratamento |
|---|---|
| Documento interno do SEI (despacho, informação) | PDF gerado pelo SEI via `link_gerar_pdf`. Aceito pelo analyzer. |
| PDF externo anexado | GET direto; aceito pelo analyzer. |
| Imagem, HTML | Baixáveis, mas **não** aceitos pelo analyzer (só PDF). Sinalizar. |
| ZIP, vídeo, planilha (`anexo`) | Baixáveis, não aceitos pelo analyzer. Sinalizar; conteúdo de ZIP não é expandido (fora de escopo). |
| Rascunho (`about:blank`) | Não baixável — já retorna `''` com aviso. `[PROVADO]` |
| Documento cancelado | Não baixável; excluir da seleção. |

### 5.7 Tratamento de PDFs no lado ÓPERA

Uma vez entregues, os PDFs seguem o pipeline existente sem qualquer alteração: extração (`fitz` ou `pdfplumber` conforme configuração), verificação de inteligibilidade, OCR automático opcional (RapidOCR), TF-IDF/similaridade, classificação de páginas por relevância e agregação com limite de tokens. `[PROVADO]` (`pdf_processor.py:747`–`:1269`; `nc_analyze_view.py:2451`)

- **RF-S12 (M)** — PDFs ininteligíveis não são rejeitados na entrada: o OCR automático da própria aplicação decide. A extensão apenas reporta o estado `ocr` e o eventual cancelamento pelo usuário.

### 5.8 Criação da peça no SEI — o que existe e o que não existe

**Existe** `registrar_documento(nup, link_processo, tipo_documento, nome_na_arvore, conteudo_html, numero=None, nivel_acesso='publico', hipotese_legal=None, assinar=True, retornar_conteudo=False)` (`client.py:1374`). `[PROVADO]` Coreografia implementada e validada em produção no projeto ePol:

1. `GET link_processo` → frameset → `GET ifrArvore`.
2. **Checagem de duplicidade** por `nome_na_arvore` na árvore; se existir, retorna o `id_sei` existente.
3. Extrai o link "Incluir Documento" de `Nos[0].acoes` (regex no JS — não existe como `<a>` estático no HTML).
4. `GET` da tela de escolha de tipo → `SeiDocumentoParser.get_tipo_documento_id` → `POST` de `frmDocumentoEscolherTipo` com `hdnIdSerie`.
5. `POST` dos metadados: `txtNomeArvore`, `rdoNivelAcesso`, `selHipoteseLegal` (se restrito), `rdoFormato='N'` (nato-digital), `rdoTextoInicial='N'`, `hdnFlagDocumentoCadastro='2'`.
6. Extrai a URL do editor (`editor_montar`) e a acessa.
7. `POST` do teor no endpoint especializado (`sei/editor/editor_processar.php`) com `Content-Type: ...; charset=iso-8859-1`; **sucesso só se a resposta começar com `"OK"`**.
8. Refresh de estado: novo `GET` no editor para sincronizar `hdnVersao` e capturar `strLinkAssinatura`.
9. `assinar=True` → assina; **`assinar=False` → o documento permanece como minuta/rascunho** e o `id_documento` é extraído de `hdnIdDocumento` ou da query string da URL do editor.

**Existe também** `registrar_documento_por_modelo(link_processo, id_modelo, placeholders, tipo_documento='Despacho', nivel_acesso='publico', assinar_documento=False, ...)` (`client.py:1582`), que usa `rdoTextoInicial='D'` + `txtProtocoloDocumentoTextoBase=id_modelo` e substitui placeholders `&lt;chave&gt;` em todas as seções do editor. `[PROVADO]`

**NÃO existe** qualquer suporte a **documento externo** / upload de arquivo binário no `SeiClient`: uma busca por `documento_externo`, `receber_arquivo`, `multipart`, `files=` e `upload` em `client.py` e `parser.py` não retorna **nenhuma** ocorrência. `[PROVADO]` (busca executada nos dois arquivos)

Isso é determinante para a estratégia da §6.

### 5.9 Manutenção de sessão e validação de sucesso

- **RF-S13 (M)** — Toda escrita segue o padrão obrigatório do `NOTES_Sei.md` §0.2: parsear o link de ação da árvore → GET da tela de confirmação → parsear `action` + hidden inputs → POST → **validar pela mudança de estado**. Nunca construir URLs de ação manualmente. `[PROVADO]`
- **RF-S14 (M)** — Validações de sucesso específicas a preservar: resposta `"OK"` do editor (passo 7); presença do documento na árvore após criação (RF-48); `divInfraMensagens` como sinal de erro de negócio. `[PROVADO]`
- **RF-S15 (M)** — Encoding ISO-8859-1 forçado em POSTs, e conversão explícita com `str()` de todo valor extraído do BeautifulSoup antes de montar payload (armadilha `NavigableString` documentada em `NOTES_Sei.md` §7.4.4). `[PROVADO]`

---

## 6. Produção e inserção da peça no SEI

### 6.1 A pergunta a resolver

O usuário quer "produzir a peça final (DOCX)" e "enviá-la ao NUP como rascunho". Existem três estratégias possíveis no SEI; a escolha **deve** derivar do que está implementado, não de preferência estética.

| Estratégia | Base no código | Custo | Resultado no SEI |
|---|---|---|---|
| **(A) Documento interno nato-digital** com teor HTML, `assinar=False` | `registrar_documento(...)` — **implementado e em produção** `[PROVADO]` | Baixo. Requer converter os dados da análise em HTML. | Documento editável no SEI, como minuta/rascunho, revisável e assinável pelo usuário. |
| **(B) Documento interno a partir de modelo SEI**, `assinar_documento=False` | `registrar_documento_por_modelo(...)` — **implementado** `[PROVADO]` | Baixo, **se** existir um documento-modelo cadastrado no SEI com os placeholders. | Igual a (A), com layout padronizado mantido pela própria unidade dentro do SEI. |
| **(C) Documento externo com o DOCX anexado** | **Não existe no `SeiClient`** `[PROVADO]` | Alto: novo fluxo multipart, campos de tipo de conferência/formato, hash, validação — tudo `[HIPÓTESE]` até levantamento com DevTools. | Anexo binário; não editável no SEI; exige "conferência com o original". |

### 6.2 Recomendação derivada

**Estratégia primária: (B) quando houver documento-modelo cadastrado; (A) como padrão imediato.** `[RECOMENDAÇÃO]`

Justificativas:

1. (A) e (B) são caminhos **já exercitados em produção** no projeto ePol, incluindo o caso `assinar=False` que produz exatamente o rascunho pedido. (C) exigiria construir do zero o fluxo mais delicado do SEI, sem nenhuma base verificada — e a orientação do projeto é não inventar comportamento.
2. Um documento interno como rascunho é revisável **dentro do SEI**, que é o que a persona "chefe de unidade" precisa. Um DOCX anexado obriga a baixar, editar fora e reanexar.
3. (B) desloca a manutenção do layout da peça para o próprio SEI (o modelo é editado por quem é dono do processo), reduzindo o acoplamento entre o ÓPERA e o formato da peça.

**O DOCX continua existindo**, como artefato entregue ao usuário: a extensão oferece o download do DOCX (gerado pelo `DocxExporter` já existente, simples ou por template) **e** cria o rascunho no SEI. São saídas complementares, não excludentes.

**Estratégia (C) permanece como evolução opcional**, condicionada a levantamento prévio do formulário de documento externo do SEI 4.0 em ambiente real. Se e quando for implementada, ela pertence ao `SeiClient` (novo método), não à extensão.

### 6.3 Consequência técnica: geração de HTML

O `DocxExporter` produz apenas `.docx`. Para a estratégia (A) é necessário um teor HTML.

- **RF-P01 (M)** — Criar um gerador de HTML no ÓPERA que consuma o mesmo `formatted_initial_analysis` e reutilize o mapeamento de nomes de campos e a formatação de listas já implementados (`_get_field_display_name`, `_format_list_item`, `doc_generator.py:33,83`). `[REQUISITO]` — é uma adição pequena e cirúrgica ao `doc_generator.py`, não uma refatoração.
- **RF-P02 (M)** — O HTML gerado deve ser conservador: parágrafos, negrito, listas e tabelas simples. O editor do SEI (CKEditor) sanitiza agressivamente; CSS externo e estruturas complexas se perdem. `[HIPÓTESE]` quanto aos limites exatos — `[A VALIDAR]` com um documento de teste.
- **RF-P03 (M)** — Para a estratégia (B), o mapeamento é direto: os placeholders do template DOCX do ÓPERA já são `<campo>` (`<descricao_geral>`, `<resumo_fato>`, `<tipificacao_penal>`, ...) `[PROVADO]` (`nc_analyze_view.py:3138`) e `registrar_documento_por_modelo` substitui exatamente `&lt;chave&gt;`/`<chave>` `[PROVADO]`. O mesmo dicionário de dados serve aos dois. Isso torna (B) uma implementação de baixíssimo atrito, **desde que** o documento-modelo seja cadastrado no SEI com os mesmos nomes de placeholder. `[A VALIDAR]`
- **RF-P04 (M)** — Placeholders sem valor devem ser substituídos por texto neutro explícito, nunca deixados no documento.

### 6.4 Parâmetros da criação

| Parâmetro | Valor proposto | Observação |
|---|---|---|
| `tipo_documento` | configurável; padrão a definir com a unidade (ex.: "Informação" ou "Despacho") | Deve existir na lista do SEI; `get_tipo_documento_id` falha com `BusinessError` se não existir. `[PROVADO]` |
| `nome_na_arvore` | `Análise ÓPERA — <NUP> — <AAAAMMDD>` | Discriminador de idempotência (RF-51). |
| `numero` | `None` | Tipos sem numeração rejeitam valor; o código já trata `None`. `[PROVADO]` |
| `nivel_acesso` | escolha explícita do usuário; padrão conservador da unidade | `restrito` exige `hipotese_legal`. `[PROVADO]` |
| `assinar` | **`False`, imutável** | Nunca exposto como opção. |
| `rdoFormato` | `'N'` (nato-digital) | Já fixado no método. `[PROVADO]` |

### 6.5 Fluxo completo de produção e inserção

```
[popup] "Produzir peça e enviar ao SEI"
   │
   ├─► POST /api/v1/sessions/{code}/result?validate=true
   │       ÓPERA: get_current_form_data(validate_for_export=True)
   │       ├─ lista de erros → 422 + campos pendentes → popup exibe e PARA  (ERR-13)
   │       └─ formatted_initial_analysis válido → 200
   │
   ├─► POST /api/v1/sessions/{code}/piece  {formato: docx|html|ambos, template?}
   │       ÓPERA: DocxExporter.export_* (docx) e/ou gerador HTML (RF-P01)
   │       → devolve bytes e/ou teor HTML + hash                            (ERR-14)
   │
   ├─► bridge: SeiClient.registrar_documento(
   │             nup, link_processo, tipo_documento, nome_na_arvore,
   │             conteudo_html, nivel_acesso, hipotese_legal, assinar=False)
   │       ├─ documento já existe → devolve id existente                    (ERR-17)
   │       ├─ editor não responde "OK" → BusinessError                      (ERR-15)
   │       └─ sucesso → id_documento                                        
   │
   ├─► bridge: releitura da árvore, confirma nó com id_sei e não assinado    (RF-48)
   │
   └─► popup: "Rascunho criado — documento SEI <n>" + link + download do DOCX
```

- **RF-P05 (M)** — O envio ao SEI só ocorre após confirmação explícita do usuário no popup; nunca automaticamente ao término da análise.
- **RF-P06 (M)** — O DOCX gerado no servidor deve ser servido por URL de uso único com expiração curta, e **não** depositado permanentemente em `assets/temp_docx_exports/`. Hoje a exportação web grava nesse diretório e dispara `page.launch_url` sem limpeza posterior. `[PROVADO]` (`nc_analyze_view.py:3074`) — a rotina de limpeza é `[REQUISITO]`.

---

## 7. Arquitetura da solução

### 7.1 Análise de viabilidade das alternativas de integração

Cada alternativa foi avaliada contra o cenário real: SEI legado com frames, cookies e `infra_hash` dinâmico; ÓPERA em canvas; rede corporativa com proxy; usuários sem privilégio administrativo.

#### (a) Extensão acessa o SEI diretamente (fetch same-origin)

**Como seria.** Content script na origem do SEI faz `fetch(..., {credentials: 'include'})`. Não há CORS: mesma origem. Cookies vão automaticamente. Reimplementa-se em JavaScript o parsing da árvore e a coreografia de escrita.

**Viabilidade.** Tecnicamente viável para **leitura**: o parsing por blocos de `Nos[x] = new infraArvoreNo` é regex sobre texto e pode ser portado. Para **escrita**, é onde mora o risco: a criação de documento envolve nove passos com hashes dinâmicos, encoding ISO-8859-1 em POST, armadilhas de `<button type=submit>`, hidden mirrors do ddslick, double-encoding de placeholders no CKEditor e validação por `"OK"` — todo um corpo de correções descobertas por tentativa e erro, documentado em `NOTES_Sei.md` §5 e §7. `[PROVADO]`

**Veredito: rejeitada como arquitetura principal.** Duplicaria em JavaScript, sem testes, a parte mais frágil e mais cara de reconquistar do `SeiClient`. Viola diretamente a diretriz de reutilização. A partir de qualquer atualização do SEI, passariam a existir duas implementações a corrigir.

#### (b) Uso da sessão/credenciais já existentes no navegador

**Viabilidade: alta, e é o mecanismo adotado** — mas como *insumo*, não como arquitetura. `chrome.cookies` (com permissão de host para o domínio do SEI) permite obter o `PHPSESSID` e injetá-lo numa `requests.Session`. Isso elimina a necessidade de o usuário fornecer senha e evita o keyring.

**Riscos:** os cookies são credenciais de portador. Precisam ficar em memória, com TTL, nunca em log, nunca em `chrome.storage`, e o destino precisa ser confiável (§9).

#### (c) Backend/API central que fala com o SEI

**Como seria.** Um serviço na VM PF recebe o NUP e os cookies do usuário e opera o SEI em nome dele.

**Viabilidade: possível, com duas objeções sérias.** Primeira: exigiria trafegar cookies de sessão do SEI até o servidor. Hoje o ÓPERA é servido em **HTTP simples** nas portas 8550/80/8080 `[PROVADO]` (`docker-compose.yml`) — enviar credenciais de sessão do SEI por canal não cifrado na rede corporativa é um retrocesso de segurança inaceitável sem TLS. Segunda: concentraria num único processo a capacidade de agir no SEI como qualquer usuário, ampliando o impacto de um comprometimento.

**Veredito: viável apenas com TLS obrigatório**; mantida como alternativa documentada (§7.7), não como recomendação.

#### (d) Serviço local / bridge Python

**Como seria.** Um pequeno processo Python na máquina do usuário, embarcando o `SeiClient`, recebendo comandos da extensão e falando com o SEI e com o ÓPERA.

**Viabilidade: alta.** Reutiliza 100% do `SeiClient` e dos parsers. Os cookies do SEI nunca saem da máquina do usuário. O projeto já domina empacotamento PyInstaller e possui um auto-updater (`update_manager.py`, `updater.exe`, `VERSION_INFO_URL`) `[PROVADO]` — ou seja, distribuição e atualização de um binário local são problema já resolvido neste projeto.

**Custo:** um artefato a instalar por estação de trabalho.

#### (e) Chrome Native Messaging

**Como seria.** A extensão conversa com a bridge por stdin/stdout, com o registro do host em `HKCU\Software\Google\Chrome\NativeMessagingHosts\<nome>` (não requer privilégio administrativo).

**Viabilidade: alta, e superior a um servidor HTTP em localhost:**
- Nenhuma porta TCP aberta na estação (menos superfície, menos atrito com política de firewall/EDR corporativo).
- O manifesto do host declara `allowed_origins` com o ID da extensão: só aquela extensão consegue falar com a bridge. Um servidor em `127.0.0.1` é acessível a qualquer processo local e a qualquer página web via `fetch`, exigindo esquema próprio de token.
- Ciclo de vida do processo gerenciado pelo Chrome.

**Limitação a respeitar:** o tamanho máximo de mensagem **do host para a extensão é de 1 MB**. Isso torna proibitivo trafegar PDFs por esse canal. `[PROVADO]` pela documentação da plataforma; `[A VALIDAR]` na versão do Chrome do parque.

**Solução de projeto que dissolve a limitação:** os arquivos **nunca passam pela extensão**. A bridge baixa do SEI e envia direto ao ÓPERA; e busca o artefato no ÓPERA e envia direto ao SEI. Pelo canal de native messaging trafegam apenas mensagens de controle (NUP, link do processo, cookies, metadados das peças, estado) — todas pequenas.

#### (f) Evolução do `SeiClient` para biblioteca reutilizável

**Necessária de todo modo.** Hoje o `SeiClient` importa `SOURCE.utils.file_manager`, `SOURCE.infra.exceptions`, `SOURCE.infra.config` e `SOURCE.infra.logger` do repositório ePol `[PROVADO]`. Consumi-lo de outro projeto exige uma das três:

1. **Extrair para pacote `sei-client`** instalável (por caminho local ou índice interno), com `config` injetável em vez de importada. `[RECOMENDAÇÃO]` — melhor a médio prazo; é a única opção que evita a divergência de duas cópias.
2. Vendorizar (copiar) — cria a duplicação que se quer evitar. Rejeitada.
3. Instalar o repositório ePol como dependência de caminho — funciona, mas arrasta todo o pacote (Prefect, clientes ePol/PJe) para dentro da bridge.

**Decisão pendente (D-01, §15).** Recomenda-se (1), com escopo mínimo: `clients/sei/*` + as quatro dependências de infra, com configuração injetada.

#### (g) Limitações de CORS, permissões, cookies e isolamento

| Aspecto | Situação |
|---|---|
| CORS SEI → extensão | Irrelevante: a bridge é Python, fora do modelo de origens do navegador. |
| CORS ÓPERA → extensão | Chamadas do service worker a `/api/v1/*` exigem permissão de host da extensão e cabeçalhos CORS no endpoint. Se todo o tráfego for feito pela bridge, o problema desaparece. `[RECOMENDAÇÃO]`: a extensão fala **apenas** com a bridge; a bridge fala com SEI e ÓPERA. |
| Cookies | `chrome.cookies` exige permissão `cookies` + host permission do domínio do SEI. Cookies `HttpOnly` **são** legíveis por essa API (diferente de `document.cookie`) — necessário, já que `PHPSESSID` é `HttpOnly`. `[HIPÓTESE]` quanto ao flag exato do cookie do SEI; `[A VALIDAR]`. |
| Isolamento entre origens | Content scripts em SEI e ÓPERA rodam em mundos isolados e não compartilham estado — toda correlação passa pelo service worker. |
| MV3 service worker | É efêmero: encerrado por inatividade. **Não pode** guardar estado da operação em variáveis de módulo; usar `chrome.storage.session`. |
| CSP do SEI | Injeção de script na página do SEI é desnecessária nesta arquitetura (apenas leitura de URL/DOM básico pelo content script). |

### 7.2 Arquitetura recomendada — componentes

```
╔══════════════════════ ESTAÇÃO DE TRABALHO DO USUÁRIO ═══════════════════════╗
║                                                                             ║
║  ┌─────────────────────── Google Chrome ─────────────────────────┐          ║
║  │                                                               │          ║
║  │  ┌── Aba SEI (sei4.pf.gov.br) ──┐   ┌── Aba ÓPERA (VM PF) ──┐ │          ║
║  │  │ content script:              │   │ content script:       │ │          ║
║  │  │  • lê URL do processo        │   │  • lê código de       │ │          ║
║  │  │    (procedimento_trabalhar)  │   │    pareamento         │ │          ║
║  │  │  • lê NUP exibido            │   │    (localStorage)     │ │          ║
║  │  │  • NÃO faz fetch ao SEI      │   │  • NÃO automatiza UI  │ │          ║
║  │  └──────────────┬───────────────┘   └───────────┬───────────┘ │          ║
║  │                 │                               │             │          ║
║  │            ┌────▼───────────────────────────────▼────┐        │          ║
║  │            │  SERVICE WORKER (background, MV3)       │        │          ║
║  │            │  • máquina de estados da operação       │        │          ║
║  │            │  • chrome.cookies (domínio SEI)         │        │          ║
║  │            │  • chrome.storage.session (estado)      │        │          ║
║  │            └────┬───────────────────────▲───────────┘        │          ║
║  │                 │  native messaging     │  eventos/estado    │          ║
║  │            ┌────▼───────────────────────┴───────────┐        │          ║
║  │            │  POPUP (UI da extensão)                │        │          ║
║  │            └────────────────────────────────────────┘        │          ║
║  └───────────────────────────┬───────────────────────────────────┘          ║
║                              │ stdin/stdout (JSON, mensagens pequenas)      ║
║  ┌───────────────────────────▼──────────────────────────────────┐           ║
║  │  ÓPERA-SEI BRIDGE  (host de native messaging, Python)        │           ║
║  │  ┌────────────────────────────────────────────────────────┐  │           ║
║  │  │ SeiClient + parsers  (reutilizados, não reimplementados)│  │           ║
║  │  │ sessão por cookies injetados · memória apenas · TTL     │  │           ║
║  │  └────────────────────────────────────────────────────────┘  │           ║
║  │  buffer de peças EM MEMÓRIA · cliente HTTP do ÓPERA          │           ║
║  └────────┬──────────────────────────────────────┬──────────────┘           ║
╚═══════════│══════════════════════════════════════│══════════════════════════╝
            │ HTTPS (leitura da árvore,            │ HTTP(S) + token de operação
            │ download, criação de documento)      │ (upload das peças, disparo,
            ▼                                      ▼  status, artefato)
   ┌─────────────────────┐              ┌──────────────────────────────────┐
   │   SEI 4.0 (PF)      │              │  ÓPERA — VM PF (Docker)          │
   │   sei4.pf.gov.br    │              │  ┌────────────────────────────┐  │
   │   frames, PHP,      │              │  │ FastAPI (novo)             │  │
   │   infra_hash        │              │  │  /api/v1/*  ← bridge       │  │
   └─────────────────────┘              │  ├────────────────────────────┤  │
                                        │  │ flet.fastapi.app(main)     │  │
                                        │  │  sessão Flet do usuário    │  │
                                        │  │  registro de pareamento    │  │
                                        │  └────────────────────────────┘  │
                                        │  UPLOAD_TEMP_DIR · pipeline      │
                                        └──────────────────────────────────┘
```

### 7.3 Fluxo de dados (quem carrega o quê)

```
COOKIES DO SEI      : Chrome ──► service worker ──► bridge ──► (memória, TTL)
                      nunca vão ao servidor ÓPERA, nunca a disco

link_processo/NUP   : aba SEI ──► service worker ──► bridge

BYTES DAS PEÇAS     : SEI ──► bridge (memória) ──► ÓPERA (multipart)
                      NUNCA passam pela extensão (limite de 1 MB do canal)
                      NUNCA tocam o disco do usuário

TEOR/ARTEFATO       : ÓPERA ──► bridge ──► SEI
                      DOCX opcionalmente ──► download do usuário

ESTADO/PROGRESSO    : ÓPERA ──► bridge ──► service worker ──► popup

CÓDIGO DE PAREAMENTO: ÓPERA (UI/localStorage) ──► content script ──► service worker
```

### 7.4 Componentes da extensão (MV3)

| Componente | Responsabilidade | Não faz |
|---|---|---|
| `manifest.json` | Declaração MV3, permissões mínimas | — |
| `service_worker.js` | Máquina de estados; ponte entre popup, content scripts e bridge; leitura de cookies; persistência em `chrome.storage.session` | Não guarda bytes de documento; não guarda cookies |
| `popup/` | UI de operação (§8) | Não faz requisições ao SEI nem ao ÓPERA |
| `content_sei.js` | Lê a URL do frameset e o NUP da aba do SEI | Não faz `fetch` ao SEI; não injeta script na página |
| `content_opera.js` | Lê o código de pareamento; detecta que a aba é do ÓPERA | Não tenta ler/clicar a UI (canvas) |
| `options/` | URL base do ÓPERA, domínio do SEI, preferências (tipo de documento, nível de acesso padrão) | Não armazena segredo |

**Permissões (princípio do menor privilégio):**

```jsonc
{
  "manifest_version": 3,
  "permissions": ["cookies", "storage", "nativeMessaging", "activeTab", "notifications"],
  "host_permissions": ["https://<host-do-sei>/*", "http(s)://<host-do-opera>/*"],
  "background": { "service_worker": "service_worker.js", "type": "module" }
}
```

Notas: `tabs` completo é dispensável (`activeTab` + content scripts declarados bastam). `downloads` só é necessário se a extensão for oferecer o DOCX ao usuário — decisão D-05 (§15). `webRequest`/`declarativeNetRequest` **não** são necessários.

### 7.5 A bridge

| Aspecto | Definição |
|---|---|
| Forma | Executável PyInstaller (`opera_sei_bridge.exe`) + manifesto de native messaging em `HKCU` |
| Protocolo | Native messaging: JSON com prefixo de 4 bytes de tamanho, stdin/stdout |
| Reuso | `SeiClient` + parsers, com configuração injetada (§7.1-f) |
| Estado | Uma operação ativa por vez; peças em memória, com limite configurável |
| Rede | Respeita proxy corporativo; `NO_PROXY` para o host do ÓPERA quando aplicável |
| Log | Arquivo local rotativo, **sem** conteúdo de documento, **sem** cookies, com NUP mascarado |
| Atualização | Mesma trilha do auto-updater já existente no projeto `[RECOMENDAÇÃO]` |

**Comandos (native messaging):**

| Comando | Entrada | Saída |
|---|---|---|
| `ping` | — | versão, saúde |
| `sei.session.check` | cookies | `ok` \| `expired` |
| `sei.tree.load` | cookies, `link_processo`, `nup` | lista classificada de peças |
| `opera.pair` | `pairing_code`, base URL | `operation_token` |
| `transfer.start` | seleção de `id_sei`, token | progresso por peça (streaming de eventos) |
| `opera.analysis.start` | token | aceito \| `409` |
| `opera.status` | token | estado + metadados |
| `piece.produce_and_submit` | token, formato, template, tipo de documento, nível de acesso | `id_documento`, link, confirmação de rascunho |
| `operation.cancel` | token | — |

### 7.6 Gerenciamento de estado e armazenamento

| Dado | Onde vive | Persistência |
|---|---|---|
| Estado da operação | `chrome.storage.session` | Some ao fechar o navegador |
| Preferências | `chrome.storage.local` | Persistente; sem segredos |
| Cookies do SEI | memória da bridge | TTL curto; descartados ao fim da operação |
| Bytes das peças | memória da bridge | Descartados após POST ao ÓPERA |
| Peças no servidor | `UPLOAD_TEMP_DIR` | TTL, limpeza ao fim (RF-19) |
| Artefato produzido | `assets/temp_docx_exports/` | URL de uso único; limpeza (RF-P06) |
| Token de operação | memória da bridge + `storage.session` | Expira por inatividade |

### 7.7 Arquitetura alternativa (registrada, não recomendada agora)

**Bridge no servidor**: um container `opera-sei-bridge` no mesmo `docker-compose`, recebendo os cookies do SEI encaminhados pela extensão. Elimina a instalação por estação. **Pré-condições obrigatórias:** (i) TLS no ÓPERA; (ii) parecer de segurança sobre encaminhamento de cookies de sessão; (iii) confirmação de que a VM alcança o SEI através do proxy configurado. Enquanto essas três condições não forem satisfeitas, a bridge local é a opção defensável.

### 7.8 Segurança da arquitetura (resumo; detalhe em §9)

- A extensão nunca vê bytes de documento.
- Os cookies do SEI não deixam a máquina do usuário.
- A senha do SEI nunca é solicitada, lida ou armazenada.
- A bridge só aceita conexões da extensão declarada (`allowed_origins`).
- Nenhuma porta é aberta na estação de trabalho.
- Nenhuma escrita no SEI ocorre sem confirmação explícita do usuário no popup.
- Assinatura é impossível por construção: o comando não existe na API da bridge.
---

## 8. UX/UI da extensão

Princípio: a extensão é um **painel de operação**, não uma segunda interface de análise. Tudo que exige julgamento sobre o conteúdo acontece no ÓPERA.

### 8.1 Estados do popup

```
┌─ ÓPERA ⇄ SEI ─────────────────────────── ⚙ ─┐   ┌─ ÓPERA ⇄ SEI ──────────────── ⚙ ─┐
│                                             │   │                                  │
│  ● SEI conectado    ● ÓPERA pareado         │   │  ● SEI conectado  ● ÓPERA pareado│
│                                             │   │                                  │
│  NUP                                        │   │  NUP 08xxx.xxxxxx/2026-xx        │
│  ┌───────────────────────────────────────┐  │   │  7 peças encontradas · 5 elegíveis│
│  │ 08___.______/____-__                  │  │   │  ┌────────────────────────────┐  │
│  └───────────────────────────────────────┘  │   │  │ ☑ Ofício 123 ......... PDF │  │
│  ⤷ detectado na aba do SEI · usar           │   │  │ ☑ Relatório .......... PDF │  │
│                                             │   │  │ ☑ Despacho ....... interno │  │
│          [    Buscar NUP    ]               │   │  │ ☐ Anexos.zip .. não suportado│ │
│                                             │   │  │ ✕ Minuta ......... rascunho │  │
└─────────────────────────────────────────────┘   │  └────────────────────────────┘  │
        (1) inicial                                │      [ Enviar ao ÓPERA ]         │
                                                   └──────────────────────────────────┘
                                                            (2) peças

┌─ ÓPERA ⇄ SEI ────────────────────┐   ┌─ ÓPERA ⇄ SEI ──────────────────────┐
│  Transferindo peças... 3/5       │   │  ✓ Análise concluída               │
│  ████████████░░░░░░░░            │   │  5 peças · 34 páginas · 12 relevantes│
│                                  │   │                                    │
│  [ Cancelar ]                    │   │  Revise os dados na aba do ÓPERA.  │
├──────────────────────────────────┤   │                                    │
│  Processando conteúdo...         │   │  Peça:  ( ) DOCX simples           │
│  OCR: página 12/40               │   │         (•) Template "NC padrão"    │
│  Analisando com a LLM...         │   │  Tipo SEI: [ Informação      ▾]    │
│  (etapas exibidas em sequência)  │   │  Acesso:   [ Público         ▾]    │
└──────────────────────────────────┘   │                                    │
        (3) em andamento                │  [ Produzir peça e enviar ao SEI ] │
                                        └────────────────────────────────────┘
                                                  (4) revisão pronta

┌─ ÓPERA ⇄ SEI ───────────────────────────────┐
│  ✓ Rascunho criado no SEI                   │
│  Documento SEI 12345678                     │
│  [ Abrir no SEI ]   [ Baixar DOCX ]         │
│  ⚠ Não assinado — revise e assine no SEI.   │
│                              [ Nova análise ]│
└─────────────────────────────────────────────┘
        (5) concluído
```

### 8.2 Regras de interação

- **UX-01** — Dois indicadores permanentes no topo: sessão SEI e pareamento ÓPERA. Vermelho ⇒ ação corretiva descrita em uma linha, com link para a aba correspondente.
- **UX-02** — Botão primário único por estado. Nunca dois caminhos concorrentes na mesma tela.
- **UX-03** — Nenhuma tela exige digitação além do NUP (e este é pré-preenchido quando detectável).
- **UX-04** — Peças inelegíveis aparecem com o motivo, em cinza, sem checkbox. Nada de exclusão silenciosa.
- **UX-05** — Durante o processamento, o popup pode ser fechado sem interromper a operação; ao reabrir, mostra o estado atual (estado em `chrome.storage.session`).
- **UX-06** — O botão de produção só é habilitado em `REVIEW_READY`. Campos obrigatórios pendentes ⇒ lista dos campos e instrução para corrigir no ÓPERA.
- **UX-07** — A tela final sempre lembra explicitamente que o documento **não está assinado**.
- **UX-08** — Erros ocupam o corpo do popup com: o que aconteceu, o que fazer, e o botão de retry quando aplicável (§10).
- **UX-09** — Acessibilidade: navegável por teclado, contraste adequado, textos em português.

### 8.3 Pareamento com a sessão do ÓPERA

Como a UI do ÓPERA é canvas, o código de pareamento precisa de um canal fora da tela:

- **Primário `[RECOMENDAÇÃO]` / `[A VALIDAR]`** — o ÓPERA grava o código em `page.client_storage`; o content script o lê do `localStorage` da origem do ÓPERA. O Flet persiste `client_storage` no `localStorage` do navegador `[PROVADO]` que `client_storage` é usado hoje para tokens de autenticação (`app.py:220-296`); **o prefixo exato das chaves gravadas pelo Flutter é `[HIPÓTESE]` e precisa ser verificado no navegador.**
- **Fallback `[REQUISITO]`** — botão "Copiar código de pareamento" na view do ÓPERA (usando o clipboard da página) e campo de colagem no popup. Simples, sem dependência de detalhes internos do Flet, e é o caminho a implementar primeiro na Fase 1.

---

## 9. Segurança e privacidade

### 9.1 Credenciais

- **SEG-01** — A extensão e a bridge **nunca** solicitam, leem ou armazenam a senha do SEI. O login permanece manual, na aba do SEI.
- **SEG-02** — O caminho de login por keyring do `SeiClient` deve ser **desabilitado** na configuração da bridge: sessão exclusivamente por cookies injetados; falha de sessão ⇒ erro, nunca login automático (RF-S02/S03).
- **SEG-03** — Credenciais do ÓPERA (token Firebase) não são manipuladas pela extensão; a autorização da API se dá pelo token de operação obtido no pareamento.

### 9.2 Cookies e sessões

- **SEG-04** — Cookies do SEI: lidos sob demanda, transportados apenas pelo canal de native messaging, mantidos em memória da bridge com TTL, descartados ao fim da operação. Nunca em `chrome.storage`, nunca em disco, nunca em log.
- **SEG-05** — Escopo mínimo de leitura: apenas os cookies do domínio do SEI, apenas quando há operação ativa.
- **SEG-06** — Token de operação do ÓPERA: curta duração, escopo de uma sessão pareada, revogável, renovável.
- **SEG-07** — O pareamento expira por inatividade e é invalidado quando a sessão Flet termina.

### 9.3 Dados processuais e documentos

- **SEG-08** — Nenhum documento é gravado no disco do usuário em nenhum momento do fluxo.
- **SEG-09** — No servidor, os arquivos vivem em `UPLOAD_TEMP_DIR` apenas enquanto durar a operação, com limpeza por TTL (RF-19). Nota: hoje o diretório de uploads é compartilhado e recebe `chmod 777` `[PROVADO]` (`run_server.py`) — a nomeação por operação (RF-18) e a limpeza tornam-se ainda mais importantes por isso.
- **SEG-10** — O artefato produzido é servido por URL de uso único com expiração, e removido em seguida (RF-P06).
- **SEG-11** — A extensão não envia conteúdo de documento a nenhum destino além do endpoint do ÓPERA configurado — na prática, ela nunca vê esse conteúdo.

### 9.4 Memória

- **SEG-12** — Buffers de peças liberados imediatamente após o POST ao ÓPERA.
- **SEG-13** — Limite configurável de memória por operação; excedido ⇒ recusa explícita, sem cair para disco silenciosamente.

### 9.5 Comunicação

- **SEG-14** — Comunicação extensão ⇄ bridge restrita ao ID da extensão via `allowed_origins`.
- **SEG-15** — Nenhuma porta TCP aberta na estação de trabalho.
- **SEG-16** — Comunicação bridge ⇄ ÓPERA autenticada por token de operação. **TLS é requisito para qualquer implantação em rede não confiável** e pré-condição da variante servidor (§7.7).
- **SEG-17** — Verificação TLS do SEI: o `SeiClient` hoje usa `verify=False` e suprime avisos de certificado `[PROVADO]` (`client.py:152`, `urllib3.disable_warnings`). Aceitável em rede corporativa com certificado interno, mas deve ser **configurável** e documentado como decisão consciente, não como padrão silencioso.

### 9.6 Exposição de tokens

- **SEG-18** — Nenhum token, cookie ou hash em URL, query string ou log.
- **SEG-19** — `infra_hash` e demais tokens do SEI ficam confinados ao processo da bridge.
- **SEG-20** — O código de pareamento é de uso único e curta duração; ele não autoriza nada por si — o token derivado sim.

### 9.7 Logs

- **SEG-21** — Logs da bridge e do ÓPERA registram: identificador de operação, etapa, resultado, duração, contagem de peças. **Nunca**: conteúdo de documento, cookies, tokens, teor da análise.
- **SEG-22** — NUP mascarado nos logs (ex.: `08xxx.xxxxxx/2026-xx`) fora do nível DEBUG.
- **SEG-23** — O `SeiClient` possui o decorador `dump_html_on_error`, que grava o HTML da última resposta em `logs/debug/` `[PROVADO]` (`client.py:53`). **Na bridge esse comportamento deve ser desabilitado por padrão**: esse HTML pode conter conteúdo de documento e dados sigilosos do processo. Habilitável apenas em modo de diagnóstico explícito, com retenção curta.
- **SEG-24** — O ÓPERA envia logs para o Firebase Storage `[PROVADO]` (`cloud_logger_handler.py`). Os novos endpoints não devem introduzir dados processuais nesse canal.

### 9.8 Menor privilégio

- **SEG-25** — Permissões da extensão limitadas ao listado em §7.4; nenhuma `<all_urls>`, nenhuma `webRequest`.
- **SEG-26** — A API da bridge expõe **apenas** os comandos de §7.5. Métodos do `SeiClient` como `_assinar_documento`, `concluir_processo`, `incluir_marcador`, `retirar_marcador` e `editar_anotacao` **não são alcançáveis** por construção.
- **SEG-27** — Escritas no SEI exigem confirmação explícita do usuário na sessão corrente. Nenhuma autorização é reaproveitada entre operações.

---

## 10. Tratamento de erros

Colunas: **Detecção** (como o sistema percebe) · **Comportamento** · **Mensagem** · **Retry** · **Retomada** (a partir de qual checkpoint, sem repetir etapa cara).

| Cód. | Erro | Detecção | Comportamento | Mensagem ao usuário | Retry | Retomada |
|---|---|---|---|---|---|---|
| **ERR-01** | NUP inexistente ou inválido | Falha de dígito verificador (local) ou divergência com o processo aberto | Aborta antes de qualquer requisição | "NUP inválido. Confira o número informado." | Sim, imediato | Nada a retomar |
| **ERR-02** | NUP não localizado no SEI | Nenhum processo aberto na aba do SEI e busca indisponível/sem resultado | Aborta; orienta abrir o processo no SEI | "Abra o processo no SEI e clique em 'Usar o processo aberto'." | Sim | Nada a retomar |
| **ERR-03** | NUP inacessível (sem permissão na unidade) | Resposta do SEI sem árvore, ou `divInfraMensagens` de permissão | Aborta; não tenta trocar de unidade | "Seu usuário não tem acesso a este processo na unidade atual." | Não automático | Nada a retomar |
| **ERR-04** | Sessão SEI expirada | `frmLogin` na resposta ⇒ `AuthError` `[PROVADO]` | Congela a operação; preserva peças já baixadas | "Sua sessão do SEI expirou. Faça login na aba do SEI e clique em Continuar." | Sim, após relogin | Retoma do ponto exato: peças já baixadas não são rebaixadas |
| **ERR-05** | Erro de parsing da árvore | `extract_documentos` devolve lista vazia, ou frame `ifrArvore` ausente ⇒ `ParsingError` | Aborta a leitura; oferece diagnóstico | "Não foi possível ler a árvore de documentos deste processo." | Sim (1x) | Nada a retomar |
| **ERR-06** | Documento sem URL de download | Anexo sem `link_download` ⇒ `ParsingError` `[PROVADO]` | Marca **só aquela peça** como falha; segue as demais | "A peça X não pôde ser obtida (link ausente). As demais seguem." | Sim, por peça | Sim: só a peça falha é retentada |
| **ERR-07** | Documento incompatível | Ícone fora do conjunto aceito, ou `NotImplementedError` | Exclui da seleção com motivo visível | "A peça X (tipo Y) não é suportada pela análise." | Não | Não aplicável |
| **ERR-08** | PDF ilegível / necessita OCR | Páginas marcadas como não inteligíveis no processamento | Segue o fluxo: o OCR automático da aplicação trata `[PROVADO]` | "Algumas páginas exigem OCR — isso pode levar alguns minutos." | Não aplicável | Não aplicável |
| **ERR-09** | Falha de transferência ao ÓPERA | Erro HTTP no POST de documentos, ou resposta parcial | Retry com backoff por peça (3 tentativas); falha persistente ⇒ aborta a transferência | "Falha ao enviar as peças ao ÓPERA (k de N enviadas)." | Sim, automático | Sim: reenvia apenas as peças pendentes |
| **ERR-10** | Falha no processamento do ÓPERA | Status `failed` com etapa `processing` | Aborta o pipeline; peças permanecem na sessão | "Erro ao processar o conteúdo dos arquivos." | Sim | Sim: reprocessa sem rebaixar do SEI |
| **ERR-11** | OCR cancelado pelo usuário | Cancelamento no diálogo do ÓPERA `[PROVADO]` | Pipeline segue com o que foi extraído | "OCR cancelado. A análise seguirá com o texto disponível." | Não | Não aplicável |
| **ERR-12** | Análise interrompida / erro de LLM | `_is_action_in_progress == False` sem `KEY_SESSION_PDF_LLM_RESPONSE` `[PROVADO]`; subcasos `ContextLengthExceededError` e `LLMTruncatedResponseError` | Estado `FAILED` com a causa específica; peças e texto agregado preservados | Contexto excedido: "O conteúdo excedeu o limite do modelo. Ajuste filtros ou modelo nas Configurações LLM." Demais: "Erro na consulta à LLM." | Sim, via `analyze_only` | **Sim, e é o caso mais importante**: reanálise não repete download nem extração/OCR (RF-56) |
| **ERR-13** | Campos obrigatórios pendentes | `get_current_form_data(validate_for_export=True)` devolve lista de erros `[PROVADO]` | Recusa a produção; lista os campos | "Preencha no ÓPERA: <lista>." | Sim, após correção | Sim: permanece em `REVIEW_READY` |
| **ERR-14** | Erro na produção do artefato | `export_simple_docx` devolve `False`, ou exceção no gerador HTML | Aborta a produção; nada é enviado ao SEI | "Falha ao gerar a peça." | Sim | Sim: dados na UI intactos |
| **ERR-15** | Erro no upload/criação no SEI | Editor não responde `"OK"`, `divInfraMensagens`, `BusinessError`/`ParsingError` `[PROVADO]` | Aborta a escrita; **nunca** repete o POST cegamente | "O SEI recusou a criação do documento: <detalhe>." | Sim, **após** verificar a árvore | Sim: artefato já produzido é reaproveitado |
| **ERR-16** | Tipo de documento inexistente no SEI | `get_tipo_documento_id` devolve `None` ⇒ `BusinessError` `[PROVADO]` | Aborta; oferece a lista de tipos disponíveis | "O tipo '<X>' não existe na lista do SEI." | Sim, com outro tipo | Sim |
| **ERR-17** | Documento já existente | Checagem de duplicidade por `nome_na_arvore` `[PROVADO]` | **Não cria novo**; devolve o existente | "Já existe um documento com este nome no processo." + [Abrir] / [Criar nova versão] | Somente por escolha explícita | Sim |
| **ERR-18** | Rascunho não confirmado na árvore | Releitura da árvore não encontra o `id_sei` (RF-48) | Estado `FAILED` com aviso forte de verificação manual | "O documento pode ter sido criado, mas não foi possível confirmar. **Verifique no SEI antes de repetir.**" | **Não automático** | Verificação manual obrigatória |
| **ERR-19** | Perda de conexão | `ConnectionError` ⇒ `InfraError` `[PROVADO]` | Pausa a operação; preserva o estado | "Sem conexão com <SEI/ÓPERA>." | Sim, automático (3x, backoff) | Sim: retoma do último checkpoint |
| **ERR-20** | Timeout | Estouro do limite da etapa (§11) | Marca a etapa como falha; não deixa a UI travada | "A operação demorou mais que o esperado." | Sim | Sim |
| **ERR-21** | Sessão ÓPERA perdida | Endpoint responde `410 Gone` (RF-34) | Solicita novo pareamento; preserva o NUP e a seleção | "A sessão do ÓPERA foi encerrada. Recarregue a aba e pareie novamente." | Sim, após pareamento | Parcial: a análise em curso se perde com a sessão Flet |
| **ERR-22** | Operação concorrente no ÓPERA | `409 Conflict` (RF-23) | Não reenvia; aguarda e reconsulta o status | "Há um processamento em andamento no ÓPERA." | Sim, automático | Sim |
| **ERR-23** | Bridge indisponível | Falha do native messaging | Popup em estado degradado, com instrução de instalação/reinício | "O componente local não respondeu." | Sim | Sim: estado preservado em `storage.session` |
| **ERR-24** | Peça excede limite de memória | Tamanho acima do configurado (RF-S11) | Recusa aquela peça; segue as demais | "A peça X é muito grande para o transporte em memória." | Não | Sim: demais peças seguem |

**Princípio transversal:** as três operações caras são (i) download das peças, (ii) extração + OCR, (iii) chamada à LLM. Nenhum erro pode obrigar a refazer uma delas se seu resultado ainda é válido. Os checkpoints de §2.2 existem exatamente para isso.

---

## 11. Requisitos não funcionais

### 11.1 Segurança
- **NFR-01** — Conforme §9, integralmente. Menor privilégio verificável por revisão do `manifest.json`.
- **NFR-02** — Nenhuma dependência JavaScript de terceiros em runtime na extensão (sem CDN, sem bundler que injete código remoto). MV3 proíbe código remoto; a extensão deve ser auditável por leitura.
- **NFR-03** — Toda escrita no SEI precedida de confirmação explícita do usuário.

### 11.2 Desempenho (metas iniciais, `[A VALIDAR]` em rede real)

| Etapa | Meta |
|---|---|
| Carregar árvore e listar peças | ≤ 30 s para processo com até 50 nós |
| Download por peça | ≤ 20 s para peça de até 20 MB |
| Transferência ao ÓPERA | ≥ 5 MB/s na LAN |
| Overhead da extensão | ≤ 10% do tempo total da operação |
| Latência do polling de status | ≤ 1 s |

Nota: `SEI_RATE_LIMIT_SECONDS = 0,8` impõe piso de ~0,8 s por requisição ao SEI `[PROVADO]`; a leitura da árvore custa 2–3 requisições e cada peça custa 1–3. O `NOTES_Sei.md` §8.4 registra latências de 15–20 s por GET via VPN no ambiente PF `[PROVADO]` — as metas acima pressupõem acesso pela LAN, não por VPN.

### 11.3 Confiabilidade
- **NFR-04** — Idempotência de ponta a ponta: repetir a operação com o mesmo NUP e o mesmo `nome_na_arvore` não cria documento duplicado.
- **NFR-05** — Nenhuma falha da extensão pode deixar a sessão do ÓPERA em estado inconsistente; a guarda `_is_action_in_progress` deve ser liberada em qualquer caminho de erro (comportamento já garantido pelo `finally` existente `[PROVADO]`).
- **NFR-06** — Falhas parciais de download não invalidam a operação inteira.

### 11.4 Observabilidade
- **NFR-07** — Identificador de operação propagado por todos os componentes (extensão → bridge → ÓPERA) e presente em todas as linhas de log.
- **NFR-08** — Log estruturado de cada transição de estado, com duração.
- **NFR-09** — O ÓPERA já injeta contexto de usuário/sessão nos logs (`context_wrap`, `cloud_logger_handler`) `[PROVADO]`; os novos endpoints devem usar o mesmo mecanismo.
- **NFR-10** — Tela de diagnóstico na extensão: versão, saúde da bridge, estado das sessões, últimos erros.

### 11.5 Compatibilidade
- **NFR-11** — Chrome/Edge (Chromium) em versão suportada corporativamente; MV3.
- **NFR-12** — Windows 10/11 para a bridge (parque atual).
- **NFR-13** — Compatível com proxy corporativo (`HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`), à semelhança do que já é configurado no container `[PROVADO]`.
- **NFR-14** — Nenhuma alteração no modo desktop do ÓPERA; a integração é exclusiva do modo servidor.

### 11.6 Manutenibilidade
- **NFR-15** — Zero duplicação da lógica do `SeiClient` na extensão ou na bridge; a bridge é uma casca fina de transporte.
- **NFR-16** — Toda a lógica de parsing do SEI permanece no `SeiClient`/parsers; correções beneficiam ePol e ÓPERA simultaneamente.
- **NFR-17** — Alterações no repositório do ÓPERA restritas a: novo módulo de API, gerador de HTML no `doc_generator.py`, registro de pareamento na view, e adaptação do bootstrap do servidor. Nada de refatoração ampla (`CLAUDE.md` §9).
- **NFR-18** — Contrato de API versionado (`/api/v1/`); mudanças incompatíveis exigem nova versão.

### 11.7 Tolerância a alterações de interface
- **NFR-19** — Zero dependência do DOM do ÓPERA (impossível por construção — canvas).
- **NFR-20** — Dependência mínima do DOM do SEI: apenas a leitura da URL do processo na aba aberta. Todo o resto é parsing server-side já resiliente (parsing por blocos, tolerante a variações de sintaxe `[PROVADO]`).
- **NFR-21** — Falhas de parsing devem produzir erro nomeado e acionável (`ParsingError` com a peça/etapa), nunca falha silenciosa.
- **NFR-22** — Suíte de testes com HTML real salvo (fixtures) para o parser da árvore e para a criação de documento, permitindo detectar quebras após atualização do SEI. `[RECOMENDAÇÃO]`

### 11.8 Memória e arquivos temporários
- **NFR-23** — Uso de memória da bridge proporcional à maior peça, não ao total do lote (transferência peça a peça, buffer liberado após cada envio).
- **NFR-24** — Zero arquivos temporários na estação de trabalho.
- **NFR-25** — No servidor, arquivos temporários são inevitáveis (o pipeline opera sobre caminhos `[PROVADO]`), mas devem ter nome previsível por operação e TTL. Eliminar essa gravação exigiria alterar o `pdf_processor` — trabalho da refatoração apartada, fora deste escopo.

---

## 12. Estratégia de implementação

Cada fase é entregável e reversível. Nenhuma fase quebra o fluxo manual existente.

### Fase 0 — Levantamento e habilitação (pré-requisito)

**Entregáveis**
- Extração do `SeiClient` para pacote reutilizável, com configuração injetada (D-01).
- Refatoração mínima de `_salvar_arquivo_em_disco` extraindo a validação para função pura sobre bytes (RF-S09).
- Caminho de leitura de árvore sem obrigatoriedade de capa (RF-S06).
- Levantamento em ambiente real: flags dos cookies do SEI; prefixo de chaves do `client_storage`; limite de mensagem do native messaging na versão do Chrome do parque.

**Critérios de aceite**
- Um script de teste importa o pacote fora do repositório ePol, injeta cookies obtidos manualmente do navegador e lista a árvore de um NUP real sem executar login.
- O mesmo script baixa uma peça **em memória** e valida que os bytes são idênticos aos do caminho em disco atual.
- Os fluxos existentes do ePol continuam passando (nenhuma regressão).

### Fase 1 — Prova de conceito da comunicação com o ÓPERA

**Entregáveis**
- `run_server.py` migrado para `flet.fastapi.app(...)` dentro de uma instância FastAPI própria, preservando `assets_dir`, `upload_dir`, `secret_key` e a porta atual.
- Registro de pareamento na view (`did_mount`/`will_unmount`) e botão "Copiar código de pareamento".
- Endpoints `POST /api/v1/pairing`, `GET /status`, `POST /documents`, `POST /analysis:start`.
- Extensão mínima: popup com campo de código de pareamento, botão de teste e exibição de status.

**Critérios de aceite**
- O ÓPERA continua funcionando exatamente como hoje pela URL atual (regressão zero: login, upload manual, análise, exportação).
- Um `curl` autenticado injeta 2 PDFs numa sessão pareada e eles aparecem na lista de arquivos da view.
- `POST /analysis:start` dispara o pipeline completo, e `GET /status` percorre `processing → analyzing → review_ready`.
- Segunda chamada concorrente devolve `409`.
- Sessão encerrada devolve `410`.

### Fase 2 — Integração com o SEI (somente leitura)

**Entregáveis**
- Bridge com native messaging, comandos `ping`, `sei.session.check`, `sei.tree.load`.
- Content script do SEI (captura de URL do processo e NUP).
- Leitura de cookies e injeção de sessão.
- Popup: campo de NUP, botão "Buscar NUP", listagem classificada das peças.

**Critérios de aceite**
- Para 5 processos reais de perfis distintos (com pasta paginada, com apensado, com anexo ZIP, com rascunho, com documento cancelado), a lista de peças e a ordem coincidem com a árvore exibida no navegador.
- Sessão expirada é detectada e reportada como ERR-04, **sem** disparar login por senha.
- Nenhum log contém cookie, token ou HTML de documento.

### Fase 3 — Transferência automática das peças

**Entregáveis**
- Download em memória peça a peça com progresso e cancelamento.
- `POST /documents` com nomeação por operação e deduplicação.
- Limpeza de temporários por TTL no servidor.

**Critérios de aceite**
- 5 peças (incluindo ao menos um documento interno que exige "Gerar PDF") chegam íntegras: hash idêntico ao do download manual pelo navegador.
- A ordem em `KEY_SESSION_PDF_FILES_ORDERED` corresponde à ordem da árvore.
- Nenhum arquivo é criado no disco do usuário (verificado por monitoramento de FS).
- Cancelar no meio interrompe em ≤ 2 s e limpa o que foi enviado.

### Fase 4 — Acionamento do analyzer e acompanhamento

**Entregáveis**
- Disparo automático após a transferência; polling adaptativo; estados `processing`/`ocr`/`analyzing`/`review_ready`.
- Tratamento de ERR-10 a ERR-12 com retomada.

**Critérios de aceite**
- Fluxo NUP → análise concluída sem nenhum clique na aba do ÓPERA.
- Com OCR automático ligado e PDF digitalizado, o popup reporta o estado `ocr`; cancelar o OCR na UI não trava a extensão.
- Forçando erro de contexto excedido, o popup exibe a mensagem específica e permite reanálise **sem** novo download nem nova extração.

### Fase 5 — Produção da peça

**Entregáveis**
- Endpoints `GET /result` (com validação), `GET /templates`, `POST /piece`.
- Gerador de HTML no `doc_generator.py` (RF-P01).
- Popup: escolha de formato/template e produção; download opcional do DOCX.

**Critérios de aceite**
- Com campo obrigatório vazio, `GET /result?validate=true` devolve `422` com a lista exata dos campos, e o popup a exibe.
- Correções feitas na UI aparecem no artefato produzido (verificado por diferença ponto a ponto).
- O DOCX gerado pela extensão é byte-a-byte equivalente ao gerado pelo botão "Exportar" com os mesmos dados e template.

### Fase 6 — Inserção automática no SEI

**Entregáveis**
- `piece.produce_and_submit` na bridge, chamando `registrar_documento(..., assinar=False)` (ou por modelo).
- Confirmação por releitura da árvore; tratamento de duplicidade.
- Tela final com número do documento, link e aviso de não assinatura.

**Critérios de aceite**
- Documento criado em processo real aparece na árvore como minuta **não assinada**, com o teor correspondente aos dados corrigidos.
- Repetir a operação **não** cria segundo documento: devolve o existente com aviso.
- Nenhum caminho de código consegue assinar (verificado por revisão + teste negativo).
- Falha simulada após a criação resulta em ERR-18 com instrução de verificação manual, e **não** em nova tentativa automática.

### Fase 7 — Endurecimento, segurança e erros

**Entregáveis**
- Matriz de erros §10 implementada, com retomada por checkpoint.
- Limites de memória e tamanho; timeouts por etapa.
- Revisão de logs (SEG-21..24), incluindo desabilitar `dump_html_on_error` por padrão.
- Fixtures de HTML real e testes de parser.
- Documentação de instalação e `NOTES_extensao_sei.md` no repositório.

**Critérios de aceite**
- Cada linha da matriz de erros tem um teste (real ou simulado) que produz a mensagem e o comportamento especificados.
- Revisão de segurança sem achado alto ou crítico.
- Teste de fumaça ponta a ponta em 10 NUPs reais, com ≥ 90% de conclusão sem intervenção manual.

---

## 13. Critérios de aceite do fluxo completo

Numerados para rastreio em teste.

**CA-01** — Com aba do SEI autenticada e processo aberto, e aba do ÓPERA pareada, informar o NUP e clicar em "Buscar NUP" lista as peças do processo em ≤ 30 s, com classificação correta (elegível / não suportada / indisponível).

**CA-02** — A ordem das peças listadas corresponde exatamente à ordem hierárquica da árvore no SEI, incluindo conteúdo de pastas paginadas expandidas.

**CA-03** — Clicar em "Enviar ao ÓPERA" transfere as peças selecionadas; ao final, a lista de arquivos na view do ÓPERA contém exatamente as mesmas peças, na mesma ordem, com os mesmos nomes.

**CA-04** — Nenhum arquivo é criado no sistema de arquivos da estação em todo o fluxo (verificado por monitoramento).

**CA-05** — A análise é disparada automaticamente após a transferência, sem interação na aba do ÓPERA, e o popup reflete as etapas `processing` → (`ocr`) → `analyzing` → `review_ready`.

**CA-06** — Concluída a análise, os campos estruturados estão preenchidos na UI do ÓPERA e permanecem plenamente editáveis pelo usuário; o comportamento da view é indistinguível do fluxo manual.

**CA-07** — Com campo obrigatório vazio, a produção é recusada e o popup lista os campos pendentes por nome.

**CA-08** — Após a correção, "Produzir peça e enviar ao SEI" gera o artefato a partir dos **dados corrigidos** — verificado alterando um campo e conferindo a alteração no documento resultante.

**CA-09** — O documento é criado no NUP de origem, aparece na árvore do SEI e está **não assinado** (rascunho/minuta).

**CA-10** — O popup exibe o número SEI do documento e um link que o abre corretamente na aba do SEI.

**CA-11** — Repetir todo o fluxo para o mesmo NUP não cria documento duplicado: o existente é reportado, com opções explícitas.

**CA-12** — Expirar a sessão do SEI no meio do fluxo produz ERR-04; após relogin, a operação retoma sem rebaixar as peças já obtidas.

**CA-13** — Recarregar a aba do ÓPERA produz `410` e solicitação de novo pareamento, sem travar a extensão.

**CA-14** — Nenhum log (extensão, bridge, ÓPERA) contém cookies, tokens, conteúdo de documento ou o teor da análise.

**CA-15** — Nenhum comando exposto pela bridge é capaz de assinar documento, concluir processo, alterar marcador ou editar anotação.

**CA-16** — Desinstalada a extensão, o fluxo manual do ÓPERA permanece integralmente funcional.

**CA-17** — Um erro de LLM (contexto excedido) permite reanálise sem repetir download nem extração/OCR.

**CA-18** — O DOCX produzido pela extensão é equivalente ao produzido pelo botão "Exportar" com os mesmos dados e template.

---

## 14. Dependências e riscos

### 14.1 Dependências externas

| Dependência | Natureza | Risco |
|---|---|---|
| SEI 4.0 (PF) | Sistema legado, sem API pública | Alto: mudança de layout/JS quebra o parser |
| `SeiClient`/parsers (ePol) | Código de outro repositório | Médio: exige governança da extração para pacote (D-01) |
| Firebase (Auth/Firestore) | Autenticação e prompts do ÓPERA | Baixo: já em produção |
| Provedor de LLM | Análise | Médio: indisponibilidade bloqueia o fluxo (já é risco atual) |
| `ml_engine` | Embeddings, com fallback | Baixo `[PROVADO]` que há fallback |
| Chrome/Chromium corporativo | Plataforma da extensão | Médio: política pode restringir instalação |

### 14.2 Dependências do ambiente corporativo

- Autorização para publicar/instalar extensão (Web Store privada, carga por política de grupo, ou modo desenvolvedor).
- Autorização para instalar a bridge nas estações (executável assinado; convivência com antivírus/EDR).
- Escrita em `HKCU` para o manifesto de native messaging (não requer administrador, mas pode ser restrita por política).
- Proxy corporativo: a bridge precisa alcançar o SEI e o ÓPERA (regras de `NO_PROXY`).
- **TLS no ÓPERA** — hoje inexistente (HTTP nas portas 8550/80/8080 `[PROVADO]`). Requisito para a variante servidor; fortemente recomendado de todo modo.

### 14.3 Dependências do navegador

- MV3: service worker efêmero (estado obrigatoriamente em `chrome.storage.session`).
- `chrome.cookies` com leitura de cookies `HttpOnly` — `[A VALIDAR]` contra a política do navegador gerenciado.
- Limite de 1 MB por mensagem do host nativo — contornado por projeto (arquivos não passam pela extensão), mas `[A VALIDAR]`.
- Native messaging pode ser restrito por política corporativa (`NativeMessagingBlocklist`).

### 14.4 Riscos de evolução do SEI

| Risco | Impacto | Mitigação |
|---|---|---|
| Mudança na estrutura de `Nos[x]` na árvore | Quebra total da leitura | Parser por blocos já é tolerante; fixtures de HTML real; erro nomeado |
| Mudança no formulário de criação de documento | Quebra da escrita | Validação por `"OK"` e por releitura da árvore falha explicitamente, sem criar documento errado |
| Novo mecanismo anti-automação (CAPTCHA, token por requisição) | Bloqueio total | Fora do controle do projeto; exigiria interlocução institucional |
| Migração para SEI com API oficial | Oportunidade | Arquitetura em camadas permite trocar apenas o `SeiClient` |

### 14.5 Riscos na interface do ÓPERA

Baixos por construção: a extensão não depende do DOM. Os pontos de acoplamento reais são as chaves de sessão e as assinaturas dos métodos internos usados pelos endpoints (`start_full_analysis_pipeline`, `get_current_form_data`, `DocxExporter.*`). Mitigação: manter esses endpoints como **única** fronteira, com testes que falhem em caso de mudança de assinatura.

**Risco específico:** a refatoração apartada (repositório separado) pode reescrever `nc_analyze_view.py` e o `pdf_processor`. A API `/api/v1/*` deve ser desenhada como contrato estável, para que a refatoração a implemente por trás — não como espelho da estrutura interna atual.

### 14.6 Limitações de segurança do Chrome

- Sem código remoto em MV3 (positivo para auditoria).
- Service worker sem estado persistente em memória.
- Ausência de acesso ao sistema de arquivos — daí a bridge.
- Diálogo nativo do `FilePicker` inacessível — daí a API.

### 14.7 Pontos que exigem validação em ambiente real

1. Flags e nomes dos cookies de sessão do SEI; leitura via `chrome.cookies` sob navegador gerenciado.
2. Comportamento de `SeiClient` com sessão puramente injetada (sem login), incluindo `Referer` e `url_mesa_atual`.
3. Formulário de pesquisa por NUP (se a Estratégia B for implementada).
4. Fidelidade do HTML aceito pelo editor do SEI (RF-P02).
5. Existência/cadastro de documento-modelo com os placeholders do ÓPERA (RF-P03).
6. Latência real ponta a ponta (LAN vs VPN).
7. Limite efetivo de mensagem do native messaging.
8. Prefixo de chaves do `client_storage` no `localStorage`.
9. Comportamento de `flet.fastapi.app` com a configuração atual (assets, upload, secret key) sem regressão.
10. Concorrência: várias sessões pareadas simultâneas no mesmo container.

---

## 15. Decisões arquiteturais pendentes

### 15.1 Comprovado pelos códigos e documentos analisados

| # | Fato | Fonte |
|---|---|---|
| C-01 | O ÓPERA não possui nenhuma API REST; `run_server.py` chama apenas `ft.app(...)` | `run_server.py` |
| C-02 | O README descreve a API REST como item **não concluído** do roadmap | `README.md:217` |
| C-03 | A UI Flet é renderizada em canvas (`CANVAS_KIT` por padrão) — automação por DOM é inviável | `flet_web/fastapi/app.py:27`; `run_server.py` |
| C-04 | O upload web usa URL assinada por HMAC gerada server-side; a extensão não pode forjá-la | `components.py:911`; `flet_web/fastapi/flet_upload.py:52-68` |
| C-05 | `flet 0.28.3` expõe `flet.fastapi.app(...)`, permitindo montar o app Flet numa FastAPI própria | `flet/fastapi/__init__.py`; `flet_web/fastapi/app.py` |
| C-06 | O pipeline opera sobre **caminhos de arquivo**, não objetos em memória | `nc_analyze_view.py:2451`; `pdf_processor.py:953` |
| C-07 | O analyzer aceita **apenas PDF** | `nc_analyze_view.py:497`; `components.py:922` |
| C-08 | Existe guarda de reentrância `_is_action_in_progress` | `nc_analyze_view.py:150,669` |
| C-09 | O pipeline já roda em threads e atualiza a UI por helpers thread-safe | `nc_analyze_view.py:3003,2369,2421` |
| C-10 | Exportação web grava em `assets/temp_docx_exports/` e dispara `page.launch_url`, sem limpeza | `nc_analyze_view.py:3074` |
| C-11 | `registrar_documento(..., assinar=False)` cria documento interno como **rascunho** — caminho implementado e em produção | `client.py:1374` |
| C-12 | `registrar_documento_por_modelo(..., assinar_documento=False)` idem, a partir de documento-modelo | `client.py:1582` |
| C-13 | **Não existe** upload de documento externo/binário no `SeiClient` | busca por `documento_externo`/`multipart`/`files=`/`upload` em `client.py` e `parser.py`: zero ocorrências |
| C-14 | O `SeiClient` **não possui** busca por NUP; todo método recebe `link_processo` orgânico | `client.py:474,615,1374` |
| C-15 | A árvore é fonte única de verdade; navegação especulativa é anti-padrão explícito | `NOTES_Sei.md` §0.1, §2, §4 |
| C-16 | Sessão expirada é detectada por `frmLogin` e vira `AuthError` | `client.py:152` |
| C-17 | `@require_session` dispara **login automático por senha do keyring** se a sessão não estiver marcada como válida | `client.py:42,122` |
| C-18 | O download termina sempre em disco, e as validações de integridade só existem nesse caminho | `client.py:682,911` |
| C-19 | `dump_html_on_error` grava HTML de resposta em `logs/debug/` | `client.py:53` |
| C-20 | Há idempotência por `nome_na_arvore` na criação de documento | `client.py:1374` |
| C-21 | O ÓPERA é servido em HTTP simples (8550/80/8080), sem TLS | `docker-compose.yml` |
| C-22 | Os placeholders dos templates DOCX do ÓPERA são `<campo>`, compatíveis com a substituição de `registrar_documento_por_modelo` | `nc_analyze_view.py:3138`; `client.py:1582` |

### 15.2 Requisitos (precisam ser construídos)

| # | Requisito |
|---|---|
| R-01 | Camada de API REST no ÓPERA (§4.5), montando o Flet via `flet.fastapi.app` |
| R-02 | Registro de pareamento sessão Flet ↔ código, com ciclo de vida em `did_mount`/`will_unmount` |
| R-03 | Endpoint de injeção de documentos, com gravação em `UPLOAD_TEMP_DIR` e limpeza por TTL |
| R-04 | Endpoint de disparo do pipeline respeitando a guarda de reentrância |
| R-05 | Endpoint de status derivado de estado observável do servidor |
| R-06 | Endpoint de resultado com validação (`get_current_form_data(validate_for_export=True)`) |
| R-07 | Gerador de HTML no `doc_generator.py`, reutilizando o mapeamento de campos existente |
| R-08 | Caminho de download em memória no `SeiClient`, preservando as validações de integridade |
| R-09 | Sessão do `SeiClient` por cookies injetados, com login por senha desabilitado |
| R-10 | Leitura de árvore sem obrigatoriedade da capa |
| R-11 | Bridge de native messaging embarcando o `SeiClient` |
| R-12 | Extensão MV3 (popup, service worker, content scripts) |
| R-13 | Confirmação de rascunho por releitura da árvore |
| R-14 | Limpeza de temporários (uploads e artefatos) por TTL |
| R-15 | Instalador e trilha de atualização da bridge |

### 15.3 Recomendações (escolhas de projeto, com alternativa)

| # | Recomendação | Alternativa registrada |
|---|---|---|
| RE-01 | Bridge **local** por native messaging | Bridge no servidor com cookies encaminhados (§7.7), condicionada a TLS |
| RE-02 | Estratégia **A** para localizar o processo (link orgânico da aba do SEI) | Estratégia B: busca por NUP no `SeiClient`, após levantamento |
| RE-03 | Peça no SEI como **documento interno rascunho** (A/B) | Documento externo com DOCX anexado (C), após levantamento |
| RE-04 | Extrair o `SeiClient` para pacote reutilizável | Dependência de caminho do repositório ePol inteiro |
| RE-05 | Arquivos nunca passam pela extensão | Streaming em chunks pelo native messaging (complexo, sem ganho) |
| RE-06 | Polling de status | Server-Sent Events (mais eficiente, mais superfície) |
| RE-07 | API na mesma porta do ÓPERA | Porta separada (exigiria CORS e nova regra de firewall) |

### 15.4 Hipóteses (não verificadas)

| # | Hipótese | Como validar |
|---|---|---|
| H-01 | O `PHPSESSID` do SEI é legível por `chrome.cookies` (inclusive `HttpOnly`) | Teste direto na estação |
| H-02 | O SEI possui formulário de pesquisa por NUP utilizável por scraping | DevTools sobre a busca real |
| H-03 | O editor do SEI aceita o subconjunto de HTML proposto sem perda relevante | Documento de teste |
| H-04 | O `client_storage` do Flet grava no `localStorage` com prefixo previsível | Inspeção no navegador |
| H-05 | O limite de mensagem do host nativo é 1 MB na versão em uso | Teste empírico |
| H-06 | A VM do ÓPERA alcança o SEI (relevante só para a variante servidor) | Teste de rede na VM |
| H-07 | O formulário de documento externo do SEI é automatizável por `requests` | Levantamento dedicado |

### 15.5 Decisões pendentes (exigem escolha do responsável pelo produto)

| # | Decisão | Opções | Impacto |
|---|---|---|---|
| **D-01** | Forma de reuso do `SeiClient` | pacote extraído · dependência de caminho · vendorizar | Manutenibilidade a longo prazo |
| **D-02** | Local da bridge | estação · servidor | Segurança × esforço de implantação |
| **D-03** | Tipo de documento SEI e nível de acesso padrão | definição da unidade | Conformidade |
| **D-04** | Documento-modelo no SEI para a estratégia (B) | criar · usar (A) por ora | Padronização da peça |
| **D-05** | A extensão oferece download do DOCX ao usuário? | sim (requer permissão `downloads`) · apenas rascunho no SEI | Permissões e privacidade |
| **D-06** | Como tratar o `FeedbackWorkflowManager` no fluxo automatizado | manter diálogo na UI · registrar com marcação "origem: extensão" · suprimir | Qualidade dos dados de feedback |
| **D-07** | TLS no ÓPERA | implantar agora · adiar | Pré-condição de D-02 = servidor |
| **D-08** | Onde o código da extensão e da bridge será versionado | neste repo · repo próprio · repo ePol | Governança |

### 15.6 A validar tecnicamente antes de codificar

1. Migração para `flet.fastapi.app` sem regressão (Fase 1 é justamente esse teste).
2. Manipulação da view a partir de thread de handler HTTP usando os helpers existentes.
3. `SeiClient` operando exclusivamente com sessão injetada.
4. Download em memória preservando integridade (comparação por hash).
5. Criação de rascunho em processo real com `assinar=False`, com confirmação na árvore.
6. Comportamento sob concorrência: duas sessões pareadas operando simultaneamente.

---

## Arquitetura Recomendada

### Resumo da solução

**Extensão Chrome MV3 + bridge local Python por Chrome Native Messaging + nova camada de API REST no ÓPERA.**

A extensão é apenas o painel de controle. Toda a interação com o SEI acontece em Python, reutilizando integralmente o `SeiClient` e seus parsers. Toda a interação com o ÓPERA acontece por uma API REST nova, servida no mesmo processo e na mesma porta do app Flet. **Os documentos nunca passam pela extensão nem tocam o disco do usuário.**

### Componentes

| Componente | Papel | Estado |
|---|---|---|
| **Extensão MV3** (popup, service worker, 2 content scripts) | Painel de operação; máquina de estados; leitura de cookies do SEI e da URL do processo | A construir |
| **ÓPERA-SEI Bridge** (executável Python, host de native messaging) | Reutiliza `SeiClient`; baixa peças em memória; envia ao ÓPERA; cria o rascunho no SEI | A construir (casca fina) |
| **`SeiClient` + parsers** | Toda a lógica do SEI: árvore, downloads, criação de documento | **Existe**; requer extração para pacote e dois ajustes cirúrgicos |
| **API `/api/v1/*` no ÓPERA** | Pareamento, injeção de peças, disparo, status, resultado, produção | A construir |
| **Núcleo do ÓPERA** (pipeline, LLM, `DocxExporter`) | Processamento e análise | **Existe**; requer apenas um gerador de HTML adicional |

### Fluxo de dados

```
  Aba SEI ─(URL do processo, NUP)─┐
  chrome.cookies ─(sessão SEI)────┤
                                  ▼
                          SERVICE WORKER ──native messaging──► BRIDGE (Python)
                                  ▲                              │  │
                                  │ estado/eventos               │  │
                               POPUP                             │  │
                                                                 │  │
                       SEI ◄── árvore, downloads, criação ───────┘  │
                                                                    │
                      ÓPERA ◄── peças, disparo, status, artefato ───┘
                        │
                        └── UI (canvas): usuário revisa e corrige
```

Trafegam pela extensão apenas mensagens de controle. Bytes de documento fazem o caminho `SEI → bridge (memória) → ÓPERA` e, na volta, `ÓPERA → bridge → SEI`.

### Justificativa técnica

1. **A automação de UI está descartada por fato, não por preferência.** A interface do ÓPERA é um canvas CanvasKit sem DOM semântico, e o upload web depende de URL assinada por HMAC no servidor. Não existe caminho de UI a preferir ou evitar: só existe o caminho programático.

2. **A lógica do SEI não deve ser reimplementada.** O `SeiClient` e o `NOTES_Sei.md` concentram um corpo de correções obtidas por tentativa e erro — hidden mirrors do ddslick, `<button type=submit>` fora de `find_all('input')`, double-encoding de placeholders no CKEditor, `NavigableString` quebrando o `urlencode`, validação por `"OK"` do editor, hashes que expiram após popup. Reescrever isso em JavaScript criaria duas implementações divergentes da parte mais frágil do sistema. A bridge Python elimina esse risco por completo.

3. **A sessão do usuário é reaproveitada sem tocar em senha.** Cookies lidos do próprio navegador, injetados numa `requests.Session`, com o login por keyring explicitamente desabilitado. Nenhuma credencial nova é criada, solicitada ou armazenada.

4. **Native messaging é mais seguro que um servidor em localhost.** Nenhuma porta aberta; apenas a extensão declarada consegue falar com a bridge; ciclo de vida gerenciado pelo navegador. A limitação de 1 MB por mensagem deixa de importar porque os arquivos, por projeto, não passam por esse canal.

5. **A bridge local mantém os cookies do SEI na máquina do usuário.** Enquanto o ÓPERA for servido por HTTP simples, encaminhar credenciais de sessão do SEI ao servidor seria um retrocesso. A variante servidor fica registrada, condicionada a TLS e a parecer de segurança.

6. **A API na mesma porta do Flet é a menor mudança possível.** `flet.fastapi.app(...)` existe na versão instalada e permite montar o app atual dentro de uma FastAPI própria, preservando assets, upload, chave secreta, porta e o deploy por bind mount. Sem CORS, sem porta nova, sem segundo container.

7. **A peça vai ao SEI pelo caminho que já funciona.** `registrar_documento(..., assinar=False)` produz exatamente o rascunho não assinado pedido, com idempotência por nome e validação de sucesso por resposta `"OK"` e releitura da árvore. O upload de documento externo — que seria o caminho "natural" para um DOCX — **não existe** no `SeiClient` e exigiria construir do zero o fluxo mais delicado do SEI. O DOCX continua sendo entregue ao usuário; o que vai para o processo é uma minuta editável e revisável dentro do próprio SEI.

8. **O acoplamento fica confinado a uma fronteira estreita.** Só a API `/api/v1/*` conhece as entranhas da view. Quando a refatoração apartada substituir o núcleo, basta que ela implemente o mesmo contrato — a extensão e a bridge não mudam.

### Alterações necessárias neste repositório (conservadoras, por design)

| Arquivo | Mudança | Risco |
|---|---|---|
| `run_server.py` | Montar `flet.fastapi.app` numa FastAPI própria, preservando parâmetros atuais | Médio — é o bootstrap de produção; exige teste de regressão dedicado (Fase 1) |
| `SOURCE/api/` (novo) | Camada REST isolada | Baixo — código novo, sem tocar o existente |
| `SOURCE/flet_ui/views/nc_analyze_view.py` | Registro/desregistro de pareamento em `did_mount`/`will_unmount` + botão de copiar código | Baixo — adição pontual |
| `SOURCE/core/doc_generator.py` | Gerador de HTML reutilizando o mapeamento de campos | Baixo — adição |
| Rotina de limpeza | TTL para `uploads_temp` e `temp_docx_exports` | Baixo — corrige um vazamento já existente |

Nenhuma alteração em `SOURCE/settings.py`, `Dockerfile` ou `docker-compose.yml` é necessária para as fases 1–6. Caso venham a ser (por exemplo, TLS ou nova variável de ambiente), tratam-se de mudanças de maior risco e devem ser confirmadas antes de aplicadas, conforme `CLAUDE.md` §9.
