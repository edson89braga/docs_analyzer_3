
> Data de atualização das informações abaixo: 20/09/2025

> **Adendo 13/08/2026:** provider `llm_pf` migrado para `Qwen3.5-35B-A3B-FP8` (janela de
> contexto 128k, antes 32k com `Qwen3-8B-AWQ`). O campo "Limite Tokens Input" do drawer de
> configurações agora aceita ficar **vazio = truncagem automática**: quando `llm_provider ==
> "llm_pf"`, `nc_analyze_view.py` (`_pdf_processing_thread_func`) e `chat_view.py`
> (`_preprocess_documents`) calculam o orçamento de tokens em runtime via
> `ai_orchestrator.compute_llm_pf_auto_token_limit()`, descontando o overhead real do prompt
> fixo (medido com tiktoken) e uma reserva de output (`LLM_PF_OUTPUT_RESERVE_TOKENS`) da janela
> do modelo (`LLM_PF_CONTEXT_WINDOW`). O chat soma ainda `LLM_PF_CHAT_HISTORY_RESERVE_TOKENS` para
> não deixar o contexto do documento consumir o espaço dos próximos turnos. Constantes em
> `SOURCE/settings.py`. `FALLBACK_ANALYSIS_SETTINGS["llm_input_token_limit"]` passou a ser `None`
> (automático) por padrão. Para outros providers (`openai`), o modo automático ainda não é
> suportado (sem tabela de janela de contexto por modelo neste repo) — cai num fallback fixo de
> 180.000 tokens, com log de warning.

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