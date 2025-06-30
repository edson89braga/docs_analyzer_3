# IA Assistente - PF/SP

> Uma plataforma de software inteligente, desenvolvida em Python e Flet, para servir como um hub de agentes de IA e assistentes especializados, otimizando rotinas de análise e processos investigativos da Polícia Federal.

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Python Version](https://img.shields.io/badge/python-3.13-blue.svg)
![License](https://img.shields.io/badge/license-Proprietário%20/%20Restrito-red)
![App Version](https://img.shields.io/badge/version-0.2.0-informational)

## 📖 Visão Geral

O **IA Assistente - PF/SP** é uma ferramenta de suporte à decisão projetada para acelerar o fluxo de trabalho de analistas e agentes. A plataforma centraliza múltiplos agentes de IA, cada um especializado em uma tarefa, começando com o módulo de **Análise de Documentos**, que automatiza a extração e estruturação de dados de Notícias-Crime e outros documentos jurídicos.

O objetivo principal é reduzir o tempo de análise preliminar de documentos de horas para minutos, padronizando a extração de dados-chave e fornecendo um resumo coeso e pronto para revisão humana. Futuros módulos expandirão as capacidades da plataforma para outras áreas de investigação e gestão de conhecimento.

### Módulos Atuais e Futuros
*   **Análise de Documentos (Módulo Inicial):** Extração de dados estruturados de PDFs.
*   **Chat com PDF (Em desenvolvimento):** Interação conversacional com documentos para obter insights específicos.
*   **Banco de Pareceres (Planejado):** Agente para busca e consulta em bases de conhecimento internas.
*   **Outros Agentes Especializados (Roadmap):** Módulos para correições, roteiros de investigação, e mais.

## 🛠️ Tecnologias Utilizadas

Este projeto é construído com um conjunto de tecnologias modernas focadas em performance e segurança.

*   **Interface e Aplicação:**
    *   [Flet](https://flet.dev/) (para a interface web/desktop em Python)
*   **Backend e Core:**
    *   Python 3.13
    *   Poetry (Gerenciamento de dependências)
*   **IA e Processamento de Linguagem:**
    *   LangChain & LangChain-OpenAI
    *   OpenAI API
    *   Sentence-Transformers (para embeddings)
    *   NLTK
*   **Processamento de Dados e Documentos:**
    *   PyMuPDF (fitz) & pdfplumber
    *   scikit-learn & NumPy (para TF-IDF e análise de similaridade)
*   **Serviços de Nuvem e Autenticação:**
    *   Firebase (Authentication, Firestore, Cloud Storage)
*   **Segurança e Criptografia:**
    *   Cryptography (para criptografia de chaves)
    *   Keyring (para armazenamento seguro de credenciais no SO)

## ⚙️ Configuração do Ambiente de Desenvolvimento

Siga os passos abaixo para configurar e executar o projeto localmente.

### Pré-requisitos
*   **Python 3.13**
*   **Poetry** instalado (consulte a [documentação oficial](https://python-poetry.org/docs/#installation))
*   Acesso ao projeto no **Firebase**.

### 1. Clonar o Repositório
```bash
git clone <URL_DO_REPOSITORIO>
cd ia-assistente-pfsp # ou outro nome de diretório
```

### 2. Configurar o Firebase
A aplicação utiliza Firebase para autenticação e armazenamento de dados.

1.  Acesse o [Console do Firebase](https://console.firebase.google.com/).
2.  Crie um novo projeto ou selecione um existente.
3.  No seu projeto, ative os seguintes serviços:
    *   **Authentication**: Habilite o provedor "E-mail/senha". Nos domínios autorizados, adicione `pf.gov.br` e `dpf.gov.br`.
    *   **Firestore Database**: Crie um banco de dados (pode iniciar em modo de teste e depois ajustar as regras).
    *   **Storage**: Crie um bucket de armazenamento.
4.  Para o setup inicial de credenciais de **administrador** (uma única vez, pelo desenvolvedor principal), é necessário o arquivo de chave de serviço (`firebase_service_key.json`). Siga as instruções do `credentials_manager.py` para criptografar e salvar essa chave. 

### 3. Configurar Variáveis de Ambiente
Crie um arquivo chamado `.env` na raiz do projeto e adicione a seguinte variável. Ela é necessária para a autenticação de usuários na interface.

```env
# Obtenha esta chave em: Configurações do Projeto > Geral > Seus apps > Configuração do SDK
FIREBASE_WEB_API_KEY="AIzaSy...SUA_CHAVE_AQUI"
```

### 4. Instalar Dependências
Com o Poetry instalado, execute o seguinte comando na raiz do projeto:
```bash
poetry install
```
Isso criará um ambiente virtual e instalará todas as dependências listadas no `pyproject.toml`.

## 🚀 Executando a Aplicação
Após a configuração, a aplicação (que roda como um app web em `localhost`) pode ser iniciada com o seguinte comando:

```bash
flet run src/flet_ui/app.py
```
A interface será aberta no seu navegador padrão. Na primeira vez, você precisará criar uma conta com um e-mail de domínio permitido.

## 🗂️ Estrutura do Projeto
O código está organizado na pasta `src/` com a seguinte estrutura modular:
```
src/
├── core/                   # Módulos centrais da lógica de negócio
│   ├── ai_orchestrator.py  # Orquestra as chamadas para LLMs
│   ├── doc_generator.py    # Gera arquivos .docx
│   └── pdf_processor.py    # Extrai e processa texto de PDFs
├── flet_ui/                # Componentes da interface gráfica com Flet
│   ├── views/              # Módulos para cada "página" ou "view" da aplicação
│   ├── app.py              # Ponto de entrada principal da aplicação Flet
│   ├── components.py       # Componentes de UI reutilizáveis (cards, botões)
│   ├── layout.py           # Layouts reutilizáveis (AppBar, NavigationRail)
│   └── router.py           # Gerenciador de rotas da UI
├── logger/                 # Configuração de logging (local e nuvem)
│   ├── cloud_logger_handler.py
│   └── logger.py
├── security/               # Módulos relacionados à segurança
│   └── anonymizer.py       # (Futuro) Anonimização de dados
├── services/               # Clientes para serviços externos
│   ├── credentials_manager.py # Gerencia chaves de criptografia e credenciais
│   ├── firebase_client.py     # Cliente para Auth/Firestore/Storage com token de usuário
│   └── firebase_manager.py    # Gerenciador com credenciais de Admin (backend)
├── app_cache.py            # Cache simples em memória para a aplicação
├── config_manager.py       # Gerenciamento de configurações (ex: proxy)
├── settings.py             # Configurações globais, constantes e paths
└── utils.py                # Funções utilitárias diversas
```

## 🧪 Testes
A estratégia de testes para este projeto utiliza `pytest`. Atualmente, a cobertura de testes está em desenvolvimento. Para executar os testes existentes:
```bash
poetry run pytest --cov=src
```
## 🤝 Como Contribuir
Contribuições para melhorar o **IA Assistente** são bem-vindas. Por favor, siga os passos:

1.  **Fork** o repositório.
2.  Crie uma nova branch para sua feature: `git checkout -b feature/minha-nova-feature`.
3.  Faça suas alterações e commite: `git commit -am 'Adiciona nova feature'`.
4.  Envie para a branch: `git push origin feature/minha-nova-feature`.
5.  Abra um **Pull Request**.

## 🗺️ Roadmap e Próximos Passos
-   [ ] **Desenvolvimento de Testes:** Implementar suíte de testes unitários e de integração para os módulos `core` e `services`.
-   [ ] **Módulo de Chat com PDF:** Finalizar a funcionalidade de interação conversacional com documentos.
-   [ ] **Módulo de Banco de Pareceres:** Desenvolver o agente de IA para busca semântica em bases de conhecimento.
-   [ ] **Módulo de Administração:** Criar uma interface web para gerenciamento de usuários, configurações e logs.
-   [ ] **Migração de Serviços:** Adaptar a arquitetura para permitir a substituição do Firebase por serviços de nuvem institucionais.
-   [ ] **CI/CD:** Configurar um pipeline de Integração e Entrega Contínua para automatizar testes e builds.

## 📄 Licença
Este projeto é distribuído como software **Proprietário / Restrito**. O uso, modificação e distribuição são permitidos apenas sob autorização expressa da instituição.