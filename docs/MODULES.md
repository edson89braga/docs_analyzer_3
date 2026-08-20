
> Data de atualização das informações abaixo: 20/09/2025

> **Adendo 13/08/2026:** provider `llm_pf` migrado para `Qwen3.5-35B-A3B-FP8` (janela de
> contexto 128k, antes 32k com `Qwen3-8B-AWQ`). O campo "Limite Tokens Input" do drawer de
> configurações agora aceita ficar **vazio = truncagem automática**: quando `llm_provider ==
> "llm_pf"`, `nc_analyze_view.py` (`_pdf_processing_thread_func`) e `chat_view.py`
> (`_preprocess_documents`) calculam o orçamento de tokens em runtime via
> `ai_orchestrator.compute_llm_pf_auto_token_limit()`, descontando o overhead real do prompt
> fixo (medido com tiktoken) e a reserva de output (`LLM_PF_MAX_OUTPUT_TOKENS`) da janela
> do modelo (`LLM_PF_CONTEXT_WINDOW`). O chat soma ainda `LLM_PF_CHAT_HISTORY_RESERVE_TOKENS` para
> não deixar o contexto do documento consumir o espaço dos próximos turnos. Constantes em
> `SOURCE/settings.py`. `FALLBACK_ANALYSIS_SETTINGS["llm_input_token_limit"]` passou a ser `None`
> (automático) por padrão. Para outros providers (`openai`), o modo automático ainda não é
> suportado (sem tabela de janela de contexto por modelo neste repo) — cai num fallback fixo de
> 180.000 tokens, com log de warning.
>
> **Correção posterior (13/08/2026):** a reserva de output do cálculo automático era uma constante
> de planejamento própria (`LLM_PF_OUTPUT_RESERVE_TOKENS = 8.000`, removida), menor que o teto de
> fato pedido à API (`LLM_PF_MAX_OUTPUT_TOKENS = 16.000`), e a margem de segurança era aplicada como
> desconto `(1 - margem)` sobre o orçamento total — que não é o inverso da inflação `(1 + margem)`
> usada em `compute_llm_pf_max_output_tokens()`. As duas inconsistências somadas deixavam o
> `max_tokens` cair para ~8.000 em lotes grandes; com `enable_thinking=True` o modelo consumia tudo
> no raciocínio e devolvia `content` vazio (`finish_reason='length'`). Agora o orçamento de input é
> `(LLM_PF_CONTEXT_WINDOW - LLM_PF_MAX_OUTPUT_TOKENS) / (1 + LLM_PF_TOKEN_SAFETY_MARGIN)` menos o
> overhead do prompt, o que preserva os 16.000 tokens de saída por construção, truncando mais páginas
> de entrada em troca. Quando o `content` ainda assim vier vazio, `analyze_text_with_llm()` usa
> `message.reasoning_content` como texto bruto, para a UI renderizar o teor aproveitável.

