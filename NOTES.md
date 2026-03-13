# 📋 RELATÓRIO DE STATUS DO PROJETO
**Sistema:** ÓPERA (IA Assistente)
**Assunto:** Implantação e Hospedagem em Ambiente Corporativo (VM Linux PF)
**Data:** Março de 2026

## 1. Objetivo e Contexto
Este relatório documenta a transição bem-sucedida do sistema ÓPERA de um ambiente de execução estritamente local (Desktop/Windows) para um ambiente de servidor (Máquina Virtual Linux) na infraestrutura da Polícia Federal. O objetivo central foi disponibilizar a ferramenta em arquitetura web, permitindo acesso multi-usuário simultâneo.

## 2. Restrições de Infraestrutura e Estratégia de "Deploy Offline"
Durante o processo de conteinerização com Docker, identificamos restrições rigorosas de rede e proxy no ambiente corporativo, que impediam a comunicação direta do Docker daemon com repositórios externos (como Docker Hub e PyPI) para o download de imagens e dependências estruturais.

Para contornar esse bloqueio de forma segura e aderente às políticas da instituição, adotamos a técnica de **Deploy Offline**:
* **Construção Isolada:** O *build* completo das imagens Docker é realizado em um computador de desenvolvimento externo (sem restrições de proxy).
* **Homologação:** As imagens são exaustivamente testadas localmente nesse ambiente de origem.
* **Exportação e Transferência:** Uma vez validadas, as imagens são convertidas em arquivos compactados (`.tar`) usando o comando `docker save` e transferidas via SSH/SCP para a VM corporativa.
* **Carregamento (Load):** Na VM, o sistema é instanciado a partir dos arquivos locais (`docker load`), sem qualquer necessidade de requisição à internet.

## 3. Arquitetura de Serviços Instanciados
A aplicação foi dividida em microsserviços rodando simultaneamente via `docker-compose`:

1. **`opera-app` (Frontend Principal):** Aplicação baseada no framework Flet, hospedada como serviço web, responsável pela interface com os usuários, roteamento e interação com os agentes de IA.
2. **`ml-engine` (Motor de Machine Learning):** API em FastAPI dedicada à geração de embeddings (vetorização de textos). Para viabilizar a portabilidade dos arquivos `.tar`, a imagem foi otimizada para utilizar uma versão do modelo PyTorch estritamente baseada em CPU (`torch==2.10.0+cpu`), removendo dependências massivas da NVIDIA/CUDA e reduzindo o peso do container em vários gigabytes.
3. **`opera-admin` (Painel Administrativo):** Serviço rodando na biblioteca Streamlit, reaproveitando a imagem base do `opera-app`, mas focado nos scripts da pasta `admin_py` para gestão de prompts, logs, provedores LLM e monitoramento.

## 4. Pipeline de Atualização Contínua (Agilidade via *Bind Mounts*)
Para evitar a necessidade operacional de realizar o tráfego de gigabytes de arquivos `.tar` a cada pequena correção ou melhoria no código base, o ambiente foi configurado com **Bind Mounts** (mapeamento de diretórios entre a VM hospedeira e os contêineres).

* **Atualizações de Código-Fonte:** Alterações na regra de negócio (arquivos `.py` no diretório `SOURCE` ou `admin_py`) são simplesmente transferidas para a VM (via WinSCP ou `scp`) e aplicadas instantaneamente através de um reinício rápido dos contêineres (`docker-compose restart`).
* **Rebuild Completo:** O processo moroso de geração de novos arquivos `.tar` no ambiente de desenvolvimento ficou reservado **apenas** para situações que exijam modificações estruturais, como a inclusão de novas bibliotecas (atualização de `requirements.txt` ou `pyproject.toml`) ou dependências de sistema operacional.
* **Gestão de Dados:** Pastas dinâmicas como `logs`, `uploads_temp` e `assets` também foram mapeadas para visualização e manuseio direto no sistema de arquivos da VM.

## 5. Refatoração e Preparação Multi-Tenant
Previamente ao deploy, todo o código do ÓPERA foi submetido a uma profunda refatoração visando o isolamento de concorrência. Foram corrigidos vazamentos de estado global, garantindo que uploads, variáveis de sessão, processamento de documentos e requisições a APIs de linguagem ocorram em threads e contextos isolados por usuário.

Apesar dessa adaptação profunda para o ambiente web multi-usuário, a base de código manteve sua **retrocompatibilidade**. A aplicação ainda pode ser executada de forma autônoma (standalone) no ambiente local do usuário, podendo ser compilada e distribuída como executável nativo do Windows através de ferramentas como `cx_Freeze` ou `PyInstaller`.

## 6. Próximos Passos
Toda a infraestrutura lógica e a refatoração foram amplamente testadas no ambiente Docker do computador de desenvolvimento. O atual estágio requer agora a **bateria de testes operacionais finais dentro do ambiente hospedado da VM PF**, validando as permissões de gravação, estabilidade sob concorrência real e o fluxo fim-a-fim da geração de análises.

