# CLAUDE.md — ÓPERA (docs-analyzer-3)

Instruções locais para este repositório. Complementa (e onde conflitar, sobrepõe) o `CLAUDE.md` global.

---

## 0. Contexto crítico — leia antes de qualquer alteração

**Este repositório é o MVP em produção**, hospedado em VM Linux da PF e em uso real por usuários (ver `NOTES.md`). Uma refatoração completa do núcleo de processamento (LangChain, Pydantic v2, pipeline `pdf_processor` modularizado, API REST) está sendo feita **em repositório/branch totalmente apartado**, para não arriscar o que está em produção.

Consequências práticas:

- **O [README.md](README.md) descreve a arquitetura da refatoração apartada, não o código deste repositório.** Não usar o README como referência de como o código atual funciona — ele documenta um estado futuro/planejado. Ver seção 8 para o que realmente existe aqui.
- Mudanças neste repositório devem ser **conservadoras e cirúrgicas por padrão** (reforça a regra global de "mudanças cirúrgicas" — aqui o custo de regressão é maior por ser produção ativa).
- Não trazer padrões da refatoração (LangChain, reestruturação de `pdf_processor.py` em pacote, etc.) para cá "de brinde". Se uma tarefa aqui parecer pedir isso, é sinal de que ela pertence ao repo da refatoração — apontar isso ao usuário antes de implementar.
- Não fazer merge/sync automático entre este repo e o da refatoração sem instrução explícita.

---

## 1. O que é o projeto

**ÓPERA — IA Assistente** (`APP_NAME = "Sist_Opera"`, `APP_VERSION` atual: ver `SOURCE/settings.py`). Aplicação da Polícia Federal para análise de documentos/PDFs (notícias-crime, expedientes) via LLM: extração, deduplicação TF-IDF, sumarização, chat sobre documentos e geração de relatórios `.docx`.

Dois modos de execução do mesmo código:
- **Desktop standalone** — `run.py`, compilável para `.exe` via PyInstaller.
- **Servidor web multi-usuário** — `run_server.py`, rodando em Docker na VM PF (`APP_MODE=server`).

---

## 2. Stack real em uso

