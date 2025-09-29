
________________________________________________________________________________________________________________________________________________

# INFO: Persistência de Dados

A aplicação utiliza um **modelo híbrido** para persistência de dados, combinando o uso de nuvem (Firebase) com o armazenamento local seguro para diferentes finalidades.

Esta abordagem equilibra a centralização e escalabilidade da nuvem com a segurança e o desempenho do armazenamento local para dados sensíveis e operacionais.

Abaixo está um resumo de como cada tipo de dado é armazenado:

### 1. Armazenamento na Nuvem (Firebase)

O Firebase atua como o backend principal para dados persistentes e compartilhados da aplicação.

*   **Firebase Authentication**:
    *   Gerencia as **contas de usuário** (email, hash de senha, UID, status de verificação).

*   **Firestore (Banco de Dados NoSQL)**:
    *   **Chaves de API dos usuários** (armazenadas de forma criptografada).
    *   **Preferências do usuário** (ex: provedor e modelo LLM padrão).
    *   **Templates de prompts** que podem ser atualizados remotamente.
    *   **Métricas de uso e feedback** para análise de desempenho e precisão da IA.
    *   **Configurações globais da aplicação** (ex: lista de provedores LLM disponíveis).

*   **Cloud Storage**:
    *   **Logs de uso e erros** enviados periodicamente para monitoramento e auditoria centralizada.

### 2. Armazenamento Local (Máquina do Usuário)

O armazenamento local é utilizado para dados sensíveis que garantem a segurança, arquivos operacionais e configurações específicas da máquina.

*   **Keyring (Cofre de Credenciais do Sistema Operacional)**:
    *   Armazena a **chave de criptografia principal (Fernet)**, que é usada para proteger outras credenciais.
    *   Guarda as **credenciais de proxy** (usuário e senha, se o usuário optar por salvar).

*   **Arquivo Criptografado (`%APPDATA%/DocsAnalyzerPF/firebase_service_key.enc`)**:
    *   Armazena a **chave de serviço do Firebase Admin** de forma criptografada. Este arquivo é necessário para operações administrativas (como gerenciamento de usuários no painel Streamlit) e é protegido pela chave principal guardada no Keyring.

*   **Arquivos Temporários**:
    *   **`uploads_temp/`**: Diretório onde os arquivos PDF são temporariamente armazenados durante o upload no modo web, antes de serem processados.
    *   **`assets/temp_docx_exports/`**: Usado para armazenar temporariamente os arquivos `.docx` gerados para download no modo web.

*   **Arquivos de Log**:
    *   **`logs/`**: Cada execução da aplicação gera um arquivo de log local para facilitar a depuração. Este diretório também serve como **backup** para logs que não puderam ser enviados para a nuvem.

*   **Arquivos de Assets e Templates**:
    *   **`assets/`**: Contém recursos da aplicação, como imagens e, crucialmente, os **templates `.docx`** que o usuário pode adicionar para a funcionalidade de exportação.

*   **Banco de Dados Local (SQLite)**:
    *   Para funcionalidades como a persistência do **histórico de conversas** do módulo "Chat com Documentos", será utilizado um banco de dados SQLite local. Esta abordagem garante que o conteúdo das conversas permaneça exclusivamente na máquina do usuário, permitindo o acesso offline e garantindo a privacidade dos dados.

### 3. Armazenamento em Memória (Server-Side Cache)

Além do armazenamento persistente, a aplicação utiliza um cache em memória no lado do servidor (`_SERVER_SIDE_CACHE` em `utils.py`) para dados de sessão que são muito grandes ou computacionalmente caros para serem recriados a cada interação. Este cache é volátil e seu conteúdo é perdido quando a aplicação é encerrada.

*   **Dados de Sessão Pesados:** Armazena temporariamente o texto agregado de múltiplos PDFs, as respostas da IA, e outros objetos de dados grandes para evitar reprocessamentos e lentidão na interface.
*   **Desempenho:** Por estar na memória RAM do servidor, o acesso a esses dados é quase instantâneo, garantindo uma experiência de usuário fluida.
*   **Escalabilidade:** Esta abordagem funciona perfeitamente em um ambiente de servidor único (execução local ou em um único contêiner). Para escalar horizontalmente com múltiplos processos de servidor, este cache precisaria ser substituído por uma solução compartilhada, como Redis.

