# NOTES_ocr.md

Decisões de design, limitações e parâmetros da ocerização automática (`SOURCE/core/pdf_processor.py`)
e da descontinuação da `ml_engine` (embeddings locais/OpenAI). Registrado em 24/08/2026.

---

## 1. Contexto — por que estas duas mudanças vieram juntas

Em produção, ficou evidente que a seleção de páginas relevantes por **TF-IDF** (`sklearn`) é tão
eficaz quanto a seleção por embeddings semânticos (`all-MiniLM-L6-v2`, servido pela `ml_engine`
separada em FastAPI/PyTorch) — e sensivelmente mais barata e rápida, sem exigir um segundo
container/processo. A opção `text-embedding-3-small` (OpenAI, cobrada por token) também foi
removida: o TF-IDF passou a ser o único modo de vetorização/seleção de páginas do sistema.

Isso liberou espaço para investir na outra lacuna conhecida: até aqui, páginas com texto
ininteligível (tipicamente digitalizadas sem camada de texto) eram apenas sinalizadas ao usuário
("considere usar OCR nelas"), sem nenhuma ação automática. Com a `ml_engine` fora do caminho, a
ocerização automática das páginas ininteligíveis passou a ser a nova etapa do pipeline.

---

## 2. Ocerização automática — fluxo

Disparada em `PDFDocumentAnalyzer.apply_ocr_to_unintelligible_pages()`, chamada por
`nc_analyze_view.py` (`_run_auto_ocr_step`) e `chat_view.py` (mesmo nome, cópia adaptada à captura
local de `page` desta view) logo após `build_combined_page_data()`/`analyze_pre_extracted_texts()`
e **antes** do cálculo de TF-IDF — assim, páginas recuperadas participam normalmente da seleção por
relevância.

```
build_combined_page_data() → páginas com 'inteligible': False
        │
        ▼
apply_ocr_to_unintelligible_pages()
        │  para cada página ininteligível:
        │    1. rasteriza a página (fitz, 300 DPI) → array numpy RGB
        │    2. roda o RapidOCR → reconstrói texto respeitando layout (linhas/colunas)
        │    3. sobrescreve text_stored/number_words/number_tokens/inteligible/ocr_applied
        │    4. reavalia is_text_intelligible() no texto ocerizado
        │
        ▼
get_similarity_and_tfidf_score_docs() → TF-IDF já sobre o texto recuperado
```

Página que segue ininteligível mesmo após a tentativa (ex.: página em branco, imagem sem texto
legível) continua sendo descartada exatamente como antes — nenhuma mudança de comportamento nesse
caso, só uma tentativa extra.

**Cancelamento:** como o custo por página (~1-3s em CPU) pode somar minutos em lotes grandes, não
há teto de páginas — em vez disso, a UI exibe um diálogo modal de progresso página a página
(`show_cancelable_progress_dialog`, `components.py`) com botão **"Cancelar OCR"**. Cancelar
interrompe só a etapa de OCR (via `threading.Event` verificado a cada página); as páginas já
recuperadas até o clique são mantidas, e o restante segue descartado como ininteligível — o
pipeline continua normalmente a partir daí (não aborta a análise inteira).

**Configuração:** toggle `auto_ocr_enabled` (`FALLBACK_ANALYSIS_SETTINGS`, `settings_drawer.py` —
substituiu o antigo dropdown "Modelo de Vetorização"), ligado por padrão.

**UI de metadados:** nova linha "Páginas Ocerizadas Automaticamente" no painel "Dados do
Processamento" (`_update_processing_metadata_display`, nc_analyze_view.py e chat_view.py), com o
mesmo formato `contagem : intervalos` das demais linhas de páginas. O aviso "páginas ininteligíveis
detectadas" agora distingue se a ocerização automática rodou (mensagem indica que já foi tentada)
ou estava desligada (mensagem sugere ligá-la).

---

## 3. Biblioteca e modelo OCR — RapidOCR (mesma configuração de outro projeto interno)

- Pacote **`rapidocr==3.8.3` fixado** (não usar range): a partir da 3.9 a validação de parâmetros do
  engine mudou e passa a rejeitar a combinação usada aqui (`ValueError: Invalid OCR configuration`).
  Testado e confirmado neste projeto em 24/08/2026.
- Configuração do engine (`get_ocr_engine()`, `pdf_processor.py`):
  `Det.ocr_version = OCRVersion.PPOCRV5`, `Rec.lang_type = LangRec.LATIN` — cobre o charset Latin
  completo, incluindo diacríticos do português (ã, ç, ê, õ...). Mesma combinação já validada em
  produção no projeto `rotina_epol_1` (`scripts_epol/rotina_epol_1/SOURCE/pdf_processor/ocr.py`).
