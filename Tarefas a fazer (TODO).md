======================================================================================
# TODO: Próximas Tarefas:
> pyinstaller e testes na rede;
------------------
> Set App-Admin
> Testes de Score sobre multiplas formas de prompt: modelos, prompts, temperaturas.
> Doc README + Fluxogramas
> Vídeo-apresentação

# PyTestes:
> Tests pdf_processor.py, ai_orchestrator.py, doc_generator.py
> Test  View: analyze_pdf1

# TODO: Posteriormente: 
> Exibir prompt_estruturado editável;
> Melhorias na apresentação dos metadados: coluna em vez de lista única?
> Rever lógica do modo de filtro 'get_pages_among_similars_groups'

# AVALIAR:
> Reorganização de InternalAnalysisController: passar para outro módulo?
> Reorganização de FeedbackWorkflowManager: incorporar à FeedbackDialog?

=============================================================================================================================================

Problemas de renderização, estado inconsistente ou falhas em novas abas — geralmente se origina de uma combinação de três fatores principais:

1.  **Gerenciamento de Estado do Lado do Servidor (Server-Side State)**
2.  **Threads e Recursos Globais**
3.  **Ciclo de Vida da Conexão Flet**

### 1. Gerenciamento de Estado do Lado do Servidor

**Problema:** No modo `WEB_BROWSER`, cada aba ou cliente que se conecta à sua aplicação cria uma **nova sessão de usuário** no backend Python. O Flet gerencia isso criando uma instância de `Page` para cada conexão. No entanto, se você armazena dados em **variáveis globais** no seu código Python, essas variáveis são compartilhadas entre **TODAS** as sessões.

**Exemplo no código:**

*   `src/utils.py`: A variável `_SERVER_SIDE_CACHE = {}` é global. Cada sessão de usuário (`page.session_id`) recebe uma entrada nela. Isso está **correto** e é a forma idiomática de isolar dados pesados por sessão.
*   `src/core/ai_orchestrator.py`: A variável `client_openai = None` é global. Se um usuário na Aba A define um `api_key`, ele cria um cliente OpenAI. Se um usuário na Aba B (que pode ser outro usuário ou o mesmo em outra sessão) faz uma análise com uma chave diferente, ele pode **sobrescrever** a instância `client_openai` que a Aba A estava usando, causando comportamento inesperado.
*   `src/core/pdf_processor.py`: `_sentence_model = None` é outro exemplo de cache global que, embora menos problemático (geralmente se usa o mesmo modelo), segue o mesmo padrão.

**Como isso causa problemas de renderização?**

Imagine este cenário:

1.  **Aba 1** abre a aplicação e inicia a análise de um PDF. Os resultados intermediários são salvos no `_SERVER_SIDE_CACHE[session_id_1]`.
2.  **Aba 2** (mesmo usuário, nova aba) abre a aplicação. Uma nova sessão é criada (`session_id_2`). Ela tem seu próprio cache em `_SERVER_SIDE_CACHE`.
3.  Se a Aba 2 realiza uma ação que modifica um recurso global (como `client_openai`), a Aba 1 pode ser afetada.
4.  Pior: se você tivesse dados importantes em variáveis globais *não isoladas por sessão*, a Aba 2 poderia sobrescrever os dados da Aba 1, levando a uma renderização inconsistente ou a erros quando a Aba 1 tentasse atualizar sua UI com dados que não existem mais ou foram alterados.

### 2. Threads e Recursos Globais

**Problema:** Threads criadas para uma sessão específica podem continuar rodando mesmo que o usuário feche a aba, ou podem interferir com threads de outras sessões se compartilharem recursos globais.

**Exemplo no seu código:**

*   `src/flet_ui/app.py`: A sua thread de renovação de token (`_proactive_token_refresh_loop`) é um exemplo perfeito. Você a armazena em variáveis globais `_token_refresh_thread_instance` e `_token_refresh_thread_stop_event`.
    *   **Cenário de falha:** Se a Aba 1 inicia a thread e o usuário a fecha, o evento `on_disconnect` corretamente sinaliza para a thread parar. Mas e se o usuário abrir a Aba 2 antes da thread da Aba 1 ter parado completamente? A Aba 2 poderia tentar iniciar uma nova thread enquanto a antiga ainda está no processo de finalização, ou poderia tentar interagir com a instância antiga. Sua lógica de `if _token_refresh_thread_instance is None or not _token_refresh_thread_instance.is_alive():` é uma boa proteção contra isso, mas a complexidade aumenta.