Em resumo, o Firebase é o repositório central para dados da aplicação, o armazenamento local é crucial para a segurança, operação e persistência de dados do usuário (históricos de chat), e o cache em memória garante o desempenho para operações complexas durante a sessão.

_________________________________________________________________________________________________________________________________________________

# firebase_manager.py:

Diferenças entre Firebase Cloud Storage e Cloud Firestore são:

1.  **Tipo de Dados Armazenados:**
    *   **Storage:** Projetado para armazenar **arquivos grandes e binários** (objetos), como imagens, vídeos, áudios, PDFs, backups, etc. Pense nele como um sistema de arquivos na nuvem.
    *   **Firestore:** É um banco de dados NoSQL para armazenar **dados estruturados em formato JSON-like** (documentos organizados em coleções). Ideal para dados de aplicação, como perfis de usuário, configurações, posts, mensagens, etc.

2.  **Estrutura de Dados:**
    *   **Storage:** Organiza arquivos em "buckets" (como diretórios raiz) e dentro deles você pode ter uma estrutura de pastas para organizar seus arquivos.
    *   **Firestore:** Estrutura hierárquica de `coleções -> documentos -> dados (campos e valores)`. Documentos podem conter subcoleções.

3.  **Consultas (Querying):**
    *   **Storage:** Oferece listagem de arquivos baseada em prefixos (nomes de pastas/arquivos), mas não permite consultas complexas sobre o *conteúdo* dos arquivos. Você baixa o arquivo para processá-lo.
    *   **Firestore:** Permite consultas **poderosas e flexíveis** sobre os dados dentro dos documentos. Você pode filtrar, ordenar e buscar documentos com base nos valores de seus campos, usando indexação.

4.  **Casos de Uso Típicos:**
    *   **Storage:**
        *   Upload e download de arquivos de usuários (fotos de perfil, anexos).
        *   Hospedagem de assets estáticos.
        *   Armazenamento de backups de bancos de dados.
    *   **Firestore:**
        *   Gerenciar dados de usuários (preferências, histórico).
        *   Sincronizar estado da aplicação em tempo real entre clientes.
        *   Armazenar catálogos de produtos, listas de tarefas, conteúdo de blogs.

5.  **Modelo de Preços (Simplificado):**
    *   **Storage:** Custa principalmente com base no volume de dados armazenados, operações (uploads/downloads) e transferência de dados de saída (egress).
    *   **Firestore:** Custa principalmente com base no número de leituras, escritas e exclusões de documentos, além do armazenamento de dados.

**Analogia Simples:**

*   Pense no **Storage** como um armário gigante onde você guarda caixas (arquivos) de diversos tamanhos.
*   Pense no **Firestore** como um fichário altamente organizado, onde cada ficha (documento) contém informações específicas e você pode procurar rapidamente por fichas que atendam a certos critérios.

Ambos são frequentemente usados juntos em uma aplicação. Por exemplo, você pode armazenar os dados de um perfil de usuário no Firestore (nome, email) e a foto de perfil desse usuário no Storage, guardando apenas o link (URL) para a foto no documento do Firestore.

_________________________________________________________________________________________________________________________________________________

# pdf_processor.py:

### Modos de Filtragem de Páginas Relevantes:

O sistema oferece diferentes estratégias (`mode_main_filter`) para selecionar as páginas mais relevantes e menos redundantes de um conjunto de documentos PDF. A quantidade de páginas selecionadas e a agressividade da filtragem podem variar significativamente entre os modos. Todos os modos concluem com um recálculo do score TF-IDF nas páginas selecionadas, ordenando o resultado final por esta relevância recalculada.

**Ordenado do Geralmente Mais Agressivo (Menos Páginas Selecionadas) para o Mais Permissivo (Mais Páginas Selecionadas):**

