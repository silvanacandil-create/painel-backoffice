import streamlit as st
import pandas as pd
from datetime import datetime
import time

st.set_page_config(
    page_title="Painel Backoffice",
    page_icon="📊",
    layout="wide"
)

# =========================
# SENHA
# =========================

SENHA_CORRETA = "produttivo123"

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acesso ao Painel Backoffice")

    senha = st.text_input("Digite a senha de acesso:", type="password")

    if st.button("Entrar"):
        if senha == SENHA_CORRETA:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")

    st.stop()

# =========================
# AUTO REFRESH
# =========================

if "ultima_atualizacao" not in st.session_state:
    st.session_state.ultima_atualizacao = datetime.now()

if "ultimo_refresh" not in st.session_state:
    st.session_state.ultimo_refresh = time.time()

# Atualiza automaticamente a cada 5 minutos
if time.time() - st.session_state.ultimo_refresh > 300:
    st.session_state.ultimo_refresh = time.time()
    st.session_state.ultima_atualizacao = datetime.now()
    st.rerun()

# =========================
# MENU
# =========================

st.sidebar.title("Menu")

pagina = st.sidebar.radio(
    "Escolha uma opção:",
    [
        "Dashboard",
        "Clientes",
        "NFS-e",
        "Financeiro",
        "Automações"
    ]
)

# =========================
# PAINEL
# =========================

st.title("📊 Painel Backoffice")

col_atualizar, col_horario = st.columns([1, 3])

with col_atualizar:
    if st.button("🔄 Atualizar agora"):
        st.session_state.ultimo_refresh = time.time()
        st.session_state.ultima_atualizacao = datetime.now()
        st.rerun()

with col_horario:
    st.caption(
        f"Última atualização: "
        f"{st.session_state.ultima_atualizacao.strftime('%d/%m/%Y %H:%M:%S')}"
    )

if pagina == "Dashboard":

    st.header("Indicadores Gerais")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Notas com erro", 0)

    with col2:
        st.metric("Clientes inadimplentes", 0)

    with col3:
        st.metric("Automações ativas", 0)

elif pagina == "Clientes":

    st.header("Clientes")
    st.write("Área de gerenciamento de clientes.")

elif pagina == "NFS-e":

    st.header("NFS-e")
    st.write("Área de controle de notas fiscais.")

elif pagina == "Financeiro":

    st.header("Financeiro")
    st.write("Área financeira.")

elif pagina == "Automações":

    st.header("Automações")
    st.write("Área de automações.")