### 3. Ciclo de Vida da Conexão Flet

**Problema:** Quando você recarrega uma aba (F5) ou abre uma nova, o cliente Flet (no navegador) estabelece uma **nova conexão WebSocket** com o servidor Python. Para o backend, isso é tratado como um novo cliente se conectando.

1.  **`on_disconnect`:** Quando a aba antiga é fechada ou a conexão é perdida, o evento `on_disconnect` é (eventualmente) disparado para a sessão antiga. Isso limpa recursos, como sinalizar a parada da thread do token.
2.  **`main()`:** A nova conexão inicia uma nova execução da função `main(page)` com uma nova instância de `page`.
3.  **Race Condition:** Pode haver uma "corrida" entre a limpeza da sessão antiga (`on_disconnect`) e a inicialização da nova sessão (`main`). Se a nova sessão tentar acessar um recurso global (como o `_token_refresh_thread_instance`) antes que a limpeza da sessão antiga tenha terminado de modificá-lo, podem ocorrer inconsistências.

**Solução e Boas Práticas (O que fazer a seguir):**

Para mitigar esses problemas, a estratégia é **isolar o estado o máximo possível por sessão**.

1.  **Centralize o Estado na `Page`:** Use `page.session` para dados leves e o `_SERVER_SIDE_CACHE` (com `page.session_id` como chave) para dados pesados. Isso você já está fazendo bem.
2.  **Evite Caches Globais para Recursos de Sessão:** Para recursos como `client_openai`, que dependem de uma `api_key` específica da sessão do usuário, não use uma variável global. Em vez disso, crie a instância dentro da função que a utiliza e passe a chave. Se a criação da instância for cara, armazene-a no cache da sessão do usuário.

    **Exemplo de Correção para `ai_orchestrator.py`:**

    ```python
    # Em src/core/ai_orchestrator.py

    # REMOVA a variável global:
    # client_openai = None

    # DENTRO de analyze_text_with_llm:
    def analyze_text_with_llm(...):
        # ...
        try:
            if provider == "openai":
                # --- INÍCIO DA MODIFICAÇÃO ---
                # Cria a instância do cliente aqui, usando a chave específica da chamada.
                # Não depende mais de um estado global.
                client_openai = OpenAI(api_key=api_key)
                os.environ["OPENAI_API_KEY"] = "" # Limpa a variável de ambiente se não for mais necessária
                # --- FIM DA MODIFICAÇÃO ---

                # O restante do código usa a instância local `client_openai`
                if prompt_name == "PROMPT_UNICO_for_INITIAL_ANALYSIS":
                    # ...
                    response = client_openai.chat.completions.create(...) # Exemplo
                # ...
    ```
    *Nota: Seu código atual em `ai_orchestrator` já parece estar instanciando `OpenAI()` dentro da função, o que é ótimo! Apenas certifique-se de que a variável global `client_openai` seja removida para evitar confusão.*

3.  **Gerencie Threads por Sessão:** Para threads em background, associe-as à sessão do usuário. O `page.run_thread()` do Flet é uma boa maneira de fazer isso para tarefas curtas. Para tarefas de longa duração como o `_proactive_token_refresh_loop`, sua abordagem com uma thread global e um evento de parada é uma solução viável, mas requer uma lógica de bloqueio cuidadosa (como a que você implementou) para garantir que apenas uma instância esteja ativa.

4.  **Limpeza Robusta em `on_disconnect`:** Sua função `on_disconnect` já está no caminho certo. Ela limpa o cache e para a thread. É crucial que essa limpeza seja completa e rápida para liberar os recursos antes que uma nova sessão os solicite.

Em resumo, os problemas de renderização em múltiplas abas quase sempre apontam para um **estado global compartilhado** que não foi devidamente isolado por sessão. A chave é pensar: "Se duas abas abrirem ao mesmo tempo, quais variáveis no meu código Python elas tentarão acessar e modificar simultaneamente?". Qualquer variável que se encaixe nessa descrição é um ponto de atenção.