import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import requests

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
    st.session_state.ultima_atualizacao = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    )

if "ultimo_refresh" not in st.session_state:
    st.session_state.ultimo_refresh = time.time()

if time.time() - st.session_state.ultimo_refresh > 300:
    st.session_state.ultimo_refresh = time.time()
    st.session_state.ultima_atualizacao = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    )
    st.rerun()

if "mes_offset" not in st.session_state:
    st.session_state.mes_offset = 0

st.sidebar.title("Menu")

pagina = st.sidebar.radio(
    "Escolha uma opção:",
    [
        "Dashboard",
        "Inadimplência"
    ]
)

st.title("📊 Painel Backoffice")

col_atualizar, col_horario = st.columns([1, 4])

with col_atualizar:
    if st.button("🔄 Atualizar agora"):
        st.session_state.ultimo_refresh = time.time()
        st.session_state.ultima_atualizacao = datetime.now(
            ZoneInfo("America/Sao_Paulo")
        )
        st.rerun()

with col_horario:
    st.caption(
        f"Última atualização: "
        f"{st.session_state.ultima_atualizacao.strftime('%d/%m/%Y %H:%M:%S')}"
    )

if pagina == "Dashboard":

    st.header("Dashboard")
    st.write("Painel geral do Backoffice.")

elif pagina == "Inadimplência":

    st.header("Inadimplência")

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))

    mes = hoje.month + st.session_state.mes_offset
    ano = hoje.year

    while mes > 12:
        mes -= 12
        ano += 1

    while mes < 1:
        mes += 12
        ano -= 1

    nomes_meses = [
        "Janeiro", "Fevereiro", "Março", "Abril",
        "Maio", "Junho", "Julho", "Agosto",
        "Setembro", "Outubro", "Novembro", "Dezembro"
    ]

    col_mes1, col_mes2, col_mes3 = st.columns([1, 2, 1])

    with col_mes1:
        if st.button("⬅️ Mês anterior"):
            st.session_state.mes_offset -= 1
            st.rerun()

    with col_mes2:
        st.subheader(f"{nomes_meses[mes - 1]}/{ano}")

    with col_mes3:
        if st.button("Próximo mês ➡️"):
            st.session_state.mes_offset += 1
            st.rerun()

    token = st.secrets["PIPEFY_TOKEN"]
    pipe_id = st.secrets["PIPEFY_PIPE_ID"]

    query = """
    query {
      allCards(pipeId: %s, first: 500) {
        edges {
          node {
            id
            title
            current_phase {
              name
            }
            fields {
              name
              value
            }
          }
        }
      }
    }
    """ % pipe_id

    response = requests.post(
        "https://api.pipefy.com/graphql",
        json={"query": query},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )

    dados = response.json()

    if "errors" in dados:
        st.error("Erro ao consultar Pipefy.")
        st.json(dados)
        st.stop()

    cards = dados["data"]["allCards"]["edges"]

    total_mes = 0
    total_revertido = 0
    total_pendente = 0
    total_churn = 0

    ticket_total = 0
    ticket_pendente = 0
    ticket_perdido = 0

    dados_cards = []

    for card in cards:

        node = card["node"]
        fase = node["current_phase"]["name"]

        valor_ticket = 0
        data_vencimento = None

        for campo in node["fields"]:

            if campo["name"] == "Valor do ticket R$":
                valor_str = campo["value"]

                if valor_str:
                    valor_str = valor_str.replace(".", "").replace(",", ".")
                    valor_ticket = float(valor_str)

            if campo["name"] == "Data de vencimento":
                data_str = campo["value"]

                if data_str:
                    try:
                        data_vencimento = datetime.strptime(data_str, "%d/%m/%Y")
                    except:
                        pass

        if not data_vencimento:
            continue

        if data_vencimento.month == mes and data_vencimento.year == ano:

            total_mes += 1
            ticket_total += valor_ticket

            if fase == "Pagou":
                total_revertido += 1

            elif fase == "Churn + Encerrar contrato":
                total_churn += 1
                ticket_perdido += valor_ticket

            else:
                total_pendente += 1
                ticket_pendente += valor_ticket

            dados_cards.append({
                "Card": node["title"],
                "Fase": fase,
                "Vencimento": data_vencimento.strftime("%d/%m/%Y"),
                "Ticket": valor_ticket
            })

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total do mês", total_mes)

    with col2:
        st.metric("Total revertido", total_revertido)

    with col3:
        st.metric("Total pendente", total_pendente)

    st.divider()

    col4, col5 = st.columns(2)

    with col4:
        st.metric(
            "Ticket total",
            f"R$ {ticket_total:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    with col5:
        st.metric(
            "Ticket pendente",
            f"R$ {ticket_pendente:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )

    if total_churn > 0:

        st.divider()

        col6, col7 = st.columns(2)

        with col6:
            st.metric("Churn", total_churn)

        with col7:
            st.metric(
                "Ticket perdido",
                f"R$ {ticket_perdido:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )

    st.divider()

    st.subheader("Cards considerados no cálculo")

    df_debug = pd.DataFrame(dados_cards)

    st.dataframe(df_debug, use_container_width=True)
