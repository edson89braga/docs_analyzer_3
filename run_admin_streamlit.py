# run_admin_streamlit.py
import streamlit as st
import pandas as pd
import io, json
from datetime import datetime, date

# Configuração do Logger (deve ser a primeira coisa)
from src.logger.logger import LoggerSetup
LoggerSetup.initialize(routine_name="Admin_Dashboard_Streamlit", dev_mode=True)

# Imports dos módulos de lógica admin
from admin_py import dashboard_analyzer, dashboard_plotter, local_data_manager, export_data
from admin_py import admin_llm_providers, upload_prompts, cleanup_cloud_logs
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
        # --- Filtros ---
        st.markdown("---")
        
        filter_cols = st.columns([3, 2])
        with filter_cols[0]:
            available_users = local_data_manager.get_available_users(user_id_to_name_map)
            valid_user_names = [name for name, uid in available_users if uid in user_id_to_name_map]
            user_options = {name: uid for name, uid in available_users if name in valid_user_names}
            selected_user_names = st.multiselect("Filtrar por Usuário(s):", options=sorted(user_options.keys()), placeholder="Todos os Usuários")
        with filter_cols[1]:
            period_days = st.radio(
                "Selecione o Período:",
                [7, 30, 9999],
                format_func=lambda x: "Últimos 7 Dias" if x==7 else "Últimos 30 Dias" if x==30 else "Desde o Início",
                horizontal=True,
            )
        # --- Filtragem de Dados ---
        df_filtered = df_metrics.copy()
        if selected_user_names:
            selected_uids = [user_options[name] for name in selected_user_names]
            df_filtered = df_filtered[df_filtered['user_id'].isin(selected_uids)]

        # --- Seção de KPIs ---
        st.markdown("---")
        kpis = dashboard_analyzer.calculate_kpis(df_filtered, user_id_to_name_map, period_days)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total de Usuários", f"{kpis['total_users']:,}")
        c2.metric("Análises Realizadas", f"{kpis['total_analyses']:,}")
        c3.metric("Feedbacks Recebidos", f"{kpis['total_feedbacks']:,}")
        c4.metric("Custo Total (USD)", f"${kpis['total_cost_usd']:.2f}")
        c5.metric("Custo Médio/Análise", f"${kpis['avg_cost_per_analysis']:.4f}")
        st.markdown("---")
        
        # --- Seção de Uso e Custos ---
        st.header("Análise de Uso e Custos")
        usage_data = dashboard_analyzer.prepare_usage_data(df_filtered, period_days)
        costs_data = dashboard_analyzer.prepare_cost_data(df_filtered, period_days) # Esta já estava correta
        cost_dist_data = dashboard_analyzer.prepare_cost_distribution_data(df_filtered, period_days)
        c1, c2, c3 = st.columns(3)
        with c1: st.plotly_chart(dashboard_plotter.create_usage_chart(usage_data), use_container_width=True)
        with c2: st.plotly_chart(dashboard_plotter.create_costs_chart(costs_data), use_container_width=True)
        with c3: st.plotly_chart(dashboard_plotter.create_cost_distribution_pie(cost_dist_data), use_container_width=True)

        # --- Seção de Qualidade da IA ---
        st.header("Análise de Qualidade da IA")
        feedback_score_data = dashboard_analyzer.prepare_feedback_quality_data(df_filtered, period_days)
        top_edited_data = dashboard_analyzer.prepare_top_edited_fields_data(df_filtered, period_days)
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(dashboard_plotter.create_feedback_score_chart(feedback_score_data), use_container_width=True)
        with c2: st.plotly_chart(dashboard_plotter.create_top_edited_fields_chart(top_edited_data), use_container_width=True)

        # --- Seção Tabela de Atividade por Usuário ---
        st.markdown("---")
        st.header("Atividade por Usuário")
        user_activity_data = dashboard_analyzer.prepare_user_activity_table(df_filtered, user_id_to_name_map, period_days)
        st.dataframe(user_activity_data, use_container_width=True, hide_index=True,
                      column_config={
                          "Custo (USD)": st.column_config.NumberColumn(format="$%.4f"),
                          "Última Atividade": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")
                      })

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
    
    from src.services.firebase_manager import FbManagerAdminAuth
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
    from src.services.firebase_manager import FbManagerFirestore
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