- `_reconstruct_text_from_layout()` e `ocr_page_text()` foram portados (com pequenas adaptações de
  docstring) da implementação já testada nesse outro projeto, em vez de reescritos do zero.
- Engine é um **singleton lazy por processo** (`get_ocr_engine()`, protegido por `threading.Lock`),
  compartilhado entre sessões/usuários no modo servidor — inferência onnxruntime é thread-safe.

### 3.1. Bootstrap dos modelos ONNX — sem download em runtime

RapidOCR baixa os modelos ONNX (det/rec/cls) de `modelscope.cn` na primeira instanciação em cada
máquina, e os cacheia em `<site-packages>/rapidocr/models/`. Isso é um problema conhecido atrás do
proxy corporativo da PF (ver `NOTES_PdfProcessor.md` do projeto `rotina_epol_1`, seção 6) — por
isso os modelos são **pré-instalados no build**, nunca baixados em runtime:

- **Docker/VM:** os 3 arquivos `.onnx` necessários para a combinação PPOCRV5+LATIN
  (`ch_PP-OCRv5_det_mobile.onnx`, `latin_PP-OCRv3_rec_mobile.onnx`,
  `ch_ppocr_mobile_v2.0_cls_mobile.onnx`) ficam em `modelos_ocr/` na raiz do repo — **gitignorado**
  (binários, ~14 MB), mas **incluído no contexto do `docker build`** (removido do
  `.dockerignore`). O `Dockerfile` copia esses arquivos para dentro do pacote `rapidocr` já
  instalado, logo após o `poetry install` (ver Dockerfile). Isso significa: **`modelos_ocr/` precisa
  existir localmente antes de rodar `docker build`** — não é criado automaticamente.
- **Como (re)popular `modelos_ocr/`:** copiar os 3 arquivos de qualquer venv onde o RapidOCR já
  tenha sido instanciado com essa mesma config (ex.: `<venv>/Lib/site-packages/rapidocr/models/`).
  Neste projeto, os arquivos vieram do venv do projeto `rotina_epol_1`
  (`rotina-epol-1-mTbM4RHL-py3.14`), que já os tinha em cache de uso anterior — evitou qualquer
  download nesta máquina de desenvolvimento.
- **Desktop (.exe):** não aplicável — ver seção 4.

---

## 4. Distribuição desktop descontinuada

A partir desta mudança, **não são mais gerados/distribuídos executáveis desktop (PyInstaller)** do
ÓPERA — apenas a versão hospedada (Docker, VM PF) é mantida. Consequências práticas:

- `run.py` continua funcional para desenvolvimento local (`python run.py` / `flet run`), mas deixou
  de ser o alvo de builds `.exe` para distribuição a usuários finais.
- O bootstrap/atualização automática da `ml_engine` foi removido de `run.py`
  (`MLEngineManager`, verificação de atualização do "Motor de ML") junto com o resto da
  descontinuação — não porque o desktop foi descontinuado, mas porque o serviço em si não existe
  mais.
- Não há necessidade de reproduzir o bootstrap de `modelos_ocr/` para PyInstaller: sem builds
  desktop, o único alvo de empacotamento é a imagem Docker (seção 3.1).
- `pyinstaller_files/*.spec` e o fluxo de `update_manager.py`/`release_info/version.json` para o
  componente `"app"` seguem no repositório (não foram removidos), caso a decisão seja revertida no
  futuro — mas não fazem parte do fluxo de release atual.

---

## 5. Limitações conhecidas / próximos passos

- **Qualidade do OCR em português jurídico não validada em produção real** — os testes desta
  mudança usaram PDFs sintéticos (texto renderizado) para validar o encanamento
  (rasterização → engine → reconstrução de layout → reintegração no pipeline TF-IDF), não a
  acurácia do reconhecimento em digitalizações reais (ruído de scanner, carimbos, assinaturas
  manuscritas, baixa resolução). Recomenda-se rodar a primeira leva de análises com OCR automático
  sob observação antes de confiar cegamente no texto ocerizado.
- Sem "modo dry-run" para estimar quantas páginas seriam ocerizadas antes de disparar a análise —
  o usuário só descobre ao ver o diálogo de progresso abrir (ou não).
- `ai_orchestrator.get_embeddings_from_api`, `calc_costs_embedding_process`,
  `KEY_SESSION_MODEL_EMBEDDINGS_LIST`/`KEY_SESSION_TOKENS_EMBEDDINGS` e a leitura do documento
  Firestore de custos de embedding (`LLM_EMBEDDINGS_CONFIG_COLLECTION`) foram removidos do cliente;
  o documento em si não foi apagado do Firestore (não há necessidade — só deixou de ser lido).
