import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Painel Backoffice",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Painel Backoffice")

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