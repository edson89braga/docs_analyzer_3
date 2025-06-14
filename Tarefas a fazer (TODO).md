======================================================================================
# TODO: Próximas Tarefas:

> revisar sistemática do logging em nuvem;

> Linkar alertas e msgs informativas de responsabilidade no uso de IA

> pyinstaller e testes na rede;

> Testes de Score sobre multiplas formas de prompt: modelos, prompts, temperaturas.

> Check lentidão na inicialização do app

------------------------------------------------------------------
1. Mensagem Inicial (Login / Primeiro Acesso)
Objetivo: Estabelecer desde o primeiro contato que a IA é uma ferramenta de suporte, e não um substituto para o julgamento humano.
Localização Sugerida:
Na tela de login, logo abaixo dos campos de senha.
Alternativamente, como um diálogo de confirmação (AlertDialog) que aparece apenas no primeiro login do usuário, forçando-o a ler e concordar.
Texto Sugerido:
Uso Responsável da IA
Este sistema utiliza Inteligência Artificial como uma ferramenta de auxílio à análise. As informações e sugestões geradas são preliminares e devem ser rigorosamente verificadas por um analista humano. A responsabilidade final pela correção, interpretação e uso dos dados é inteiramente do usuário.

3. Alerta Contextual (Junto aos Resultados da Análise)
Objetivo: Alertar o usuário no momento exato em que ele está consumindo a informação gerada pela IA, reforçando a necessidade de revisão antes de qualquer ação.
Localização Sugerida:
Como um cabeçalho ou um balão de aviso (ft.Container com ícone e cor de destaque) imediatamente acima da área onde os resultados da análise LLM são exibidos (LLMStructuredResultDisplay).
Texto Sugerido:
Análise Preliminar (Gerada por IA)
Atenção: Todos os campos, classificações e resumos a seguir foram gerados por um modelo de linguagem e devem ser tratados como uma sugestão inicial. Revise e valide cuidadosamente cada informação antes de prosseguir com qualquer ato administrativo ou encaminhamento oficial.

4. Seção "Sobre / Termos de Uso"
Objetivo: Fornecer um detalhamento completo das limitações e responsabilidades, servindo como um termo de referência formal dentro da aplicação.
Localização Sugerida:
Em um item de menu, talvez dentro das "Configurações" ou em um link "Sobre" na AppBar. Pode abrir um AlertDialog ou uma nova view.
Texto Sugerido (mais detalhado):
Diretrizes de Uso e Limitações da IA
Ao utilizar o Docs Analyzer, você concorda e compreende os seguintes pontos:
Ferramenta de Suporte: A IA é um assistente para otimizar a análise preliminar de documentos. Ela não substitui a expertise, o julgamento crítico e a decisão final do analista humano.
Verificação Obrigatória: É de sua inteira responsabilidade verificar, corrigir e validar todas as informações extraídas, classificadas e resumidas pela IA. Os resultados podem conter imprecisões, omissões ou erros.
Alucinações e Vieses: Modelos de linguagem podem gerar informações que parecem factuais, mas não estão presentes no documento original (alucinações) ou refletir vieses contidos em seus dados de treinamento. Redobre a atenção em dados críticos como nomes, datas, valores e tipificações.
Responsabilidade (Accountability): Todas as ações, decisões e documentos oficiais gerados a partir do uso desta ferramenta são de responsabilidade exclusiva do usuário que os executa e subscreve. O sistema registra métricas de uso para fins de auditoria e aprimoramento.
Não é Aconselhamento Jurídico: As tipificações penais e classificações sugeridas pela IA são baseadas em padrões e não constituem parecer ou aconselhamento jurídico formal. A decisão final sobre o enquadramento legal cabe à autoridade competente.

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

