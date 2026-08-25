## TODO: Próximas Tarefas:

[x] - Doc informação padrão
[x] - Monitorar e corrigir erros de log da versão hospedada
[x] - Prompt_estruturado editável;

[ ] - Formatar Tipos Penais conforme regex requerido

[ ] - endereço customizado: opera-assistente.pf.gov.br

- Refatorar toda arquitetura migrando para modelo de API
- Usar supabase local em vez de firebase, ou database próprio? 
- Refazer todo o frontend com React sobre a API desenvolvida

# ----------------------------------
[ ] - Observalidade com Jaeger + Grafana  ?

===============================================================================================================

## Plano Resumido de Ação sobre as Tarefas da Fase 3 (Chat com PDF, RAG e Anonimização. A entregar):

    **Novo Módulo de UI:**
    *   `src/flet_ui/views/chat_view.py`: Conterá a classe `ChatViewContent`, responsável por toda a interface do usuário do chat, incluindo upload de arquivos, exibição de mensagens, painel de métricas e o drawer de configurações.

    **Novo Módulo de Orquestração:**
    *   `src/core/chat_llm_orchestrator.py`

    **Atualização de Módulos Existentes:**
    *   `src/security/anonymizer.py`: Será expandido para incluir a lógica de NER com spaCy e o mapeamento reverso (desanonimização).
    *   `src/flet_ui/router.py`: Será atualizado para incluir a nova rota `/chat`.
    *   `src/flet_ui/layout.py`: Será atualizado para adicionar o novo item na `NavigationRail`.

### Fase 3.0: 
    - src/flet_ui/views/chat_view.py com App mínimo para testes rápidos (run_chat_test.py)
    - Implementar chat_llm_orchestrator.py em src/core, em vez de usar ai_orchestrator.py, para integração exclusiva com api da OpenAI.
    - chat_llm_orchestrator deve utilizar a nova API da openai: client.responses.create

#### Fase 3.1: Módulo Chat w/ Docs:
    - Definir um system-prompt adequado.
    - Inicialmente apenas PDF; Posteriormente podemos extender para outros tipos de arquivos;
    - Aproveitar pré-processamento c/ filtro de páginas usado no módulo NC-Analyze;
    - Inicialmente sem RAG; Vamos manter o chat com amplo contexto do arquivo (possivelmente filtrado no pre-processamento);
    - Integrar dialog de métricas de consumo da API da OpenAI e de uso de tokens do LLM.

    - Inserir metadados mínimos no contexto: nome do arquivo/documento e número das respectivas páginas com conteúdo referenciado.
    - Ajustar Drawer_options para servir tanto ao nc_analyzer quanto ao chat_docs, customizado para as respectivas views.
    - Ajustar panel de métricas de chat_docs; na verdade substituir por Text indicativo na top_bar e o detalhamento passará a ser mostrado em Dialog.
    - Default Settings devem ser diferentes para nc_analyse e chat_view; configurações padrão por view e por usuário; 
    - Aproveitamento do mesmo conteudo processado;

    - implementar o updater.py e separar a aplicação no tocante aos módulos pesados (modelo de embeddings, e NER);
    - Novos módulos incorporados: core/chat_llm_orchestrator.py, services/engine_manager.py, /update_manager.py, e /local_db_manager.py
    - Ao final desta etapa, devemos entregar a aplicação para testes em produção por usuários selecionados.

#### Fase 3.2:
    - Alterar home-design com nome Opera e Logo cérebro ?
    - Permitir edição de configurações para os usuários em geral;
    - Ajustes no prompt estruturado, reordenando, e Liberando-o para edição pelo usuário comum;
    - Conferir atualização do prompt estruturado;

> Fase Llamaindex:
    - Posteriormente, em vez de usar Rag com serviço 'File-Search' da OpenAI, vamos tentar o LLamindex.
    - Vamos manter uma sistemática híbrida de uso de Amplo Contexto e RAG a depender do tamanho do(s) arquivo(s) submetidos à sessão do chat.
    - Parâmetros iniciais:CHUNK_SIZE = 2048, CHUNK_OVERLAP = 256, e SIMILARITY_TOP_K = 5

    - Elaborar RAG Híbrida com busca lexical integrada! (que também serve para pesquisa sobre os Metadados de paginação e nomes de arquivo/doc).
    - Ajustar panel de arquivos para conter as opções e visualização dos modos de chat:
        - amplo contexto ou RAG  /  Otimizado ou não (se amplo contexto) / Anonimizado ou não

