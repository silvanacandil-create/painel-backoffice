import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
import time

from pages_inadimplencia import exibir_inadimplencia
from pages_inadimplencia_anual import exibir_inadimplencia_anual

st.set_page_config(
    page_title="Painel Backoffice",
    page_icon="📊",
    layout="wide"
)

SENHA_CORRETA = st.secrets["SENHA_PAINEL"]

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso ao Painel Backoffice")
    senha = st.text_input("Digite a senha:", type="password")

    if st.button("Entrar"):
        if senha == SENHA_CORRETA:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")

    st.stop()

if "ultima_atualizacao" not in st.session_state:
    st.session_state.ultima_atualizacao = datetime.now(ZoneInfo("America/Sao_Paulo"))

if "ultimo_refresh" not in st.session_state:
    st.session_state.ultimo_refresh = time.time()

if time.time() - st.session_state.ultimo_refresh > 300:
    st.session_state.ultimo_refresh = time.time()
    st.session_state.ultima_atualizacao = datetime.now(ZoneInfo("America/Sao_Paulo"))
    st.rerun()

if "mes_offset" not in st.session_state:
    st.session_state.mes_offset = 0

st.sidebar.title("Menu")

pagina = st.sidebar.radio(
    "Escolha uma opção:",
    ["Dashboard", "Inadimplência Mensal", "Inadimplência Anual"]
)

st.title("📊 Painel Backoffice")

col_atualizar, col_horario = st.columns([1, 4])

with col_atualizar:
    if st.button("🔄 Atualizar agora"):
        st.session_state.ultimo_refresh = time.time()
        st.session_state.ultima_atualizacao = datetime.now(ZoneInfo("America/Sao_Paulo"))
        st.rerun()

with col_horario:
    st.caption(
        f"Última atualização: "
        f"{st.session_state.ultima_atualizacao.strftime('%d/%m/%Y %H:%M:%S')}"
    )

if pagina == "Dashboard":
    st.header("Dashboard")
    st.write("Painel geral do Backoffice.")

elif pagina == "Inadimplência Mensal":
    exibir_inadimplencia()

elif pagina == "Inadimplência Anual":
    exibir_inadimplencia_anual()
