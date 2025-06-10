======================================================================================
# TODO: Próximas Tarefas:

> Atualização ai_orchestrator para lidar com prompts agrupados e aproveitamento de cached_tokens;
-------
> Testes de Score sobre multiplas formas de prompt: modelos, prompts, temperaturas.

> Linkar alertas e msgs informativas de responsabilidade no uso de IA

> Check lentidão na inicialização do app

> revisar sistemática do logging em nuvem;

> pyinstaller e testes na rede;

------------------------------------------------------------------

> Tests pdf_processor.py, ai_orchestrator.py, doc_generator.py
> Test  View: analyze_pdf1

# TODO: Posteriormente: 

> Fix: CreateUser: Tratar erro "message": "EMAIL_EXISTS"

> Exibir prompt_estruturado editável;

> Melhorias na apresentação dos metadados: coluna em vez de lista única?
> Melhorias na responsividade do LLMStructuredResultDisplay;
> Reorganização referente aos métodos de limpeza e atualização da nc_analyze_view
    - Prompt inicial: "Considere a versão atual do módulo nc_analyze_view.py. Identifique oportunidades de refatoração relacionadas aos métodos de limpeza e atualização da interface gráfica (GUI), que atualmente são invocados em múltiplos pontos do código. Proponha uma refatoração pontual que centralize essa lógica de atualização, simplifique a manutenção e garanta o correto tratamento das flags relacionadas a dados salvos dinamicamente."
> Reorganização de InternalAnalysisController: passar para outro módulo?
> Reorganização de FeedbackWorkflowManager: incorporar à FeedbackDialog?

============================================================================================================================

# RETIRAR do nc_analyze_view.py:
> Concentrar atualização da gui para evitar o espalhamento dos seus 6 métodos internos de atualização;

> Além dos métodos `_calc_costs_embedding_process` e `_calc_costs_llm_analysis`, outros potenciais candidatos à realocação:

    Dentro da classe `InternalAnalysisController`:

    1.  _log_analysis_metrics   -> firebase_client.py
    2.  save_feedback_data_now  -> firebase_client.py
        feedback_data_list      -> firebase_client.py

        *   **O que faz:** Coleta diversos dados da sessão e dos metadados de processamento/LLM e os envia para o Firestore.
        *   **Por que mover:** A lógica de coletar, formatar e enviar métricas é uma responsabilidade de serviço, não de visualização.

    3.  _pdf_processing_thread_func -> pdf_processor.py (método de mais alto nível dentro)

        *   **O que faz:** Este método atualmente chama sequencialmente vários métodos do `self.pdf_analyzer` (como `extract_texts_and_preprocess_files`, `_build_combined_page_data`, `analyze_similarity_and_relevance_files`, `filter_and_classify_pages`, `group_texts_by_relevance_and_token_limit`) e também `ai_orchestrator.get_embeddings_from_api`. Ele também prepara o dicionário `proc_meta_for_ui`.
        *   **Por que mover:** A orquestração dessas etapas de processamento de documento é uma lógica de negócio central. A view deveria apenas disparar esse processo e receber os resultados finais e metadados prontos.

    4.  _llm_analysis_thread_func -> ai_orchestrator.py  

        *   **O que faz:** Chama `ai_orchestrator.analyze_text_with_llm`, processa a resposta (incluindo parse de JSON para `FormatAnaliseInicial` se necessário) e prepara `llm_meta_for_gui`.
        *   **Por que mover:** A view não deveria se preocupar com o formato bruto da resposta da LLM (string JSON vs. objeto). O `ai_orchestrator` poderia ter uma função que já retorna o objeto `FormatAnaliseInicial` parseado e os metadados da LLM prontos.
        
        * try_convert_to_pydantic_format já criado em prompts.py


    Dentro da classe `InternalExportManager`:

    6.  **`_get_default_filename_base`**: -> utils.py
        *   **O que faz:** Gera um nome base para arquivos exportados a partir do nome do lote na sessão.
        *   **Por que mover:** É uma pequena função utilitária de manipulação de strings.

    7.  **`copy_template_to_assets`**: -> utils.py
        *   **O que faz:** Copia arquivos de template para o diretório de assets.
        *   **Por que mover:** Operações de sistema de arquivos.

    Dentro da classe `FeedbackWorkflowManager`:

    8.  **`_get_prepared_feedback_data(self)`**: -> Tornar uma função acessória independente, tal como get_api_key_in_firestore
        *   **O que faz:** Compara os dados originais da LLM com os dados atuais da UI (após edição do usuário) para determinar quais campos foram editados, e calcula a similaridade para campos textuais.
        *   **Por que mover:** A comparação de dados e o cálculo de similaridade são lógicas de processamento/negócio, não diretamente de UI.