1.  **`get_pages_among_similars_graphs` (Representante de Clusters Completos de Redundância):**
    *   **Como funciona:** Constrói um grafo onde páginas são nós e similaridade acima de um limiar forma uma aresta. Identifica todos os "clusters de redundância" (componentes conectados), que são grupos onde todas as páginas são direta ou indiretamente similares entre si. Um único representante é escolhido para cada um desses clusters completos (ex: o com mais palavras ou maior TF-IDF inicial no grupo).
    *   **Comportamento Esperado:** Tende a ser o **mais agressivo** na remoção de redundâncias, resultando no menor número de páginas selecionadas, pois agrupa extensivamente páginas relacionadas.
    *   **Ideal para:** Máxima compressão do documento, mantendo apenas uma versão de cada conjunto de conteúdo interconectado.

2.  **`get_pages_among_similars_matrix` (Representante de Vizinhos Diretos - Processamento Ordenado):**
    *   **Como funciona:** Para cada página, identifica suas "vizinhas" diretas (outras páginas diretamente similares a ela acima de um limiar). O sistema então itera pelas páginas na ordem original do documento. Quando uma página não processada é encontrada, ela e todas as suas vizinhas diretas (identificadas no passo anterior) formam um grupo. Um representante é escolhido desse grupo, e todas as páginas desse grupo são marcadas como processadas.
    *   **Comportamento Esperado:** **Agressividade alta a moderada.** Mais permissivo que `_graphs` porque não considera a transitividade total ao formar os grupos iniciais para seleção, mas o processamento ordenado e a marcação de todo o grupo de vizinhos como processado ainda promove uma boa desduplicação.
    *   **Ideal para:** Uma desduplicação robusta que respeita a ordem original das páginas ao iniciar a formação de grupos.

3.  **`get_pages_by_tfidf_initial` (Relevância Individual com Desduplicação Iterativa):**
    *   **Como funciona:** Primeiro, todas as páginas são pontuadas individualmente usando TF-IDF. As páginas são então processadas em ordem decrescente dessa pontuação. Uma página é selecionada se não for excessivamente similar a páginas *mais relevantes* já escolhidas.
    *   **Comportamento Esperado:** **Agressividade moderada.** O número de páginas selecionadas pode ser similar ou um pouco diferente de `_matrix`, dependendo da distribuição de scores TF-IDF e da similaridade entre páginas de alta pontuação.
    *   **Ideal para:** Priorizar páginas com conteúdo único e estatisticamente importante, desduplicando em relação ao que já foi considerado mais relevante.

4.  **`get_pages_among_similars_groups` (Representante de Grupos Formados Iterativamente - Processamento Ordenado):**
    *   **Como funciona:** Itera pelas páginas na ordem original. Se uma página não foi agrupada anteriormente, ela inicia um novo grupo. Este grupo inclui a página inicial e quaisquer de suas vizinhas diretas que também não tenham sido agrupadas por páginas anteriores. Um representante é escolhido para cada grupo assim formado, e os membros do grupo são marcados como processados.
    *   **Comportamento Esperado:** Tende a ser **mais permissivo** que `_graphs` e `_matrix`. A forma como os grupos são "reivindicados" sequencialmente pode levar à formação de mais grupos distintos (e, portanto, mais representantes) se as conexões de similaridade não forem todas capturadas pelo primeiro "líder de grupo" encontrado.
    *   **Ideal para:** Uma abordagem de agrupamento que é sensível à ordem e pode permitir que mais "variantes" de um tema sobrevivam se não forem imediatamente agrupadas por uma página processada anteriormente.

**Nota Importante:**
*   O parâmetro `similarity_threshold` (limiar de similaridade) tem um impacto crucial em todos os modos. Limiares mais baixos (ex: 0.80) são mais agressivos (menos páginas), enquanto limiares mais altos (ex: 0.90) são mais permissivos (mais páginas).
*   O tipo de vetorização (TF-IDF vs. Embeddings) também influencia. Geralmente, limiares de similaridade mais baixos podem ser apropriados para TF-IDF em comparação com embeddings para alcançar um nível semelhante de distinção conceitual.
*   A escolha do `mode_filter_similar` (`'bigger_content'` ou `'higher_initial_score'`) define qual página é escolhida como representante de um grupo, afetando a *qualidade* da seleção, mas menos a *quantidade* do que os fatores acima.

---

