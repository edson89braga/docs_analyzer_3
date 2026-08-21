# run_admin_streamlit.py
import streamlit as st
import pandas as pd
import io, json
from datetime import datetime, date, timedelta

# Configuração do Logger (deve ser a primeira coisa)
from SOURCE.logger.logger import LoggerSetup
LoggerSetup.initialize(
    routine_name="Admin_Dashboard_Streamlit",
    dev_mode=True,
    modules_to_log=['SOURCE', 'admin_py', '__main__']
)

# Imports dos módulos de lógica admin
from admin_py import dashboard_analyzer, dashboard_plotter, local_data_manager, export_data
from admin_py import admin_llm_providers, upload_prompts, cleanup_cloud_logs, user_verification
from admin_py import feedback_analyzer
from admin_py.set_admin import set_user_admin_status

st.set_page_config(
    page_title="IA Assistente - Painel Admin",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Cache de Dados ---
@st.cache_data(ttl=600) # Cache por 10 minutos
def load_metrics_df():
    df = dashboard_analyzer.load_all_metrics_to_dataframe()
    return df if df is not None else pd.DataFrame()

@st.cache_data(ttl=3600) # Cache por 1 hora
def get_user_map():
    return local_data_manager.get_user_id_to_name_map()

# --- Carregamento de Dados ---
df_metrics = load_metrics_df()
user_id_to_name_map = get_user_map()
# Resolve UID -> nome uma única vez: todas as agregações usam a coluna 'user_name'.
df_metrics = dashboard_analyzer.attach_user_names(df_metrics, user_id_to_name_map)

# --- Barra Lateral de Navegação ---
st.sidebar.title("Painel Administrativo")
page = st.sidebar.radio("Navegar", ["Dashboard", "Dados & Logs", "Usuários", "Configurações"])

last_sync = local_data_manager.load_last_sync_timestamp()
if last_sync:
    st.sidebar.caption(f"Dados sincronizados em:\n{last_sync}")
else:
    st.sidebar.caption("Nenhuma sincronização realizada.")

# --- Renderização das Páginas ---

if page == "Dashboard":
    st.title("📊 Dashboard de Métricas")

    if df_metrics.empty:
        st.warning("Nenhum dado de métrica encontrado. Sincronize os dados na aba 'Dados & Logs'.")
    else:
        # --- Filtros Globais ---
        # Aplicados uma única vez, aqui, e propagados para todas as abas. Garante que dois
        # gráficos lado a lado estejam sempre olhando para o mesmo recorte.
        data_min, data_max = dashboard_analyzer.get_date_bounds(df_metrics)
        opcoes_filtro = dashboard_analyzer.get_filter_options(df_metrics)

        with st.container(border=True):
            fc1, fc2, fc3 = st.columns([2, 1, 1])
            with fc1:
                preset = st.radio(
                    "Período:",
                    ["7 dias", "30 dias", "90 dias", "Tudo", "Personalizado"],
                    index=1, horizontal=True,
                )
                if preset == "Personalizado":
                    intervalo = st.date_input(
                        "Intervalo:", value=(data_min, data_max),
                        min_value=data_min, max_value=data_max, format="DD/MM/YYYY",
                    )
                    # date_input com intervalo devolve uma tupla de 1 elemento enquanto o
                    # usuário ainda não escolheu a segunda data.
                    if isinstance(intervalo, (list, tuple)) and len(intervalo) == 2:
                        data_inicial, data_final = intervalo
                    else:
                        data_inicial, data_final = data_min, data_max
                elif preset == "Tudo":
                    data_inicial, data_final = data_min, data_max
                else:
                    dias = {"7 dias": 7, "30 dias": 30, "90 dias": 90}[preset]
                    data_final = data_max
                    data_inicial = max(data_min, data_final - timedelta(days=dias - 1))
                    st.caption(f"De {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}")

            with fc2:
                granularidade = st.selectbox("Agrupar por:", ["Dia", "Semana", "Mês"], index=0)
                usuarios_disponiveis = sorted(df_metrics['user_name'].dropna().unique())
                usuarios_sel = st.multiselect(
                    "Usuário(s):", options=usuarios_disponiveis, placeholder="Todos os usuários",
                )
            with fc3:
                modelos_sel = st.multiselect(
                    "Modelo(s):", options=opcoes_filtro["modelos"], placeholder="Todos os modelos",
                )
                provedores_sel = st.multiselect(
                    "Provedor(es):", options=opcoes_filtro["provedores"], placeholder="Todos os provedores",
                )

        uids_sel = [uid for uid, nome in user_id_to_name_map.items() if nome in usuarios_sel]
        # Usuários presentes nas métricas mas ausentes do Auth são rotulados pelo próprio UID.
        uids_sel += [u for u in usuarios_sel if u not in user_id_to_name_map.values()]

        df_filtered = dashboard_analyzer.apply_filters(
            df_metrics, data_inicial, data_final,
            user_ids=uids_sel or None,
            modelos=modelos_sel or None,
            provedores=provedores_sel or None,
        )

        long_feedback = feedback_analyzer.build_feedback_long_table(df_filtered, user_id_to_name_map)
        exibir_custo = dashboard_analyzer.has_cost_data(df_filtered)

        tab_uso, tab_fb_geral, tab_fb_detalhe = st.tabs(
            ["📈 Uso", "🎯 Feedback — Visão Geral", "🔍 Feedback — Detalhe"]
        )

        # ==================== ABA 1: USO ====================
        with tab_uso:
            kpis = dashboard_analyzer.calculate_kpis(df_filtered)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Requisições", f"{kpis['total_requests']:,}".replace(",", "."),
                      help="Análises de PDF + mensagens de chat")
            c2.metric("Usuários Ativos", f"{kpis['active_users']:,}".replace(",", "."))
            c3.metric("Documentos", f"{kpis['total_documents']:,}".replace(",", "."))
            c4.metric("Páginas Processadas", f"{kpis['total_pages']:,}".replace(",", "."))
            c5.metric("Tempo Médio", f"{kpis['avg_response_seconds']:.0f}s")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Análises de PDF", f"{kpis['total_analyses']:,}".replace(",", "."))
            c2.metric("Mensagens de Chat", f"{kpis['total_chats']:,}".replace(",", "."))
            c3.metric("Tokens de Entrada", f"{kpis['input_tokens']:,}".replace(",", "."))
            c4.metric("Tokens de Saída", f"{kpis['output_tokens']:,}".replace(",", "."))
            # Custo só ocupa espaço quando existe: o uso atual é majoritariamente do provedor
            # interno (LLM_PF), de custo zero.
            if exibir_custo:
                c5.metric("Custo Total (USD)", f"${kpis['total_cost_usd']:.2f}",
                          help=f"Média de ${kpis['avg_cost_per_request']:.4f} por requisição")

            st.markdown("---")

            st.plotly_chart(
                dashboard_plotter.create_requests_by_user_chart(
                    dashboard_analyzer.prepare_requests_by_period_and_user(df_filtered, granularidade),
                    granularidade,
                ),
                use_container_width=True,
            )

            if exibir_custo:
                g1, g2 = st.columns(2)
                with g1:
                    st.plotly_chart(
                        dashboard_plotter.create_token_usage_chart(
                            dashboard_analyzer.prepare_token_usage_by_period(df_filtered, granularidade),
                            granularidade),
                        use_container_width=True)
                with g2:
                    st.plotly_chart(
                        dashboard_plotter.create_costs_chart(
                            dashboard_analyzer.prepare_cost_data(df_filtered, granularidade),
                            granularidade),
                        use_container_width=True)
                st.plotly_chart(
                    dashboard_plotter.create_cost_by_model_chart(
                        dashboard_analyzer.prepare_cost_by_model(df_filtered)),
                    use_container_width=True)
            else:
                st.plotly_chart(
                    dashboard_plotter.create_token_usage_chart(
                        dashboard_analyzer.prepare_token_usage_by_period(df_filtered, granularidade),
                        granularidade),
                    use_container_width=True)
                st.caption(
                    "💡 Indicadores de custo ocultos: nenhuma requisição do período teve custo "
                    "registrado (uso do provedor interno)."
                )

            st.plotly_chart(
                dashboard_plotter.create_user_period_heatmap(
                    dashboard_analyzer.prepare_user_period_heatmap(df_filtered, granularidade),
                    granularidade),
                use_container_width=True)

            st.subheader("Atividade por Usuário")
            tabela_usuarios = dashboard_analyzer.prepare_user_activity_table(df_filtered)
            colunas_usuario = {
                "Custo (USD)": st.column_config.NumberColumn(format="$%.4f"),
                "Última Atividade": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            }
            if not exibir_custo and "Custo (USD)" in tabela_usuarios.columns:
                tabela_usuarios = tabela_usuarios.drop(columns=["Custo (USD)"])
                colunas_usuario.pop("Custo (USD)")
            st.dataframe(tabela_usuarios, use_container_width=True, hide_index=True,
                         column_config=colunas_usuario)

            st.subheader("Uso por Modelo")
            tabela_modelos = dashboard_analyzer.prepare_model_usage(df_filtered)
            colunas_modelo = {
                "Custo (USD)": st.column_config.NumberColumn(format="$%.4f"),
                "Tempo Médio (s)": st.column_config.NumberColumn(format="%.1f s"),
            }
            if not exibir_custo and "Custo (USD)" in tabela_modelos.columns:
                tabela_modelos = tabela_modelos.drop(columns=["Custo (USD)"])
                colunas_modelo.pop("Custo (USD)")
            st.dataframe(tabela_modelos, use_container_width=True, hide_index=True,
                         column_config=colunas_modelo)

        # ==================== ABA 2: FEEDBACK — VISÃO GERAL ====================
        with tab_fb_geral:
            kpis_uso = dashboard_analyzer.calculate_kpis(df_filtered)
            kpis_fb = feedback_analyzer.calculate_feedback_kpis(long_feedback, kpis_uso['total_analyses'])

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Feedbacks Recebidos", f"{kpis_fb['total_feedbacks']:,}".replace(",", "."))
            c2.metric("Taxa de Retorno", f"{kpis_fb['taxa_retorno']:.1%}",
                      help="Proporção de análises de PDF que receberam avaliação do usuário")
            c3.metric("Taxa de Acerto", f"{kpis_fb['taxa_acerto']:.1%}",
                      help="Campos não editados pelo usuário sobre o total de campos avaliados")
            c4.metric("Campos Avaliados", f"{kpis_fb['total_campos']:,}".replace(",", "."))
            c5.metric("Reanálises Solicitadas", f"{kpis_fb['total_reanalises']:,}".replace(",", "."))

            if long_feedback.empty:
                st.info("Nenhum feedback registrado no período e nos filtros selecionados.")
            else:
                st.markdown("---")
                st.plotly_chart(
                    dashboard_plotter.create_requests_by_user_chart(
                        dashboard_analyzer.prepare_events_by_period_and_user(
                            df_filtered, "llm_feedback", granularidade),
                        granularidade,
                        value_col="eventos",
                        title="Feedbacks por período e usuário",
                        yaxis_title="Feedbacks",
                    ),
                    use_container_width=True)

                st.plotly_chart(
                    dashboard_plotter.create_feedback_score_chart(
                        feedback_analyzer.prepare_accuracy_by_period(long_feedback, granularidade)),
                    use_container_width=True)

                st.plotly_chart(
                    dashboard_plotter.create_accuracy_by_field_chart(
                        feedback_analyzer.prepare_accuracy_by_field(long_feedback)),
                    use_container_width=True)

                min_amostras = st.slider(
                    "Mínimo de avaliações por célula (campo × modelo):",
                    min_value=1, max_value=30, value=5,
                    help="Células com menos avaliações ficam em branco, evitando concluir a "
                         "partir de uma ou duas ocorrências.",
                )
                st.plotly_chart(
                    dashboard_plotter.create_accuracy_heatmap(
                        feedback_analyzer.prepare_accuracy_by_field_and_model(
                            long_feedback, min_amostras)),
                    use_container_width=True)

        # ==================== ABA 3: FEEDBACK — DETALHE ====================
        with tab_fb_detalhe:
            if long_feedback.empty:
                st.info("Nenhum feedback registrado no período e nos filtros selecionados.")
            else:
                sub_erros, sub_tabela, sub_confusao = st.tabs(
                    ["Erros recorrentes", "Tabela completa", "Matriz de confusão"]
                )

                # --- Erros recorrentes: leitura acionável dos valores corrigidos ---
                with sub_erros:
                    st.markdown(
                        "Cada linha é uma classificação que a IA errou e a correção que o "
                        "usuário aplicou. É o insumo direto para ajuste de prompt e das listas "
                        "de opções."
                    )
                    confusoes = feedback_analyzer.prepare_top_confusions(long_feedback, top_n=30)
                    if confusoes.empty:
                        st.warning(
                            "Nenhum par 'resposta da IA → correção' disponível no recorte. "
                            "Os valores só passaram a ser gravados novamente a partir da versão "
                            "que restaurou a persistência para campos de valor único; "
                            "registros anteriores guardam apenas qual campo foi corrigido."
                        )
                    else:
                        st.dataframe(confusoes, use_container_width=True, hide_index=True)

                # --- Tabela completa: uma linha por (feedback, campo) ---
                with sub_tabela:
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        campos_sel = st.multiselect(
                            "Campo(s):", options=sorted(long_feedback['campo'].dropna().unique()),
                            placeholder="Todos os campos")
                    with fc2:
                        situacao = st.radio("Situação:", ["Todos", "Apenas corrigidos", "Apenas corretos"],
                                            horizontal=True)

                    detalhe = long_feedback.copy()
                    if campos_sel:
                        detalhe = detalhe[detalhe['campo'].isin(campos_sel)]
                    if situacao == "Apenas corrigidos":
                        detalhe = detalhe[~detalhe['acertou']]
                    elif situacao == "Apenas corretos":
                        detalhe = detalhe[detalhe['acertou']]

                    exibicao = detalhe[[
                        'timestamp', 'user_name', 'arquivo', 'campo', 'acertou',
                        'valor_llm', 'valor_corrigido', 'similaridade', 'modelo', 'provedor',
                    ]].rename(columns={
                        'timestamp': 'Data/Hora', 'user_name': 'Usuário', 'arquivo': 'Arquivo',
                        'campo': 'Campo', 'acertou': 'Acertou', 'valor_llm': 'Resposta da IA',
                        'valor_corrigido': 'Corrigido para', 'similaridade': 'Aproveitamento',
                        'modelo': 'Modelo', 'provedor': 'Provedor',
                    }).sort_values('Data/Hora', ascending=False)

                    st.caption(f"{len(exibicao):,} campos avaliados no recorte.".replace(",", "."))
                    st.dataframe(
                        exibicao, use_container_width=True, hide_index=True, height=460,
                        column_config={
                            "Data/Hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                            "Acertou": st.column_config.CheckboxColumn(),
                            "Aproveitamento": st.column_config.ProgressColumn(
                                format="%.0f%%", min_value=0, max_value=1),
                        })

                    output_fb = io.BytesIO()
                    # Reusa o mesmo escritor da aba "Dados & Logs" — aceita um buffer no lugar
                    # de um caminho, já que pandas.to_excel trata ambos.
                    export_data.export_data_to_excel(exibicao.to_dict(orient="records"), output_fb)
                    st.download_button(
                        "Exportar para Excel", data=output_fb.getvalue(),
                        file_name=f"feedback_detalhado_{data_inicial:%Y%m%d}_{data_final:%Y%m%d}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                    st.markdown("---")
                    st.subheader("Submissões de Feedback")
                    st.caption("Selecione uma linha para ver a avaliação campo a campo.")
                    submissoes = feedback_analyzer.prepare_submission_table(long_feedback)
                    evento = st.dataframe(
                        submissoes.drop(columns=['doc_id']),
                        use_container_width=True, hide_index=True, height=280,
                        on_select="rerun", selection_mode="single-row",
                        column_config={
                            "Data/Hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                            "Taxa de Acerto": st.column_config.ProgressColumn(
                                format="%.0f%%", min_value=0, max_value=1),
                            "Reanálise": st.column_config.CheckboxColumn(),
                        })

                    linhas_sel = evento.selection.rows if evento and evento.selection else []
                    if linhas_sel:
                        doc_id = submissoes.iloc[linhas_sel[0]]['doc_id']
                        campos_doc = long_feedback[long_feedback['doc_id'] == doc_id]
                        cabecalho = campos_doc.iloc[0]

                        st.markdown(
                            f"**{cabecalho['user_name']}** · {cabecalho['timestamp']:%d/%m/%Y %H:%M} · "
                            f"`{cabecalho['modelo'] or 'N/D'}` · {cabecalho['arquivo']}"
                        )
                        col_ok, col_erro = st.columns(2)
                        with col_ok:
                            st.markdown("**✅ Respostas mantidas**")
                            for _, campo in campos_doc[campos_doc['acertou']].iterrows():
                                st.markdown(f"- {campo['campo']}")
                        with col_erro:
                            st.markdown("**✏️ Respostas corrigidas**")
                            corrigidos = campos_doc[~campos_doc['acertou']]
                            if corrigidos.empty:
                                st.caption("Nenhuma correção nesta submissão.")
                            for _, campo in corrigidos.iterrows():
                                if pd.notna(campo['valor_llm']) and pd.notna(campo['valor_corrigido']):
                                    st.markdown(
                                        f"- **{campo['campo']}**  \n"
                                        f"  `{campo['valor_llm']}` → `{campo['valor_corrigido']}`")
                                elif pd.notna(campo['similaridade']):
                                    st.markdown(
                                        f"- **{campo['campo']}** — texto editado "
                                        f"(aproveitamento {campo['similaridade']:.0%})")
                                else:
                                    st.markdown(f"- **{campo['campo']}** — editado")

                # --- Matriz de confusão por campo ---
                with sub_confusao:
                    campos_com_valor = feedback_analyzer.get_fields_with_values(long_feedback)
                    if campos_com_valor.empty:
                        st.warning(
                            "Nenhum campo do recorte possui valores registrados. A matriz de "
                            "confusão depende do par 'resposta da IA / correção', preservado "
                            "apenas para campos de valor único (listas fechadas e numéricos); "
                            "campos de texto livre têm os valores descartados na origem por "
                            "conterem conteúdo do documento analisado."
                        )
                    else:
                        rotulos = {
                            f"{linha['campo']} ({linha['com_valor']} avaliações)": linha['nome_campo']
                            for _, linha in campos_com_valor.iterrows()
                        }
                        escolhido = st.selectbox("Campo:", options=list(rotulos.keys()))
                        nome_campo = rotulos[escolhido]
                        matriz = feedback_analyzer.build_confusion_matrix(long_feedback, nome_campo)
                        st.plotly_chart(
                            dashboard_plotter.create_confusion_heatmap(
                                matriz, escolhido.split(" (")[0]),
                            use_container_width=True)
                        st.caption(
                            "A diagonal são os acertos. Células fora dela concentram as confusões "
                            "recorrentes do modelo."
                        )

