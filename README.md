# ÓPERA - IA Assistente

**O**perador de **P**rocessos e **R**espostas **A**utomatizadas: Uma plataforma de baseada em inteligência artifical, desenvolvida em Python, para servir como um hub de agentes de IA e assistentes especializados, otimizando rotinas de análise e processos investigativos da Polícia Federal.

---

## Contexto

Este projeto é uma reformulação completa de um sistema legado que operava sem LangChain e expunha uma interface MVP em [Flet](https://flet.dev). A reescrita abandona a interface desktop e refoca o sistema como um núcleo de processamento headless, projetado para futura exposição via API REST (FastAPI) e interface React.

As principais mudanças arquiteturais em relação ao legado:

- Substituição da orquestração LLM artesanal por **LangChain modernizado**
- Substituição da extração vetorial antiga por pipeline **PyMuPDF + Chonkie**
- Similaridade e deduplicação baseadas em **TF-IDF lexical** como estratégia primária (ver decisão abaixo)
- ML Engine separado (Sentence Transformers/PyTorch) disponível para embeddings semânticos, mas não utilizado no escopo atual de análise de notícias-crime
- Schemas de saída estruturados com **Pydantic v2**
- Infraestrutura de testes com **pytest-asyncio**

---

## Estrutura do Repositório

```
OPERA IA/
├── docs/                          # Documentação técnica dos módulos
│   └── pdf_analyzer.md
├── scripts/
│   └── notebooks/                 # Notebooks exploratórios e de desenvolvimento
│       ├── test_nc_analyzer.ipynb
│       ├── test_pdf_processor.ipynb
│       └── test_summaryzer.ipynb
├── SOURCE/                        # Pacote principal da aplicação
│   ├── core/
│   │   ├── pdf_processor/         # Pipeline de extração e análise de PDFs
│   │   │   ├── analyzer.py        # Orquestrador: TF-IDF, deduplicação, limite de tokens
│   │   │   ├── extractor.py       # Extração via PyMuPDF + chunking (Chonkie)
│   │   │   ├── ml_client.py       # Cliente do ML Engine (embeddings)
│   │   │   ├── text_utils.py      # Pré-processamento e qualidade de texto
│   │   │   ├── tokenizer.py       # Tiktokenizer + wrappers de contagem de tokens
│   │   │   ├── file_utils.py      # Leitura/escrita de arquivos auxiliares
│   │   │   ├── dataclasses.py     # ChunkData, PageRecord
│   │   │   └── constants.py       # Constantes configuráveis do pipeline
│   │   ├── ai_orchestrator.py     # Invocação LLM, batch, normalização de resposta
│   │   ├── nc_analyzer.py         # Análise de notícias-crime (fluxos de prompt)
│   │   ├── summaryzer.py          # Sumarização Map-Reduce para documentos longos
│   │   └── exceptions.py          # Exceções de domínio centralizadas
│   ├── prompts/
│   │   ├── __init__.py            # load_prompts, get_prompt, get_reference_list
│   │   ├── output_schemas.py      # Schemas Pydantic de saída da LLM
│   │   ├── reference_validator.py # Fuzzy matching contra listas de referência
│   │   ├── references.yaml        # Listas de domínio (tipificações, assuntos RE, etc.)
│   │   └── templates.yaml         # Templates de prompt por etapa
│   ├── schemas.py                 # LLMConfig, enums de verbosidade e reasoning effort
│   └── settings.py                # EnvSettings, LLMProvider
├── tests/
│   ├── core/
│   │   ├── pdf_processor/
│   │   │   ├── assets/            # PDFs de fixture (simple, multipage, large_block)
│   │   │   ├── test_analyzer_unit.py
│   │   │   ├── test_analyzer_integration.py
│   │   │   ├── test_extractor.py
│   │   │   └── test_extractor_integration.py
│   │   ├── test_ai_orchestrator_utils.py
│   │   └── test_summaryzer.py
│   ├── prompts/
│   │   └── test_prompts.py
│   ├── conftest.py                # Fixtures globais (LLMConfig, mocks, mensagens)
│   └── test_schemas.py
├── conftest.py                    # Opção --run-integration para pytest
├── pyproject.toml
└── start_ml_engine.bat            # Inicializa o serviço ML Engine (Windows)
```

---

## Componentes Principais

### `ai_orchestrator.py`
Camada de abstração sobre LangChain. Expõe `invoke_completion_llm` e `batch_completion_llm` com suporte a múltiplos provedores (OpenAI, LLM-PF VPN, LLM-PF local), structured output via Pydantic, retry de parsing e acumulação de telemetria de tokens (`TokenUsageAccumulator`).

### `pdf_processor/`
Pipeline modular de processamento de PDFs:
1. **Extração** — PyMuPDF lê página a página; Chonkie fatia hierarquicamente quando necessário
2. **Qualidade** — heurísticas + detecção de idioma (lingua) para descartar chunks ilegíveis
3. **TF-IDF** — score de relevância lexical por chunk, base para todas as etapas seguintes
4. **Deduplicação** *(opcional)* — remoção de clones literais por grafo de componentes conexas (`similars_graphs`), operando sobre vetores TF-IDF
5. **Limite de contexto** *(opcional)* — seleção dos chunks de maior `score_tfidf` até a janela do modelo, com reordenação cronológica para preservar a narrativa

**Decisão de design — TF-IDF como estratégia primária:**
Embeddings semânticos estão disponíveis via ML Engine, mas **não são utilizados na etapa de deduplicação** para o escopo de análise de notícias-crime. Documentos jurídicos e oficiais contêm peças distintas sobre os mesmos fatos e sujeitos — dois despachos sobre o mesmo réu em momentos distintos têm alta similaridade semântica mas informações juridicamente opostas. O TF-IDF, medindo vocabulário literal, preserva essa distinção. O único tipo de redundância presente nos expedientes processados — páginas de protocolo repetidas, duplicatas de encaminhamento — é precisamente o que o TF-IDF com threshold alto (≥ 0.97) captura com precisão máxima e sem risco de perda informativa. Detalhes completos em [`docs/pdf_analyzer.md`](docs/pdf_analyzer.md).

**Estratégia para PDFs que excedem a janela de contexto:**

| Situação | Abordagem |
|---|---|
| Cabe no limite após filtro de qualidade | Texto integral, sem deduplicação |
| Volume moderado | Dedup TF-IDF (threshold 0.97) + corte por `score_tfidf` |
| Volume elevado | Loop com thresholds decrescentes [0.97 → 0.75] até caber |
| Volume genuíno (informação real, não redundância) | **Sumarização Map-Reduce** ou **sumarização por refinamento** *(a implementar — ver Roadmap)* |

### `nc_analyzer.py`
Orquestra fluxos multi-etapa de prompt para análise de notícias-crime. Suporta diferentes `PromptFlow` (1 etapa, 2 etapas, etc.), valida tokens de entrada antes de invocar a LLM e implementa retry automático sobre falhas de validação Pydantic.

### `summaryzer.py`
`MapReduceSummarizer`: agrupa chunks em lotes respeitando a janela do modelo, resume em paralelo (Map) e consolida iterativamente (Reduce) até atingir o limite de tokens desejado.

### `prompts/`
Templates YAML carregados via `get_prompt()`. Schemas de saída (`output_schemas.py`) incluem validação cruzada com `references.yaml` via fuzzy matching, suportando variações de grafia retornadas pela LLM.

---

## ML Engine

Serviço separado responsável pela geração de embeddings semânticos (Sentence Transformers / PyTorch). Inicializado localmente via `start_ml_engine.bat` no Windows.

Durante a reformulação, foi avaliado o uso de **ONNX Runtime** como alternativa mais leve ao PyTorch para inferência local. O resultado foi desempenho inferior; o PyTorch foi mantido.

O `ml_client.py` consome esse serviço via HTTP. Em caso de indisponibilidade, o pipeline faz fallback automático para TF-IDF denso.

**Uso atual:** o ML Engine está disponível na infraestrutura, mas os embeddings semânticos **não são a estratégia primária** no pipeline de análise de notícias-crime. A decisão está documentada em [`docs/pdf_analyzer.md`](docs/pdf_analyzer.md) — em síntese, embeddings são insensíveis a detalhes de entidade (nomes, CPFs, datas, valores monetários) e podem fundir chunks juridicamente distintos com alta similaridade temática. O TF-IDF lexical é mais seguro e suficiente para o tipo de redundância presente nos expedientes processados. O ML Engine permanece disponível para uso futuro em outros escopos.

---

## Configuração

### Variáveis de ambiente

Configure um arquivo `.env` na raiz com as chaves necessárias para os provedores desejados. Consulte `SOURCE/settings.py` (`EnvSettings`) para a lista completa de variáveis.

### Provedores LLM suportados

| Provider | Descrição |
|---|---|
| `openai` | API OpenAI (paga) |
| `llm_pf_vpn` | LLM interno PF via VPN |
| `llm_pf_local` | LLM interno PF rodando localmente |

---

## Instalação

```bash
# Instalar dependências
poetry install

# Iniciar o ML Engine (opcional — usado para embeddings semânticos em escopos futuros)
start_ml_engine.bat        # Windows
# ou equivalente no seu ambiente

# Executar testes unitários
pytest

# Incluir testes de integração (requerem APIs reais ativas)
pytest --run-integration
```

---

## Testes

Os testes são organizados espelhando a estrutura de `SOURCE/`. Markers disponíveis:

| Marker | Quando usar |
|---|---|
| `integration` | Testes que dependem de serviços externos; requerem `--run-integration` |
| `external` | Chamadas a APIs externas genéricas |
| `openai` | Testes que consomem a API paga da OpenAI |
| `llm_pf` | Testes que requerem VPN ou ML Engine local ativo |

PDFs de fixture estão em `tests/core/pdf_processor/assets/`.

---

## Roadmap

### Concluído

- [x] Refatoração do ML Engine — avaliação de ONNX Runtime (descartado) e manutenção do PyTorch
- [x] Refatoração do `pdf_processor` (extractor + analyzer)
- [x] Refatoração do `ai_orchestrator` com LangChain modernizado
- [x] Implementação do `summaryzer` (Map-Reduce)
- [x] Novos schemas Pydantic de saída (pessoas envolvidas, tipificações penais, timeline)

### Em andamento

- [ ] Incrementar etapa 3 opcional do fluxo de análise (`nc_analyzer`)
- [ ] Definição do local de análise nas listas de referência (COR/SP ou outra UF)
- [ ] Refatoração completa do `nc_analyzer`
- [ ] Módulos de testes automáticos e parametrizados para avaliação comparativa de modelos LLM

### Próximos passos

- [ ] **API REST (FastAPI)** — expor `ai_orchestrator`, `summaryzer` e `nc_analyzer` como endpoints
- [ ] **GUI React** — interface para visualização de análises, dashboards e interação com agente
- [ ] **PDFs longos — sumarização Map-Reduce** — quando o volume é informação real (não redundância), aplicar `MapReduceSummarizer` antes da análise; estratégia preferida sobre o loop de thresholds
- [ ] **PDFs longos — sumarização por refinamento** — variante iterativa do Map-Reduce para consolidação progressiva; complementar ao item anterior
- [ ] **Retry de parsing Pydantic** — reenvio automático ao LLM em caso de falha de validação
- [ ] **Script de atualização de `references.yaml`** — manutenção das listas de domínio
- [ ] **Logger para produção** — logs estruturados, ambiente multi-tenant, integração com monitoramento
- [ ] **Banco de dados local** — PostgreSQL + SQLAlchemy ORM
- [ ] **Autenticação** — módulo auth integrado ao FastAPI
- [ ] **Refatoração do `chat_orchestrator`** — histórico de conversação, gerenciamento de contexto, artefatos
- [ ] **PDFs com bloqueios/ofuscamento** — estratégia de tratamento a definir

---

## Requisitos

- Python `>=3.13, <3.14.1`
- Poetry `>=2.0`
- ML Engine (opcional) — para embeddings semânticos em escopos futuros; pipeline opera integralmente via TF-IDF sem ele
- Acesso à VPN PF para uso do provider `llm_pf_vpn`
