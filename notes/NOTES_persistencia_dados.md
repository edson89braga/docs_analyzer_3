# NOTES — Persistência de Dados, Logs e Métricas (ÓPERA)

> Levantamento feito em 19/08/2026, com ações de descontinuação do Firebase Storage para logs
> executadas em 20/08/2026 (ver seção 7). Este documento registra **o que o código realmente faz**,
> não o comportamento pretendido — ver `README.md` para a arquitetura da refatoração apartada, que
> não é a deste repositório.
>
> O tópico de bloqueio de versões antigas do desktop foi recortado para
> [`NOTES_bloqueio_versao_antiga.md`](NOTES_bloqueio_versao_antiga.md) — assunto independente, sem
> relação com persistência de dados.

---

## 1. Mapa real de persistência

| Dado | Onde é salvo | Mecanismo | Desktop (empacotado) | Servidor (VM/Docker) |
|---|---|---|---|---|
| Métricas de negócio (`pdf_analysis_completed`, `llm_feedback`, etc.) | **Firestore**, `user_metrics/{uid}/metrics/{doc_id}` | REST API com o **id_token do próprio usuário** — `FirebaseClientFirestore.save_metrics_client` ([SOURCE/services/firebase_client.py:523](SOURCE/services/firebase_client.py)) | ✅ Ativo | ✅ Ativo |
| Logs de texto (nuvem) | **Descontinuado em 20/08/2026** — ver seção 7. Histórico: `logs/AAAA/MM/DD/...` (legado) e `users/{uid}/logs/...` (novo) no Firebase Storage | Admin SDK — `FbManagerStorage`/`AdminLogUploader` ([SOURCE/logger/cloud_logger_handler.py](SOURCE/logger/cloud_logger_handler.py)) | ❌ Desligado | ❌ Desligado |
| Logs de texto (arquivo local, sempre) | Disco local, `PATH_LOGS_DIR` (`RotatingFileHandler`) | Sempre ativo, independe do Firebase — **agora a única persistência de logs** | ✅ | ✅ (`./logs` bind mount) |
| Prompts customizados / chat | SQLite local (`local_storage.sqlite`) | [SOURCE/services/local_db_manager.py](SOURCE/services/local_db_manager.py) | ✅ (por instalação) | ✅ (por container) |
| Realtime Database | — | Não utilizado — só um comentário morto em `firebase_manager.py` | — | — |

**Storage era usado só para logs de texto operacionais** — não há upload de PDFs/expedientes/documentos de caso para lá. Isso reduziu o risco de privacidade da migração feita na seção 7.

### Caminho de dump no Storage (histórico): hospedado vs. empacotado
A estrutura de pasta era **igual** nos dois modos (`logs/AAAA/MM/DD/{usuário}_{HHMMSS}_{hostname}.log`,
[cloud_logger_handler.py:205](SOURCE/logger/cloud_logger_handler.py)). A única diferença era o campo `hostname`:
- Desktop: nome de usuário Windows real (`os.getlogin()`).
- Container: `os.getlogin()` falha (sem sessão interativa) → cai no fallback `"unknown_pc"`.

O arquivo de log local (`./logs`) sempre rodou **em paralelo** ao upload para nuvem, nos dois modos — nunca foi um substituto.

---

## 2. Bug (histórico): upload de logs para o Storage estava quebrado na prática

> Contexto histórico — mantido para referência, já que a seção 7 descontinuou o mecanismo em vez de
> corrigi-lo (a decisão tornou o conserto do bug irrelevante).

Em `LoggerSetup.add_cloud_logging` / `_create_cloud_logger_handler` (removidos/neutralizados na seção 7; código original estava em [SOURCE/logger/logger.py:280-321](SOURCE/logger/logger.py)):