> Fase Anonimização de dados:
    - Posteriormente, vamos implementar a opção do usuário anonimizar os dados do(s) documento(s) submetidos à LLM.
    - spaCy + Regex para números de identificação, emails, etc.
    - Estruturar a integração da anonimização/desanonimização de dados com o RAG, LLM e a UI.

    - Detalhamento das Tarefas desta etapa:

	> Lógica de Anonimização - `anonymizer.py`
        Expandiremos o módulo existente para suportar NER e a desanonimização.

        Classe `DataAnonymizer` (Expansão):
        *   `__init__`: Carregará o modelo `spaCy` (`pt_core_news_lg`) na inicialização.
        *   `anonymize_text(self, text: str, custom_terms: list[str] = []) -> tuple[str, dict]`:
            *   Receberá o texto bruto e uma lista opcional de termos customizados.
            *   **Passo 1 (NER):** Processará o texto com o `spaCy` para identificar entidades (`PER`, `LOC`, `ORG`).
            *   **Passo 2 (Regex):** Aplicará as regras de regex para CPFs, CNPJs, telefones, etc.
            *   **Passo 3 (Termos Customizados):** Buscará e substituirá os termos fornecidos pelo usuário.
            *   **Mapeamento:** Durante a substituição, criará um dicionário de mapeamento (ex: `{'[PESSOA_1]': 'João da Silva', '[CPF_1]': '123.456.789-00'}`).
            *   **Retorno:** Retornará uma tupla contendo o `texto_anonimizado` e o `dicionario_mapeamento`.
        *   `deanonymize_text(self, anonymized_text: str, mapping_dict: dict) -> str`:
            *   Receberá um texto anonimizado e o dicionário de mapeamento.
            *   Fará a substituição reversa dos placeholders (ex: `[PESSOA_1]`) pelos valores originais.
            *   Retornará o texto legível para o usuário.

        > Integração e Modificações
        Dependências:
        *   Adicionar `spacy` ao `requirements.txt`.
        *   Incluir instrução no `README.md` para baixar o modelo: `python -m spacy download pt_core_news_lg`.

> Fase Feedback dos usuários:
    - Estruturar forma de obtenção de feedback dos usuários sobre qualidade da interação com a LLM no novo módulo 'Chat with Docs';

> Fase final: Antes de entregar chat_w/docs, Proceder alterações no módulo nc_analyzer:
    - Corrigir mensagem de confirmação de e-mail através do firebase;
    - Simplificar ai_orchestrator.py, eliminando lib langchain não utilizada; Suprimir opções de prompts não utilizadas (manter apenas o prompt único);
    - Revisar sistemática de filtro de páginas (pdf_processor.py);
    - Rever lógica do modo de filtro 'get_pages_among_similars_groups'
    - Ajustar para uso dos modelos gpt-5 com parâmetros reasoning e verbosity;
    - Acrescentar no processing_metadata: modelo de vetorização utilizado e similaridade utilizada.

    - Módulo de testes automáticos sobre respostas de modelos;
    - Habilitar opção de uso de provedor LLM local (servido através de endpoint da rede corporativa);
    - biblioteca de prompts do usuário;
    
    - Habilitar opção de uso de outros provedores de LLMs, além da OpenAI;
    - Implementar Weakref nas threads de processamento de nc_analyze_view.
    - Em nc_analyze_view.py, Segregar InternalAnalysisController em 3 classes: 
        - FilesProcessorController: responsável por interagir com o PDFDocumentAnalyzer;
        - AnalysisController: responsável pela interação com ai_orchestrator;
        - MetricsController: responsável pelo tratamento e envio de métricas ao firestore;
        Obs.: As novas classes podem ser módulos específicos dentro de src\flet_ui\controllers\
    - ChatViewContent usará o mesmo FilesProcessorController que nc_analyze;
    - Criar um ChatllmController próprio para interação com chat_llm_orchestrator;
    - MetricsController deve ser flexível o suficiente para atender às duas views (nc_analyze e chat_view).

# ----------------------------------


