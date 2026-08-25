# NOTES — Monitoramento de uso em produção (quem está usando agora)

> Criado em 25/08/2026. Cobre o acompanhamento operacional da VM (quem está conectado,
> logs por usuário) — não confundir com `NOTES_metricas_dashboard.md`, que cobre as
> métricas de uso (análises, chat, feedback) sincronizadas em lote para o painel Streamlit.

---

## 1. Problema

O acompanhamento via `docker logs -f opera-ia-frontend` (SSH na VM) mistura os logs de
todos os usuários conectados simultaneamente, sem identificação de quem gerou cada linha
nem visão de quem está online no momento.

## 2. O que já existia

- O logger de **arquivo** (`logs/DocsAnalyzer3_Server.log`, sempre em DEBUG) já grava
  `session_id`/`user_id` em cada linha, via `SessionContextFilter`
  (`SOURCE/logger/logger.py`). O logger de **console** (o que aparece em `docker logs`)
  usa um formato reduzido, sem esses campos — daí a sensação de log "misturado".
- Esse arquivo já está fora do container: `./logs:/app/logs` é bind mount no
  `docker-compose.yml`, então está disponível diretamente no disco da VM.
- Já existia contagem de sessões ativas em memória (`global_active_sessions`, em
  `SOURCE/flet_ui/app.py`), logada como `[MONITORIA] ... Usuários conectados agora: N`
  — mas só a quantidade, não quem, e apenas em RAM (perdida a cada restart do processo).

## 3. O que foi implementado

### Nível 0 — usar o que já existe
`scripts/watch_logs.sh`: roda **localmente** (Git Bash no Windows, ou qualquer máquina
com `ssh`), conecta na VM via SSH e acompanha `logs/DocsAnalyzer3_Server.log` em tempo
real (`tail -F`), com filtro opcional por usuário/sessão/texto e cores por nível
(ERROR/WARNING em destaque). Não precisa copiar nada para a VM: a lógica remota
(`scripts/_remote_watch_logs.sh`) é enviada via stdin do SSH a cada execução — só
`ssh` local é necessário. Pede a senha da VM a cada chamada, como o SSH manual.

```bash
./scripts/watch_logs.sh                  # tudo
./scripts/watch_logs.sh usuario@dominio  # só as linhas desse usuário
```

Host/caminho da VM são configuráveis via `VM_HOST`/`VM_PATH` (env vars), com default
apontando para a VM de produção conforme `Instruções SSH VM PF Docker Deploy.txt`.

### Nível 1 — "quem está online agora", persistido

- `global_active_sessions` (`SOURCE/flet_ui/app.py`) passou de `set[session_id]` para
  `dict[session_id, user_email | None]` — guarda quem, não só quantos.
- Nova tabela `active_sessions` no SQLite local (`SOURCE/services/local_db_manager.py`):
  `session_id`, `user_email`, `connected_at`, `disconnected_at`. Métodos:
  `register_session_connect`, `register_session_user`, `register_session_disconnect`,
  `reset_stale_sessions` (fecha sessões órfãs de uma execução anterior, chamado uma vez
  na inicialização do singleton — evita sessão-fantasma "ativa para sempre" após restart).
- A associação sessão → e-mail acontece em dois pontos, cobrindo login novo e sessão
  restaurada do `client_storage`:
  - `SOURCE/flet_ui/views/login_view.py` (`handle_login_click`), logo após autenticar;
  - `SOURCE/flet_ui/app.py` (`initialize_app_flow`), quando `load_auth_state_from_storage`
    já traz uma sessão autenticada (reload/reconexão sem novo login).
- Persiste em SQLite (sobrevive a restart do container) — diferente do dict em memória,
  que continua existindo só para o log `[MONITORIA]` já existente.

Consulta pontual, também via SSH local (mesmo padrão do `watch_logs.sh`):

```bash
./scripts/check_active_sessions.sh          # sessões ativas agora
./scripts/check_active_sessions.sh --all    # inclui histórico de sessões encerradas
```

O script remoto (`scripts/_remote_check_active_sessions.sh`, enviado via stdin) roda
`docker exec ... python -m SOURCE.scripts.check_active_sessions` dentro da VM — o módulo
`SOURCE/scripts/check_active_sessions.py` precisa executar dentro do container porque a
tabela vive no volume nomeado `opera_data` (`/app/data`, não é bind mount).

### Padrão dos scripts de operação (`scripts/`)

`watch_logs.sh` e `check_active_sessions.sh` são os únicos pensados para rodar
localmente — fazem o SSH e enviam a lógica remota (`scripts/_remote_*.sh`) via stdin do
próprio comando SSH, então **nada precisa ser copiado manualmente para a VM**: qualquer
alteração nesses arquivos já vale na próxima execução. `VM_HOST`/`VM_PATH` (e
`CONTAINER`/`DOCKER_CMD` no segundo) são configuráveis via variável de ambiente.

## 4. O que ficou fora (avaliar se a dor persistir)

- Log estruturado (JSON) no console / handler do console também identificado por
  sessão — hoje só o arquivo tem os campos completos.
- Agregação centralizada (Loki+Promtail+Grafana como serviço adicional no
  `docker-compose.yml`) para dashboard/histórico/alertas, se o volume de uso crescer
  o suficiente para justificar.
- Presença em tempo real fora da VM (ex.: Firestore) — desproporcional ao uso atual.

## 5. Armadilha conhecida

Se um dia a aplicação rodar com múltiplas réplicas/workers do processo Flet,
`global_active_sessions` (em memória) deixa de refletir o total real — cada processo só
vê suas próprias sessões. A tabela SQLite tem o mesmo problema caso `SERVER_DATA_DIR`
não seja compartilhado entre réplicas. Não é o cenário atual (um único container,
`opera-ia-frontend`), mas vale revisitar se isso mudar.
