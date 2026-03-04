# ÓPERA - IA Assistente

**O**perador de **P**rocessos e **R**espostas **A**utomatizadas: Uma plataforma de baseada em inteligência artifical, desenvolvida em Python, para servir como um hub de agentes de IA e assistentes especializados, otimizando rotinas de análise e processos investigativos da Polícia Federal.

## 📖 Visão Geral

![Tela_inicial](https://github.com/edson89braga/docs_analyzer_3/blob/master/docs/PrintScreens%20Telas/v0.5/1-tela-home.png)

O **ÓPERA - IA Assistente** é uma ferramenta de suporte à decisão projetada para acelerar o fluxo de trabalho de analistas e agentes. A plataforma centraliza múltiplos agentes de IA, cada um especializado em uma tarefa, com foco em segurança, modularidade e eficiência.

O objetivo principal é reduzir o tempo de análise preliminar de documentos de horas para minutos, padronizando a extração de dados-chave, fornecendo resumos coesos e permitindo uma interação conversacional inteligente com o conteúdo processado.

### Módulos Atuais
*   **Análise de Documentos:** Automatiza a extração, estruturação e sumarização de informações de Notícias-Crime e outros documentos jurídicos em formato PDF.
*   **Chat com Documentos:** Permite uma interação conversacional com o conteúdo dos documentos carregados, utilizando amplo contexto para obter respostas precisas e insights específicos.

## 🏛️ Arquitetura do Sistema

A plataforma possui uma arquitetura desacoplada, composta por três componentes principais:

1.  **Aplicação Principal (Frontend/UI):** Desenvolvida com **Flet**, é o ponto de entrada para o usuário (`run.py`). Ela gerencia a interface, o estado da sessão e orquestra a comunicação com os outros componentes. Roda como uma aplicação web local no navegador do usuário.
2.  **Motor de ML (Serviço Local):** Um servidor **FastAPI** (`ml_engine/engine.exe`) que expõe endpoints para tarefas de Machine Learning pesadas, como a geração de embeddings de texto. A aplicação principal gerencia o ciclo de vida (início/fim) deste serviço, que roda em segundo plano.
   <br>Repositório do engine: [Link](https://github.com/edson89braga/ml_engine)
4.  **Painel de Administração (Dashboard):** Uma aplicação **Streamlit** (`run_admin_streamlit.py`) para administradores, permitindo o monitoramento de métricas de uso, visualização de logs, gerenciamento de usuários e configuração de prompts e provedores LLM.

## 🏛️ Arquitetura do Agente de Análise de Documentos

O módulo inicial, "Agente Assistente de Autuação", foi projetado como um pipeline modular que executa um ciclo completo de análise de documentos, desde o recebimento de arquivos PDF até a geração de um documento conclusivo. A arquitetura é uma referência útil para a construção de novos agentes no "Hub de Agentes de IA".

![Print_tela_nc_analyze_1](https://github.com/edson89braga/docs_analyzer_3/blob/master/docs/PrintScreens%20Telas/v0.5/2-tela-nc-analyze.png)

![Print_tela_nc_analyze_2](https://github.com/edson89braga/docs_analyzer_3/blob/master/docs/PrintScreens%20Telas/v0.2/6-llm1.jpg)

O núcleo da lógica do agente pode ser entendido em quatro etapas sequenciais:

### 1. Pré-processamento de Entrada (`src/core/pdf_processor.py`)

Este módulo atua como o "funil de entrada" do agente, recebendo um ou mais arquivos PDF e extraindo deles um texto otimizado e relevante para a análise.

*   **Extração de Texto:** Utiliza bibliotecas como **PyMuPDF (fitz)** para extrair o conteúdo bruto de todas as páginas.
*   **Filtragem e Classificação:** Aplica técnicas de **TF-IDF** e **embeddings de similaridade** (via Sentence Transformers) para identificar e classificar as páginas mais relevantes, descartando conteúdo repetitivo ou de baixo valor informativo (capas, páginas de assinaturas, etc.).
*   **Agregação e Otimização:** Agrupa o texto das páginas selecionadas, garantindo que o conteúdo final não exceda o limite de tokens do modelo de linguagem (LLM). Isso otimiza custos e a qualidade da resposta ao enviar apenas a informação mais densa para análise.

### 2. Formulação da Tarefa (`src/core/prompts.py`)

Este módulo gerencia a montagem dos prompts e o processamento da resposta da IA. O conteúdo textual dos prompts é carregado dinamicamente do **Firestore** (com um fallback local em `admin_py/repo_prompts.py`), garantindo flexibilidade e gerenciamento centralizado.

*   **Construção Dinâmica de Prompts:** Contém a lógica para montar pipelines de prompts complexos a partir de componentes base. Suporta tanto um prompt único e geral quanto uma abordagem segmentada, projetada para otimizar custos e performance em LLMs que suportam cache de contexto.
*   **Definição da Estrutura de Saída:** Utiliza classes **Pydantic** (ex: `formatted_initial_analysis`) para definir o formato JSON exato esperado como resposta da LLM, garantindo consistência e facilitando a validação.
*   **Revisão e Normalização da Resposta:** Fornece funções de pós-processamento (`normalizing_function`, `review_function`) que são aplicadas à resposta JSON recebida. Essas funções validam, corrigem e enriquecem os dados (ex: normalizam siglas de UF, validam municípios, aplicam regras de negócio) antes de apresentar o resultado final.

### 3. Orquestração da IA (`src/core/ai_orchestrator.py`)

Este é o orquestrador central que gerencia a comunicação com a API do modelo de linguagem.

*   **Integração com LLM:** Atualmente, integra-se com a **API da OpenAI**. A arquitetura é projetada para ser extensível a outros provedores.
*   **Execução da Análise:** Recebe o texto otimizado do `pdf_processor` e o prompt final do `prompts.py`, envia a requisição para a API do LLM e trata a resposta.
*   **Gerenciamento de Custos:** Inclui funcionalidades para calcular os custos estimados da análise com base no uso de tokens de entrada, saída e cache.

### 4. Pós-processamento da Resposta (`src/core/doc_generator.py`)

Este módulo lida com a saída da análise, transformando os dados estruturados em um formato final para o usuário.

*   **Geração de Documentos:** Converte a resposta JSON estruturada em um arquivo **Word (.docx)**.
*   **Exportação via Templates:** Suporta o preenchimento de templates `.docx` customizados. O usuário pode carregar um modelo com placeholders (ex: `<resumo_fato>`), e o módulo os substitui automaticamente pelos dados correspondentes.

### Módulos de Suporte Relevantes

*   **Gerenciamento de Credenciais (`src/services/credentials_manager.py`):** Implementa uma abordagem de segurança robusta para o armazenamento de chaves na máquina do usuário, utilizando **Keyring** para a chave de criptografia principal e criptografia **Fernet** para os arquivos de credenciais.
*   **Fluxo de Feedback do Usuário (`src/flet_ui/views/nc_analyze_view.py`):** Contém uma implementação de referência para coletar feedback sobre a precisão da IA. O sistema compara a resposta original da LLM com a versão final editada pelo usuário, calcula a similaridade textual (**ROUGE-L**) e registra esses dados como métricas para aprimoramento contínuo do modelo.

## 🏛️ Arquitetura do Módulo 'Chat com Documentos'

O módulo "Chat com Documentos" permite uma interação conversacional com o conteúdo de um ou mais arquivos PDF. Sua arquitetura foi projetada para ser eficiente, configurável e responsiva, separando a lógica da interface do usuário da orquestração da IA.

![Print_tela_chat_docs_1](https://github.com/edson89braga/docs_analyzer_3/blob/master/docs/PrintScreens%20Telas/v0.5/3-tela-chat-docs.png)

![Print_tela_chat_docs_2](https://github.com/edson89braga/docs_analyzer_3/blob/master/docs/PrintScreens%20Telas/v0.5/4-tela-chat-docs-2.png)

### Fluxo de Trabalho do Usuário e Componentes

O fluxo de trabalho do agente de chat é dividido em três etapas principais, cada uma gerenciada por componentes específicos:

**1. Carregamento e Preparação do Contexto (`chat_view.py`)**

O usuário inicia o processo carregando os documentos. A partir daí, ele tem duas opções para preparar o contexto que será utilizado pela IA:

*   **Extrair Texto (Bruto):** Ao clicar em "Extrair Texto(s)" (`_handle_process_extract`), o sistema executa a extração simples e concatena o conteúdo de **todas as páginas** de todos os documentos. Este é o modo de "amplo contexto" não otimizado, ideal para documentos curtos ou quando cada página é crucial.
*   **Otimizar Conteúdo:** Ao clicar em "Otimizar Conteúdo" (`_handle_optimize_click`), o sistema ativa o pipeline de pré-processamento avançado. Ele reutiliza o `PDFDocumentAnalyzer` (do módulo `core/pdf_processor.py`) para:
    1.  Extrair o texto de todos os arquivos.
    2.  Analisar a relevância e a similaridade entre as páginas.
    3.  Filtrar e descartar páginas irrelevantes ou redundantes.
    4.  Agregar o texto das páginas mais importantes em um contexto final otimizado.

O resultado de qualquer um dos processos (bruto ou otimizado) é armazenado na sessão do usuário (`KEY_SESSION_CHAT_DOCUMENT_CONTEXT`) e fica pronto para ser usado nas conversas.

**2. Orquestração da Conversa (`chat_llm_orchestrator.py`)**

Quando o usuário envia uma mensagem (`_handle_send_message`), a orquestração da comunicação com a IA é delegada ao `ChatLLMOrchestrator`.

*   **Construção do Payload:** O orquestrador monta o payload completo para a API, que inclui:
1.  O **Prompt de Sistema** (definido pelo usuário como "Estrito", "Flexível" ou "Customizado").
    2.  O **Contexto do Documento** (preparado na etapa anterior).
    3.  O **Histórico da Conversa** atual.
    4.  A **Nova Pergunta** do usuário.
*   **Interação com a API:** Utiliza a API `client.responses.create` da OpenAI, que é mais moderna e eficiente.
*   **Gerenciamento de Cache:** A implementação utiliza os parâmetros `previous_response_id` e `store=True`. Isso permite que a API da OpenAI gerencie o cache de contexto do lado do servidor, otimizando significativamente o custo e a velocidade em conversas longas, pois o contexto do documento não precisa ser reenviado a cada nova pergunta.

**3. Gerenciamento da Interface e Estado (`chat_view.py`)**

A classe `ChatViewContent` é responsável por toda a experiência do usuário, garantindo uma interface fluida e a persistência do estado.

*   **Interface Responsiva:** A chamada para a IA é executada em uma **thread separada** (`_handle_ai_response_thread`). Isso evita que a interface do usuário congele enquanto a resposta está sendo gerada. Uma referência fraca (`weakref`) à instância da view é passada para a thread, garantindo que as atualizações da UI só ocorram se a view ainda estiver ativa.
*   **Exibição de Mensagens:** A resposta da IA é exibida progressivamente na tela (simulando streaming), atualizando a bolha de mensagem à medida que os "chunks" de texto são recebidos da thread.
*   **Gerenciamento de Estado:** O histórico da conversa, métricas de uso e o contexto dos arquivos são salvos na sessão do Flet e no cache do servidor (`user_cache`). Isso permite que o estado da conversa seja restaurado se o usuário navegar para outra tela e depois retornar (`did_mount`).

#### Principais Funcionalidades Implementadas

*   **Contexto Otimizado ou Bruto:** O usuário pode escolher entre usar o texto completo dos documentos ou uma versão otimizada e filtrada, equilibrando custo e abrangência.
*   **Orquestração Dedicada:** Um orquestrador (`ChatLLMOrchestrator`) específico para o chat, que utiliza as funcionalidades mais recentes da API da OpenAI, incluindo o cache de respostas.
*   **Gerenciamento de Estado Persistente:** A sessão de chat do usuário é mantida durante a navegação na aplicação.
*   **Configuração Flexível:** Através do painel de configurações (`ChatSettingsDrawer`), o usuário pode alterar o modelo de LLM, seus parâmetros (temperatura, etc.) e o comportamento do assistente através de prompts de sistema ("Estrito", "Flexível" ou "Personalizado").
*   **Métricas Detalhadas:** Um diálogo de métricas fornece um detalhamento completo do consumo de tokens (entrada, saída, cache) e dos custos estimados por requisição e por sessão.
*   **Ações de Mensagem:** O usuário pode editar, excluir, copiar ou "retomar" a conversa a partir de qualquer ponto do histórico, oferecendo total controle sobre o fluxo da interação; além de opção de regeneração da última resposta.

## 🛠️ Tecnologias Utilizadas

*   **Interface e Aplicação Principal:**
    *   Python 3.13
    *   Flet (para a interface web/desktop em Python)

*   **IA e Processamento de Linguagem:**
    *   OpenAI API (integração direta via SDK)
    *   Sentence-Transformers (para embeddings de texto)
    *   spaCy (planejado para NER e anonimização)
    *   NLTK & Tiktoken (para processamento e tokenização de texto)

*   **Motor de ML (Serviço Local):**
    *   FastAPI (para servir o modelo de embedding como uma API REST local)
    *   PyTorch / Transformers

*   **Processamento de Dados e Documentos:**
    *   PyMuPDF (fitz)
    *   scikit-learn & NumPy (para TF-IDF e análise de similaridade)

*   **Backend, Banco de Dados e Autenticação:**
    *   Firebase (Authentication, Firestore, Cloud Storage)
    *   SQLite (para armazenamento local de configurações do usuário)

*   **Dashboard de Administração:**
    *   Streamlit
    *   Pandas & Plotly (para visualização de dados)

*   **Segurança e Criptografia:**
    *   Cryptography (para criptografia de chaves Fernet)
    *   Keyring (para armazenamento seguro de credenciais no SO)

*   **Empacotamento e Distribuição:**
    *   Poetry (Gerenciamento de dependências)
    *   PyInstaller (para compilação em executáveis)

## ⚙️ Configuração do Ambiente de Desenvolvimento

### Pré-requisitos
*   **Python 3.13**
*   **Poetry** instalado (consulte a [documentação oficial](https://python-poetry.org/docs/#installation))
*   Acesso ao projeto no **Firebase**.
*   (Opcional, para futura fase de anonimização) Baixar o modelo de linguagem para spaCy:
    ```bash
    python -m spacy download pt_core_news_lg
    ```

### 1. Clonar o Repositório
```bash
git clone https://github.com/edson89braga/docs_analyzer_3
cd ia-assistente
```

### 2. Configurar o Firebase
A aplicação utiliza Firebase para autenticação e armazenamento de dados.

1.  Acesse o [Console do Firebase](https://console.firebase.google.com/).
2.  Crie um novo projeto ou selecione um existente.
3.  No seu projeto, ative:
    *   **Authentication**: Habilite o provedor "E-mail/senha". Nos domínios autorizados, adicione `pf.gov.br` e `dpf.gov.br`.
    *   **Firestore Database**: Crie um banco de dados.
    *   **Storage**: Crie um bucket de armazenamento.
4.  Para o setup de credenciais de **administrador** (necessário para o Dashboard Admin e setup inicial), obtenha o arquivo de chave de serviço (`firebase_service_key.json`) e siga as instruções da aplicação na primeira execução para criptografá-lo e salvá-lo localmente via `credentials_manager.py`.

### 3. Configurar Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto e adicione a chave da API Web do Firebase.

```env
# Obtenha esta chave em: Configurações do Projeto > Geral > Seus apps > Configuração do SDK
FIREBASE_WEB_API_KEY="AIzaSy...SUA_CHAVE_AQUI"
```

### 4. Instalar Dependências
Com o Poetry, execute na raiz do projeto:
```bash
poetry install
```

## 🚀 Executando a Aplicação

### Aplicação Principal
Para iniciar a interface principal do usuário, execute:```bash
python run.py
```
A aplicação será aberta no seu navegador padrão no endereço `http://localhost:8550`. O `run.py` gerenciará automaticamente o serviço do Motor de ML.

### Painel de Administração
Para iniciar o dashboard de administração (requer credenciais de admin configuradas), execute em um terminal separado:
```bash
streamlit run run_admin_streamlit.py
```

## 🗂️ Estrutura do Projeto
```
.
├── ml_engine/                # Código-fonte e executável do Motor de ML (FastAPI)
├── release_info/             # Arquivos de configuração para o atualizador automático
├── SOURCE/
│   ├── core/                 # Módulos centrais da lógica de negócio (processamento, IA)
│   ├── flet_ui/              # Componentes da interface gráfica com Flet
│   │   ├── components/       # Componentes de UI reutilizáveis (cards, diálogos)
│   │   └── views/            # Módulos para cada "página" da aplicação
│   ├── logger/               # Configuração de logging (local e nuvem)
│   ├── security/             # Módulos de segurança (anonimização)
│   ├── services/             # Clientes para serviços externos (Firebase, Motor de ML, etc.)
│   ├── app_cache.py          # Cache em memória para a aplicação
│   ├── config_manager.py     # Gerenciamento de configurações (ex: proxy)
│   ├── settings.py           # Configurações globais, constantes e paths
│   └── utils.py              # Funções utilitárias diversas
├── admin_py/                 # Lógica do backend para o painel de administração Streamlit
├── run.py                    # Ponto de entrada principal da aplicação Flet
├── run_admin_streamlit.py    # Ponto de entrada do painel de administração
├── updater.py                # Script do atualizador automático
└── pyproject.toml            # Definições do projeto e dependências (Poetry)
```

## 🧪 Testes
A estratégia de testes utiliza `pytest`. Para executar os testes existentes e verificar a cobertura de código:
```bash
poetry run pytest --cov=src
```

## 🤝 Como Contribuir
Contribuições são bem-vindas. Por favor, siga os passos:

1.  **Fork** o repositório.
2.  Crie uma nova branch: `git checkout -b feature/minha-nova-feature`.
3.  Faça suas alterações e commite: `git commit -am 'Adiciona nova feature'`.
4.  Envie para a branch: `git push origin feature/minha-nova-feature`.
5.  Abra um **Pull Request**.

## 🗺️ Roadmap e Próximos Passos
-   [ ] **Fase 3.2 (RAG e Interação Avançada):** Implementar *Retrieval-Augmented Generation* (RAG) para otimizar o chat com documentos grandes, utilizando LlamaIndex e sumarização de conteúdo com grafos.
-   [ ] **Fase 4 (Segurança e Atualizações):** Implementar o módulo de anonimização de dados sensíveis (NER com spaCy) antes do envio para APIs externas.
-   [ ] **Fase 5 e 6 (Integrações e Offline):** Criar uma API para integração com sistemas externos (RPA) e adicionar suporte a LLMs que rodam localmente (Ollama, Llama.cpp).
-   [ ] **Melhorias Contínuas:** Expandir a suíte de testes, aprimorar o dashboard de administração e refinar a experiência do usuário com base no feedback.

## 📄 Licença
Este projeto é distribuído como software **Proprietário / Restrito**. O uso, modificação e distribuição são permitidos apenas sob autorização expressa da instituição.
