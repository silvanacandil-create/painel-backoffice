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

USUARIOS = st.secrets["USUARIOS"]

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None

if not st.session_state.autenticado:

    col1, col2, col3 = st.columns([3, 1, 3])

    with col2:

        st.markdown("<br><br>", unsafe_allow_html=True)

        st.title("🔐 Painel Backoffice")

        with st.form("login_form"):

            usuario = st.text_input(
                "Usuário",
                placeholder="Digite seu usuário"
            )

            senha = st.text_input(
                "Senha",
                type="password",
                placeholder="Digite sua senha"
            )

            entrar = st.form_submit_button(
                "Entrar",
                use_container_width=True
            )

            if entrar:

                if usuario in USUARIOS and senha == USUARIOS[usuario]:

                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = usuario

                    st.rerun()

                else:
                    st.error("Usuário ou senha incorretos.")

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

st.sidebar.success(
)

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