- Quando a função era chamada com `user_token_for_client`/`user_id_for_client` (o caso normal — todo
  login passava por aqui, [login_view.py:265](SOURCE/flet_ui/views/login_view.py)), o código
  **evitava** criar o `AdminLogUploader` (partindo do princípio de que ia usar um "uploader de
  cliente" alternativo).
- Esse "uploader de cliente" **nunca foi implementado** — só existia menção em comentário.
- Resultado: `_admin_uploader_instance` permanecia `None`, `_create_cloud_logger_handler` caía no
  `else` e retornava `None` silenciosamente (`logger.debug`, sem exceção nem alerta visível) — o
  `CloudLogHandler` nunca era anexado ao logger raiz.

**Evidência real de produção que confirmou o bug (19/08/2026):**
- O inventário do Storage (seção 5) mostrou que o log mais recente em `logs/` era de **2026-06-16**
  — mais de 2 meses sem nenhum log novo, apesar do sistema estar em uso ativo.
- `/app/logs/logs_backup_cloud_failed` na VM estava **vazio** — esse diretório só recebe arquivo
  quando o upload é tentado e falha após todas as retries. Vazio = uploads não estavam nem sendo
  *tentados*, consistente com o `CloudLogHandler` nunca sendo criado.
- `docker logs --tail 500 opera-ia-frontend` não trouxe nenhuma linha contendo `CloudLogHandler`.

---

## 3. Prompts customizados no SQLite — verificação (20/08/2026)

Verificado a pedido do usuário, que suspeitava que a funcionalidade nunca tivesse sido implementada:

- **`custom_prompts` — implementado e em uso real, mas com escopo bem mais estreito do que o nome
  sugere.** Não é um repositório de prompts genéricos da aplicação: a única coisa persistida ali é o
  **system-prompt customizável da interface de chat com documentos** (opção "Personalizado" do
  diálogo de instruções, chave fixa `"chat_custom"`, escopada por `user_id`) — não existe prompt
  customizado para `nc_analyze_view.py` ou qualquer outro fluxo.
  `LocalDBManager.save_custom_prompt()` / `get_custom_prompt()` ([SOURCE/services/local_db_manager.py:85-114](SOURCE/services/local_db_manager.py:85))
  são chamados pelo `ChatSettingsDrawer`
  ([SOURCE/flet_ui/components/settings_drawer.py:529](SOURCE/flet_ui/components/settings_drawer.py:529) e
  [:636](SOURCE/flet_ui/components/settings_drawer.py:636)). Detalhado também em
  [`docs/MODULES.md`](docs/MODULES.md) (nota de 20/08/2026, seção `ChatSettingsDrawer`).
- **`chat_history` (histórico de chat) — este sim é código morto.** A tabela é criada no schema
  ([local_db_manager.py:58-66](SOURCE/services/local_db_manager.py:58)) mas nenhum `INSERT`/`SELECT`
  é feito nela em lugar nenhum do código. O `chat_history_view` visível em `chat_view.py` é só o
  `ft.ListView` da UI (estado em memória da sessão), não persiste no SQLite.

---

## 4. Diagnóstico da VM de produção (19/08/2026)

Comandos rodados via SSH pelo usuário:

```
$ docker exec opera-ia-frontend ls -la /app/data
firebase_service_key.enc   3276 bytes   (30/Mar/2026)
local_storage.sqlite       40960 bytes  (14/Aug/2026)

$ docker exec opera-ia-frontend env | grep -iE "firebase|dpf_secret|app_mode"
APP_MODE=server
DPF_SECRET_SIST_OPERA_FIREBASE_ENCRYPTION_KEY=m0MMyi6H8ih9wjRTDZPsV6lqJKUQiI8KuuThQjK9eHc=

$ docker logs --tail 500 opera-ia-frontend | grep -iE "CloudLogHandler|Firestore|firebase.*inicializado|falha.*storage"
→ só linhas de "FirebaseClientFirestore inicializado" / "Configurações padrão carregadas do
  Firestore" — nenhuma linha de CloudLogHandler ou de inicialização do Admin SDK.

$ docker exec opera-ia-frontend ls -la /app/logs/logs_backup_cloud_failed
→ vazio (só '.' e '..')

$ docker exec -it opera-ia-admin python -c "..."
→ Error: container is not running

$ docker ps --filter "name=opera-ia-admin"
→ nenhum container listado

$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8501
→ 000 (sem resposta)
```

**Conclusões:**
1. A chave de serviço do Firebase **estava presente** no volume persistente da VM
   (`/app/data/firebase_service_key.enc`) — o Admin SDK tinha condição de funcionar lá.
2. O Firestore está confirmadamente ativo e em uso no servidor (linhas de log de inicialização
   recorrentes) — **não foi tocado** pela descontinuação da seção 7, só o Storage.
3. Ausência de logs de `CloudLogHandler` e diretório de backup de falha vazio reforçaram o bug da
   seção 2.
4. **O container `opera-ia-admin` (painel Streamlit) não estava rodando** — apesar do serviço estar
   definido e descomentado em `docker-compose.yml` na época. Em 20/08/2026 o serviço foi comentado
   de propósito no `docker-compose.yml` (seção 7, item 3) — agora o arquivo reflete corretamente a
   nota do `CLAUDE.md` local sobre estar "descontinuado".

---

## 5. Inventário real do Firebase (read-only, via credencial local configurada em 19/08/2026)

Rodado localmente com `SOURCE.services.firebase_manager` (Admin SDK), sem baixar, alterar ou
remover nenhum dado:

```
[AUTH] Total de usuários cadastrados: 51

[STORAGE] Total de objetos: 3299
[STORAGE] Tamanho total: 19.09 MB (20.020.551 bytes)
[STORAGE] Data mais antiga: 2025-06-23
[STORAGE] Data mais recente: 2026-06-16   ← nenhum log novo há > 2 meses (ver seção 2)

[STORAGE] Detalhamento por prefixo:
   - logs/ (legado)               3196 arquivos, 18.92 MB
   - users/{uid}/logs/ (novo)      103 arquivos,  0.17 MB

[FIRESTORE] Coleções de nível raiz:
   - app_default_settings
   - llm_providers_config
   - prompt_templates
   - user_api_keys
   - user_metrics

[FIRESTORE] Usuários com métricas salvas: 22 / 51
[FIRESTORE] Total de documentos de métrica: 964
```

Observações:
- Não existe uma coleção raiz `metrics` (a que `FbManagerFirestore.save_metrics`, via Admin SDK,
  gravaria) — confirma que esse método é código morto; tudo passa pelo caminho REST
  (`save_metrics_client`, `user_metrics/{uid}/metrics`).
- Volume do Storage era pequeno (~19 MB, 3299 arquivos) — a migração/download completo (seção 7) foi
  uma operação rápida e de baixo risco técnico, como previsto.

---

## 6. Ferramentas já existentes para consolidação

`admin_py/` já tinha boa parte do caminho andado — reaproveitado em vez de recomeçado (seção 7):

- **`local_data_manager.py`** → `sync_cloud_data_to_local()`: baixa incrementalmente (só o que
  ainda não existe localmente) todos os logs do Storage **e** todas as métricas do Firestore. Não
  foi usado diretamente na migração da seção 7 porque mistura os dois (o usuário pediu para não
  tocar no Firestore por enquanto) — em vez disso, foi criado `sync_storage_logs_only.py`
  (só Storage).
- **`dashboard_analyzer.py`**: carrega `admin_data/metrics/` num DataFrame pandas e calcula KPIs
  (usuários ativos, total de análises, custo LLM/embeddings, feedback de acurácia).
- **`dashboard_plotter.py`**: gráficos para o Streamlit.
- **`export_data.py`**: achata métricas (`pdf_analysis_completed`, `llm_feedback`) para
  exportação tabular.
- **`cleanup_cloud_logs.py`**: `get_cloud_log_stats()` e `run_cloud_log_cleanup()` para Storage —
  segue existindo para o usuário rodar manualmente a limpeza do bucket, depois de confirmar o
  download da seção 7 e apagar os dados pelo console do Firebase.
- **`run_admin_streamlit.py`**: entrypoint do painel, validado rodando localmente na seção 7 (item 5).

---

## 7. Ações executadas em 20/08/2026 (descontinuação do Storage para logs)

Decisão do usuário: parar de usar o Firebase Storage para persistir logs de texto; tudo passa a ser
local (VM) + trazido para este repositório antes de qualquer remoção manual no console do Firebase.

1. **`LoggerSetup.add_cloud_logging()` neutralizado** ([SOURCE/logger/logger.py](SOURCE/logger/logger.py)) —
   virou no-op (retorna `False` imediatamente, loga em debug). Os callers em
   [SOURCE/flet_ui/app.py:344](SOURCE/flet_ui/app.py:344) e
   [SOURCE/flet_ui/views/login_view.py:265](SOURCE/flet_ui/views/login_view.py:265) já toleravam
   retorno `False` silenciosamente, então nenhum outro ponto precisou de alteração. O método
   `_create_cloud_logger_handler`, órfão após essa mudança, foi removido junto. `cloud_logger_handler.py`
   (classes `CloudLogHandler`/`AdminLogUploader`) e `firebase_manager.py::FbManagerStorage` foram
   **mantidos** (código agora inerte no fluxo de produção, mas ainda usados pelas ferramentas
   administrativas de download/limpeza abaixo).
2. **Download de segurança do Storage**: script novo
   [`admin_py/sync_storage_logs_only.py`](admin_py/sync_storage_logs_only.py) (só Storage, não toca
   Firestore) executado — trouxe os **3299/3299 objetos** do bucket para
   `admin_data/logs/` (734 novos + 2565 que já existiam de uma sincronização anterior de 26/03/2026).
   Contagem local bate exatamente com o inventário da seção 5.
3. **`docker-compose.yml`**: serviço `opera-admin` (painel Streamlit) comentado — decisão do item 6
   abaixo (painel só roda a partir deste repositório local a partir de agora). Bloco mantido como
   comentário para referência/reversão, não apagado.
4. **Scripts para trazer os logs da VM** (para o usuário executar manualmente):
   - [`scripts/fetch_vm_logs.sh`](scripts/fetch_vm_logs.sh) — baixa via SSH/rsync o conteúdo de
     `./logs` (bind mount do container `opera-ia-frontend`) da VM para `admin_data/vm_logs/` neste
     repositório. Requer preencher `VM_USER`/`VM_HOST`/`VM_REMOTE_DEPLOY_DIR` no topo do arquivo.
   - [`scripts/cleanup_vm_logs.sh`](scripts/cleanup_vm_logs.sh) — a rodar **só depois** de confirmar
     visualmente que `admin_data/vm_logs/` está completo. Por segurança, não faz `rm -rf` direto:
     move o conteúdo de `./logs` na VM para `./logs_backup_<timestamp>` (mesmo diretório de deploy)
     e recria `./logs` vazio — dry-run por padrão, exige `--yes` para executar de fato. Como
     `./logs` é bind mount para `/app/logs` do container, limpar no host já limpa no container, sem
     precisar de `docker exec`.
5. **Dashboard consolidada validada localmente**: `run_admin_streamlit.py` rodado localmente
   (`streamlit run run_admin_streamlit.py`) contra `admin_data/` já populado — carregou sem erros
   (KPIs, gráficos Plotly, tabela de atividade). Números de análises/feedback aparecem zerados no
   filtro "últimos 7 dias" porque as métricas do Firestore não foram ressincronizadas (última
   sincronização é de 26/03/2026) — Firestore não foi tocado por decisão explícita do usuário.

**Pendências que ficam para quando o usuário decidir seguir adiante:**
- Rodar `scripts/fetch_vm_logs.sh` e depois `scripts/cleanup_vm_logs.sh` (manual, fora desta sessão).
- Confirmar visualmente `admin_data/logs/` (Storage) e `admin_data/vm_logs/` (VM) antes de apagar
  qualquer coisa no console do Firebase.
- Rodar `cleanup_cloud_logs.run_cloud_log_cleanup()` ou apagar o bucket manualmente no console do
  Firebase (fora do escopo desta sessão — o usuário faz isso manualmente).
- Decidir se/quando sincronizar o Firestore (métricas) também — não fazia parte do pedido de hoje.
- Realinhar a nota do `CLAUDE.md` local sobre o `opera-admin` — antes dizia "descontinuado" mas o
  arquivo não estava comentado; agora está, e a nota passou a ser precisa.

---

*Documento gerado a partir de leitura de código + diagnóstico ao vivo da VM (seção 4, colado pelo
usuário) + inventário read-only do Firebase (seção 5, executado localmente em 19/08/2026) + ações
de descontinuação executadas em 20/08/2026 (seção 7), todas por Claude Code, com a credencial de
admin configurada na máquina do usuário para esta sessão.*