> **Adendo 13/08/2026 — atualizações de UI a partir de threads.** Correção do
> `AttributeError: 'NoneType' object has no attribute 'session'` + `AssertionError` do Flet que
> matavam a thread de análise LLM quando o usuário navegava para outra view durante o
> processamento. Convenções agora válidas para toda a UI:
> - **`safe_control_update(control)` / `safe_page_update(page, *controls)`**
>   (`components/components.py`) substituem o idioma `if ctl.page and ctl.uid: ctl.update()` e
>   o bloco manual `with update_lock: page.update()`. Serializam o flush sob
>   `page.data["global_update_lock"]` (adquirido **com timeout de 5s**, degradando para update
>   sem lock em vez de congelar a sessão) e engolem `AssertionError`/`PageDisconnectedException`
>   com log de warning, evitando que uma árvore de controles inválida mate a thread chamadora.
> - O `global_update_lock` passou de `Lock` para **`RLock`** (`app.py`, `router.py`): `page.add()`
>   dentro de uma seção crítica dispara `did_mount()` das views, que atualizam seus próprios
>   controles — reentrância legítima na mesma thread.
> - `AnalyzePDFViewContent` e `ChatViewContent` expõem **`_is_view_usable()`** (`_is_mounted` +
>   `page` válida). Todo método de atualização de UI agendado por thread (`page.run_thread`)
>   checa esse guard antes de tocar `self.page.session` ou controles. `ChatViewContent` ganhou
>   `will_unmount()` para zerar `_is_mounted`.
> - Threads de background do chat (`_preprocess_documents`, `_extract_raw_context_from_files`)
>   capturam `page = self.page` na entrada — o Flet anula `self.page` no unmount, mas a sessão
>   continua viva, e os resultados devem ser persistidos mesmo se o usuário sair da view (mesma
>   estratégia já usada em `_handle_ai_response_thread`).
> - Nos blocos `finally` das threads de `nc_analyze_view`, `hide_loading_overlay()` roda **antes**
>   do guard de montagem (o overlay é global da página, não da view) e as mutações de controle
>   só depois.

# nc_analyze_view.py

## Funções importadas principais:
- get_user_cache
- firestore_client

## Variáveis globais:
- Constantes para nomes de controles
- Enums tipo_exportação
- Enums option_feedback

## Função Factory:
- create_analyze_pdf_content

## Funções auxiliares:
- load_prompts_from_firestore
- get_api_key_in_firestore
- get_prepared_feedback_data
- get_field_type_for_feedback

## Classe Principal: 

- AnalyzePDFViewContent

## Subclasses:
- LLMStructuredResultDisplay

- InternalFileListManager
- InternalAnalysisController
- InternalExportManager
- FeedbackWorkflowManager + FeedbackDialog

## Variáveis de armazenamento:

- user_cache[KEY_SESSION_LIST_TO_PROMPTS]	= Componentes em cloud: prompts em versão template + Listas de referências para replace
- user_cache[KEY_SESSION_PROMPTS_DICT] 		= Chunks do(s) prompt(s) final(is)
- user_cache[KEY_SESSION_PROMPTS_FINAL] 	= Dicionário contendo prompts de uso, em versão pronta para uso;

## Fluxos: 

1) create_analyze_pdf_content: get_user_cache + load_prompts_from_firestore 
    -> AnalyzePDFViewContent: _build_gui_structure + AnalyzeSettingsDrawer + LLMStructuredResultDisplay + _initialize_file_picker

2) CTL_PROMPT_STRUCT_BTN: 	_toggle_prompt_view -> _create_prompt_display_layout
3) CTL_SETTINGS_BTN:		_handle_toggle_settings_drawer

4) CTL_UPLOAD_BTN: 	-> _handle_upload_click
5) CTL_PROCESS_BTN:	-> _handle_process_content_click
6) CTL_ANALYZE_BTN:	-> _handle_analyze_click
7) CTL_RESTART_BTN:	-> _handle_restart_click
8) CTL_EXPORT_BTN: 	-> export_manager.handle_export_selected

### TODO:
- Detalhar os fluxos envolvendo os outros métodos abaixo

    _initiate_analysis_step
    _update_export_button_menu

    _update_gui_from_state: _update_button_states + _update_processing_metadata_display + _update_llm_metadata_display + _show_info_balloon_or_result

    _reset_processing_and_llm_results
    _reset_llm_results

    _clear_all_data_and_gui + clear_user_cache + _remove_data_session



# chat_view.py

## Fluxos:

1) create_chat_view_content -> ChatViewContent -> _build_layout -> _restore_state_from_session

_handle_upload_click 	-> _handle_files_uploaded   -> _extract_raw_context_from_files -> session.set(KEY_SESSION_CHAT_RAW_PAGES_TEXT,...) & session.set(KEY_SESSION_CHAT_DOCUMENT_CONTEXT,...)
                                                    -> self.page.session.set(KEY_SESSION_CHAT_FILES, files)