- **UI:** [Flet](https://flet.dev) — mesma base de código para desktop e web.
- **LLM:** chamadas diretas via `openai` SDK (**não** usa LangChain, apesar de listado em `pyproject.toml` — dependência não utilizada no código atual, possivelmente resquício ou preparação para a refatoração).
- **Extração de PDF / NLP:** PyMuPDF (`fitz`), pdfplumber, `scikit-learn` (TF-IDF), `tiktoken`, `nltk`, `langdetect`.
- **Backend/dados:** Firebase (Auth + Firestore + Storage) via `firebase-admin`; SQLite local (`SOURCE/services/local_db_manager.py`); `keyring` + `cryptography` (Fernet) para credenciais locais.
- **ML Engine:** serviço FastAPI + PyTorch **separado** (`ml_engine/`, executável compilado), consumido via HTTP por `SOURCE/services/ml_client.py`, com fallback automático se indisponível.
- **Empacotamento:** PyInstaller (desktop) + Docker (`Dockerfile`, `docker-compose.yml` — servidor).

---

## 3. Estrutura real (`SOURCE/`)

```
SOURCE/
├── core/
│   ├── ai_orchestrator.py        # Chamadas LLM (OpenAI SDK direto)
│   ├── chat_llm_orchestrator.py  # Orquestração do chat sobre documentos
│   ├── pdf_processor.py          # Extração + TF-IDF + dedup (arquivo único, não pacote)
│   ├── prompts.py                # Templates e montagem de prompts
│   └── doc_generator.py          # Geração de relatórios .docx
├── flet_ui/
│   ├── app.py, router.py, layout.py, theme.py
│   └── views/                    # login, signup, home, nc_analyze, chat, profile, llm_settings, proxy_settings
│   └── components/                # file_list_manager, settings_drawer, components
├── services/
│   ├── firebase_client.py, firebase_manager.py   # Auth/Firestore/Storage
│   ├── credentials_manager.py    # Keyring + Fernet
│   ├── engine_manager.py, ml_client.py  # ML Engine (processo externo)
│   ├── local_db_manager.py       # SQLite
│   └── update_manager.py         # Auto-updater (via updater.py/updater.exe)
├── security/anonymizer.py
├── logger/logger.py + cloud_logger_handler.py    # Logs locais + upload para Firebase Storage
├── config/provider.py, config_manager.py
└── settings.py, app_cache.py, utils.py
```

`admin_py/` — painel administrativo Streamlit (`run_admin_streamlit.py`). Conforme `NOTES.md`, o serviço `opera-admin` no `docker-compose.yml` está marcado como descontinuado/comentado — **confirmar com o usuário antes de assumir que está ativo** em qualquer tarefa que o envolva.

---

## 4. Convenções de nomenclatura (observadas no código — adotar estas, não o fallback global)

- Módulos, funções, variáveis: `snake_case`.
- Classes: `PascalCase`.
- Constantes: `UPPER_SNAKE_CASE`.
- **Chaves de sessão/cache do Flet:** prefixo `KEY_SESSION_*`, definidas centralizadamente em `SOURCE/settings.py` (não espalhar strings literais de chave de sessão pelo código — sempre referenciar a constante).
- Nomes técnicos em inglês; nomes de domínio/negócio em português (`nc_analyzer`, `dashboard_analyzer`, campos de prompts, etc.) — consistente com o padrão fallback global.
- Sem `ruff`/`mypy` configurados em `pyproject.toml` ainda. Ao tocar em código, seguir PEP 8 e type hints manualmente (regra global), mas **não introduzir a configuração de lint/mypy neste repo sem alinhar antes** — pode gerar ruído grande em um MVP com muito código legado não tipado.

---

## 5. Testes

- `tests/` está **essencialmente vazio** (sem testes reais) — a suíte pytest descrita no README pertence à refatoração apartada.
- `tests_scripts/` e `tests_in_dev/` contêm scripts manuais/exploratórios (gitignorados) usados para validação ad hoc, não uma suíte automatizada.
- Ao corrigir bugs ou alterar lógica aqui, **não é obrigatório** criar testes automatizados (diferente da regra global de "se existir `tests/` correspondente, atualizar é obrigatório" — não há testes correspondentes de fato). Sugerir cobertura pontual quando a lógica for crítica, mas sem bloquear a entrega por isso.

---

## 6. Segredos e configuração

- `.env` na raiz (gitignorado) guarda `api_key` — correto.
- ⚠️ **`docker-compose.yml` está versionado e contém segredos em texto puro** (`FLET_SECRET_KEY`, `DPF_SECRET_SIST_OPERA_FIREBASE_ENCRYPTION_KEY`). Não copiar esse padrão em novos arquivos; ao tocar nesse arquivo, sinalizar a exposição e propor migração para variável de ambiente externa/secret do Docker antes de prosseguir.
- Chave de serviço do Firebase é armazenada criptografada localmente (`ENCRYPTED_SERVICE_KEY_PATH`, Fernet) — não versionar `credentials_fb.json` nem chaves derivadas.
- Variáveis de proxy corporativo (`PROXY_URL_DEFAULT`, etc.) são específicas do ambiente de rede da PF — não hardcodear novos endpoints sem confirmar com o usuário.

---

## 7. Deploy

- Produção: Docker na VM Linux da PF, com estratégia de **deploy offline** (build local sem proxy → `docker save` → `scp`/WinSCP → `docker load` na VM), documentada em `NOTES.md`.
- **Bind mounts** (`./SOURCE`, `./assets`, `./logs`, `./uploads_temp`) permitem hot-reload de código sem rebuild da imagem — mudanças em `.py` só exigem `docker-compose restart`. Rebuild completo só é necessário para mudanças em dependências (`pyproject.toml`) ou no `Dockerfile`.
- Auto-updater do executável desktop consulta `VERSION_INFO_URL` (GitHub raw) — coordenar com `release_info/` ao gerar novas versões.

### ⚠️ `Deploy_PF/` — NUNCA tocar

- `Deploy_PF/` (raiz do repo, gitignorado) é a área de staging do deploy manual do usuário: cópia paralela de `SOURCE/`/`admin_py/`/`assets/` + `docker-compose.yml`, `credentials_fb.json`, `firebase_service_key.enc`, e os `.tar` das imagens Docker já exportadas (`opera_app_image.tar`, `ml_engine_image.tar`).
- **O usuário sincroniza esse diretório manualmente** (copia os `.py` alterados de `SOURCE/` para dentro de `Deploy_PF/SOURCE/` por conta própria) e depois faz o SCP dele para a VM. Isso é proposital — ele quer manter controle explícito sobre o que vai para produção e quando.
- **Nunca copiar, editar ou sincronizar arquivos dentro de `Deploy_PF/` de forma autônoma**, mesmo que ele fique visivelmente desatualizado em relação a `SOURCE/` (isso é esperado e normal entre um deploy e outro). Também listado em `.claudeignore` — não ler/buscar nesse diretório por padrão.
- Editar em `SOURCE/` é suficiente para qualquer tarefa de código. Só mencionar `Deploy_PF/` se o próprio usuário perguntar sobre o estado do deploy.

---

## 8. Sobre a documentação existente

- `README.md` — descreve a arquitetura da **refatoração apartada** (LangChain, Pydantic v2, `pdf_processor/` como pacote, testes pytest). Não confiável como referência do código atual deste repositório.
- `docs/MODULES.md` — notas manuais (parciais, datadas 20/09/2025) sobre fluxos internos de algumas views Flet (`nc_analyze_view.py`, `chat_view.py`, `settings_drawer.py`). Útil como mapa de fluxo, mas não exaustivo nem necessariamente atualizado — conferir contra o código antes de confiar cegamente.
- `NOTES.md` — relatório de status sobre a migração para deploy em VM/Docker; é a fonte mais confiável sobre a infraestrutura de produção atual.
- Ao promover mudanças relevantes neste repo, atualizar `docs/MODULES.md`/`NOTES.md` conforme aplicável — **não** o `README.md`, que pertence à narrativa da refatoração (a menos que o usuário peça explicitamente para dessincronizar/corrigir essa mistura).

---

## 9. Regras específicas deste repositório

- Commits diretos na `master`, prefixos `FEAT:`/`FIX:`/`UPD:`/`DOCS:` — já em uso consistente no histórico (`git log`), manter.
- Por ser MVP em produção com usuários ativos: preferir correções mínimas e reversíveis; evitar refatorações amplas de módulos existentes mesmo que o código pareça pedir (isso é trabalho do repo apartado).
- Qualquer alteração em `SOURCE/settings.py`, `docker-compose.yml` ou `Dockerfile` afeta produção diretamente via bind mount — tratar como mudança de maior risco, confirmar com o usuário antes de aplicar.