elif page == "Dados & Logs":
    st.title("📄 Sincronização e Visualização de Dados")

    if st.button("Sincronizar Dados da Nuvem Agora", type="primary"):
        with st.spinner("Sincronizando logs e métricas... Isso pode levar alguns minutos."):
            success, message = local_data_manager.sync_cloud_data_to_local()
        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(message)
    
    st.markdown("---")
    st.header("Visualizador de Logs e Métricas")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        user_options = {"Todos os Usuários": "ALL"}
        user_options.update({name: uid for name, uid in local_data_manager.get_available_users(user_id_to_name_map)})
        selected_user_name = st.selectbox("Filtrar por Usuário:", options=user_options.keys())
        selected_user_uid = user_options[selected_user_name]
    with c2:
        selected_type = st.selectbox("Filtrar por Tipo:", ["Todos", "Logs", "Métricas"])
    with c3:
        selected_level = st.selectbox("Filtrar por Nível de Log:", ["ALL", "INFO", "WARNING", "ERROR", "CRITICAL"])
    with c4:
        selected_date = st.date_input("Filtrar por Data:", value=date.today())

    filtered_data = local_data_manager.get_filtered_logs(
        selected_user_uid, selected_level, selected_date, selected_type, user_id_to_name_map
    )

    if not filtered_data:
        st.info("Nenhuma entrada encontrada para os filtros selecionados.")
    else:
        export_df_data = export_data.process_filtered_data_for_export(selected_user_uid, selected_level, selected_date, selected_type.lower(), user_id_to_name_map)
        if export_df_data:
            output = io.BytesIO()
            export_data.export_data_to_excel(export_df_data, output)
            st.download_button(
                label="Exportar para Excel",
                data=output.getvalue(),
                file_name=f"relatorio_filtrado_{selected_date.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        st.text(f"Exibindo {len(filtered_data)} entradas:")
        with st.container(height=600):
            for entry in filtered_data:
                color = "green" if entry['type'] == 'metric' else "blue"
                with st.expander(f":{color}[{entry['user_name']} - {entry['type'].upper()}] - {entry['content'][:100]}"):
                    st.code(entry['content'], language='log')

elif page == "Usuários":
    st.title("👥 Gerenciamento de Usuários")
    
    from SOURCE.services.firebase_manager import FbManagerAdminAuth
    auth_manager = FbManagerAdminAuth()

    users_list = []
    try:
        for user in auth_manager.list_users().iterate_all():
            users_list.append({
                "Email": user.email, "Nome": user.display_name, "UID": user.uid,
                "Admin": user.custom_claims.get('admin', False) if user.custom_claims else False
            })
    except Exception as e:
        st.error(f"Erro ao carregar lista de usuários: {e}")

    if users_list:
        df_users = pd.DataFrame(users_list)
        st.dataframe(df_users, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Gerar Links Manuais (Autenticação)")
        link_type = st.radio("Tipo de Link:", ["Verificação de Email", "Redefinição de Senha"], horizontal=True)
        target_email = st.text_input(
            "Email do usuário para gerar o link:",
            placeholder="Digite o e-mail do usuário alvo"
        )
        if st.button("Gerar Link Manualmente"):
            if target_email:
                with st.spinner(f"Gerando link para {target_email}..."):
                    if link_type == "Verificação de Email":
                        success, result = user_verification.generate_verification_link(target_email)
                    else:
                        success, result = user_verification.generate_password_reset_link(target_email)
                if success:
                    st.success("Link gerado com sucesso! Copie e envie para o usuário.")
                    st.code(result, language=None)
                else:
                    st.error(f"Falha ao gerar o link: {result}")

        st.subheader("Alterar Status de Administrador")
        selected_email = st.selectbox("Selecione o email do usuário:", options=[u['Email'] for u in users_list])
        
        current_admin_status = next((u['Admin'] for u in users_list if u['Email'] == selected_email), False)
        is_admin = st.checkbox("Tornar este usuário um administrador?", value=current_admin_status)
        
        if st.button("Aplicar Alteração", type="primary"):
            with st.spinner(f"Alterando status para {selected_email}..."):
                success = set_user_admin_status(selected_email, is_admin)
            if success:
                st.success(f"Status de administrador para {selected_email} atualizado para {is_admin}!")
                st.rerun()
            else:
                st.error("Falha ao alterar o status do usuário.")

elif page == "Configurações":
    st.title("⚙️ Configurações da Aplicação")
    from SOURCE.services.firebase_manager import FbManagerFirestore
    fs_manager_admin = FbManagerFirestore()

    with st.expander("Manutenção", expanded=True):
        if st.button("Atualizar Cache da Lista de Usuários"):
            get_user_map.clear()
            st.success("Cache da lista de usuários limpo. A lista será recarregada na próxima vez que o dashboard for acessado.")

    with st.expander("Gerenciar Provedores LLM"):
        st.markdown("Edite a lista de provedores e modelos em formato JSON. A alteração afeta todos os usuários.")
        
        current_providers = admin_llm_providers.read_providers_from_firestore(fs_manager_admin)
        json_text = json.dumps(current_providers, indent=2, ensure_ascii=False)
        
        edited_json = st.text_area("Configuração de Provedores (JSON):", value=json_text, height=300)

        if st.button("Salvar Alterações nos Provedores", type="primary"):
            try:
                new_providers_list = json.loads(edited_json)
                with st.spinner("Salvando configuração..."):
                    success = admin_llm_providers.write_providers_to_firestore(fs_manager_admin, new_providers_list)
                if success:
                    st.success("Configuração de provedores salva com sucesso!")
                else:
                    st.error("Falha ao salvar a configuração no Firestore.")
            except json.JSONDecodeError:
                st.error("O texto fornecido não é um JSON válido.")

    with st.expander("Gerenciar Templates de Prompt"):
        st.markdown("Esta ação sobrescreverá os prompts base no banco de dados com a versão definida no código do projeto (`repo_prompts.py`).")
        if st.button("Fazer Upload dos Templates", disabled=True):
            with st.spinner("Enviando templates..."):
                success = upload_prompts.upload_prompt_templates()
            if success:
                st.success("Templates de prompt enviados com sucesso!")
            else:
                st.error("Falha ao enviar templates.")

    with st.expander("Limpeza de Logs na Nuvem"):
        st.markdown("Remove arquivos de log antigos do Firebase Storage para controlar custos.")
        
        days_to_keep = st.number_input("Manter logs dos últimos (dias):", min_value=1, value=30, step=1)
        
        if st.button("Verificar Logs na Nuvem"):
            with st.spinner("Verificando estatísticas de logs..."):
                stats = cleanup_cloud_logs.get_cloud_log_stats(days_to_keep)
            if "error" in stats:
                st.error(stats["error"])
            else:
                st.metric("Total de Arquivos de Log", stats.get('total_count', 0))
                st.metric(f"Arquivos com Mais de {days_to_keep} Dias", stats.get('old_count', 0))

        st.markdown("---")
        is_dry_run = st.checkbox("Apenas simular (não deletar)", value=True)
        if st.button("Executar Limpeza", type="secondary"):
            with st.spinner("Executando limpeza de logs..."):
                success = cleanup_cloud_logs.run_cloud_log_cleanup(days_to_keep, is_dry_run)
            if success:
                st.success("Operação de limpeza concluída. Verifique os logs do console para detalhes.")
            else:
                st.error("Operação de limpeza falhou.")


# streamlit run run_admin_streamlit.py --logger.level INFO