_handle_optimize_click 	-> _preprocess_documents(KEY_SESSION_CHAT_RAW_PAGES_TEXT) -> self.page.session.set(KEY_SESSION_CHAT_DOCUMENT_CONTEXT, aggregated_text)

_handle_send_message 	-> THREAD: _get_context_and_call_ai -> Se texto ainda não processado: _get_raw_document_context -> _handle_ai_response -> _set_processing_state(False)
						-> _set_processing_state(True)

# src/flet_ui/settings_drawer.py

## Variáveis config:
- Dict:
    FALLBACK_ANALYSIS_SETTINGS  

- Session_Key:
    KEY_SESSION_LOADED_LLM_PROVIDERS
    KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS
    **KEY_SESSION_ANALYSIS_SETTINGS**
    KEY_SESSION_CHAT_PROMPT_ACTIVE_KEY

- User_cache_key:
    KEY_SESSION_CHAT_PROMPT_STRICT
    KEY_SESSION_CHAT_PROMPT_FLEXIBLE
    KEY_SESSION_CHAT_PROMPT_CUSTOM

## BaseSettingsDrawer = AnalyzeSettingsDrawer:

build_content:
    controls["proc_vectorization_dd"]               
    controls["similarity_threshold_slider"]         
    + controls["similarity_threshold_value_label"]  
    controls["llm_provider_dd"]                     
    controls["llm_model_dd"]                        
    controls["llm_token_limit_tf"]                  
    controls["temperature_slider"]                  
    + controls["temperature_value_label"]           
    controls["llm_max_output_length_tf"]    
    controls["reasoning_effort_dd"]         
    controls["verbosity_level_dd"]          

values_settings = page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or FALLBACK_ANALYSIS_SETTINGS.copy()

### on_change (all controls):

setup_event_handlers:
    if slider -> _handle_slider_change
    _handle_provider_change  -> _populate_models_for_selected_provider   -> _handle_model_change
    _handle_model_change     -> _toggle_model_specific_fields            -> save_settings_to_session
    _handle_setting_change   -> save_settings_to_session

### Fluxos:

- build_content                 -> page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) -> _populate_models_for_selected_provider + _builds...
- save_settings_to_session      -> _get_settings_from_controls -> page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, new_settings)
- load_settings_into_controls   -> page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) -> _toggle_model_specific_fields + _update_reset_button_visibility
- _handle_reset_settings_click  -> page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS) + load_settings_into_controls

## ChatSettingsDrawer:

-> load_default_prompts_from_firestore_or_fallback
-> get_user_cache + build_content + _get_active_prompt_text + _build_instructions_prompt_section
-> open_prompt_dialog:
    - update_editor_text
    - save_and_close

### Nota (20/08/2026) — escopo do "prompt customizado" persistido no SQLite

`LocalDBManager.save_custom_prompt()` / `get_custom_prompt()` (`SOURCE/services/local_db_manager.py`)
**não é um repositório de prompts genéricos da aplicação** — a única coisa persistida ali, via
`ChatSettingsDrawer.save_and_close`, é o texto do system-prompt customizado da opção "Personalizado"
no diálogo de instruções do **chat com documentos** (chave fixa `"chat_custom"`, escopada por
`user_id`). Não existe (ainda) nenhum mecanismo de prompts customizados para a análise de
notícias-crime (`nc_analyze_view.py`) ou qualquer outro fluxo — só o chat.

**Pendência confirmada:** a tabela `chat_history`, criada no mesmo schema (`_create_tables`), nunca
teve nenhum `INSERT`/`SELECT` implementado em lugar nenhum do código — o histórico de mensagens em
`chat_view.py` (`chat_history_view`) vive só em memória da sessão (`ft.ListView`), não é persistido.
Se histórico de chat entre sessões vier a ser um requisito, é essa tabela que precisa ser
efetivamente conectada a `chat_view.py`.