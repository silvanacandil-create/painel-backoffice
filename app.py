import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit_cookies_controller import CookieController

from pages_fluxo_caixa import render
from pages_inadimplencia import exibir_inadimplencia
from pages_inadimplencia_anual import exibir_inadimplencia_anual
from pages_indicadores_cs import exibir_indicadores_cs
from services_pipefy import buscar_cards_pipefy


st.set_page_config(
    page_title="Painel Backoffice",
    page_icon="📊",
    layout="wide",
)


FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
NOME_COOKIE_LOGIN = "painel_backoffice_login_diario"
USUARIOS = dict(st.secrets["USUARIOS"])


# A assinatura impede que alguém altere manualmente o usuário ou a data do cookie.
def _chave_assinatura_login():
    conteudo = json.dumps(USUARIOS, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(conteudo.encode("utf-8")).digest()


def _criar_token_login(usuario):
    data_atual = datetime.now(FUSO_HORARIO).date().isoformat()
    conteudo = f"{usuario}|{data_atual}"
    assinatura = hmac.new(
        _chave_assinatura_login(),
        conteudo.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{conteudo}|{assinatura}"


def _validar_token_login(token):
    if not token:
        return None

    try:
        usuario, data_token, assinatura_recebida = token.split("|", 2)
    except ValueError:
        return None

    if usuario not in USUARIOS:
        return None

    data_atual = datetime.now(FUSO_HORARIO).date().isoformat()
    if data_token != data_atual:
        return None

    conteudo = f"{usuario}|{data_token}"
    assinatura_esperada = hmac.new(
        _chave_assinatura_login(),
        conteudo.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(assinatura_recebida, assinatura_esperada):
        return None

    return usuario


def _segundos_ate_fim_do_dia():
    agora = datetime.now(FUSO_HORARIO)
    proxima_meia_noite = datetime.combine(
        agora.date() + timedelta(days=1),
        datetime.min.time(),
        tzinfo=FUSO_HORARIO,
    )
    return max(60, int((proxima_meia_noite - agora).total_seconds()))


# O componente mantém a validação no navegador mesmo após atualizar ou fechar a aba.
controlador_cookies = CookieController(key="cookie_login_backoffice")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None

# Ao iniciar uma nova sessão, tenta restaurar o login válido do mesmo dia.
if not st.session_state.autenticado:
    token_cookie = controlador_cookies.get(NOME_COOKIE_LOGIN)
    usuario_cookie = _validar_token_login(token_cookie)

    if usuario_cookie:
        st.session_state.autenticado = True
        st.session_state.usuario_logado = usuario_cookie


if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([2, 1, 2])

    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔐 Painel Backoffice")
        st.caption("A validação será solicitada uma vez por dia neste navegador.")

        with st.form("login_form"):
            usuario = st.text_input(
                "Usuário",
                placeholder="Digite seu usuário",
            )

            senha = st.text_input(
                "Senha",
                type="password",
                placeholder="Digite sua senha",
            )

            entrar = st.form_submit_button(
                "Entrar",
                width="stretch",
            )

            if entrar:
                usuario = usuario.strip()

                if usuario in USUARIOS and hmac.compare_digest(
                    str(senha), str(USUARIOS[usuario])
                ):
                    token = _criar_token_login(usuario)
                    controlador_cookies.set(
                        NOME_COOKIE_LOGIN,
                        token,
                        max_age=_segundos_ate_fim_do_dia(),
                        same_site="strict",
                        secure=True,
                    )
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = usuario
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

    st.stop()


if "ultima_atualizacao" not in st.session_state:
    st.session_state.ultima_atualizacao = datetime.now(FUSO_HORARIO)

if "ultimo_refresh" not in st.session_state:
    st.session_state.ultimo_refresh = time.time()

if time.time() - st.session_state.ultimo_refresh > 300:
    st.session_state.ultimo_refresh = time.time()
    st.session_state.ultima_atualizacao = datetime.now(FUSO_HORARIO)
    st.rerun()

if "mes_offset" not in st.session_state:
    st.session_state.mes_offset = 0


st.sidebar.title("Menu")
st.sidebar.caption(f"Usuário: {st.session_state.usuario_logado}")

if st.sidebar.button("Sair", use_container_width=True):
    controlador_cookies.remove(NOME_COOKIE_LOGIN)
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None
    time.sleep(0.5)
    st.rerun()

pagina = st.sidebar.radio(
    "Escolha uma opção:",
    [
        "Dashboard",
        "Fluxo de Caixa",
        "Inadimplência Mensal",
        "Inadimplência Anual",
        "Indicadores para CS",
    ],
)

st.title("📊 Painel Backoffice")

col_atualizar, col_horario = st.columns([1, 4])

with col_atualizar:
    if st.button("🔄 Atualizar agora"):
        buscar_cards_pipefy.clear()
        st.session_state.ultimo_refresh = time.time()
        st.session_state.ultima_atualizacao = datetime.now(FUSO_HORARIO)
        st.rerun()

with col_horario:
    st.caption(
        "Última atualização: "
        f"{st.session_state.ultima_atualizacao.strftime('%d/%m/%Y %H:%M:%S')}"
    )


if pagina == "Dashboard":
    st.header("Dashboard")
    st.write("Painel geral do Backoffice.")

elif pagina == "Fluxo de Caixa":
    render()

elif pagina == "Inadimplência Mensal":
    exibir_inadimplencia()

elif pagina == "Inadimplência Anual":
    exibir_inadimplencia_anual()

elif pagina == "Indicadores para CS":
    exibir_indicadores_cs()
