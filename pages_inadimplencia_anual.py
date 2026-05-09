import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from services_pipefy import buscar_cards_pipefy

from utils_formatacao import (
    formatar_reais,
    converter_valor_brasileiro,
    converter_data_brasileira
)

CAMPO_VALOR_TICKET = "Valor do ticket R$"
CAMPO_DATA_VENCIMENTO = "Data de vencimento"

FASE_PAGOU = "Pagou"
FASE_CHURN = "Churn + Encerrar contrato"


def obter_valor_campo(fields, nome_campo):
    for campo in fields:
        if campo["name"] == nome_campo:
            return campo["value"]
    return None


def obter_data_pagamento(phases_history):
    if not phases_history:
        return None

    for item in phases_history:
        fase = item.get("phase", {}).get("name")

        if fase == FASE_PAGOU:
            data_pagamento = item.get("firstTimeIn") or item.get("lastTimeIn")

            if data_pagamento:
                try:
                    return datetime.fromisoformat(
                        data_pagamento.replace("Z", "+00:00")
                    )
                except:
                    return None

    return None


def preparar_dados_anual(cards, ano):
    dados = []

    for card in cards:
        node = card["node"]

        fase_atual = node["current_phase"]["name"]
        fields = node["fields"]

        valor_ticket = converter_valor_brasileiro(
            obter_valor_campo(fields, CAMPO_VALOR_TICKET)
        )

        data_vencimento = converter_data_brasileira(
            obter_valor_campo(fields, CAMPO_DATA_VENCIMENTO)
        )

        if not data_vencimento:
            continue

        if data_vencimento.year != ano:
            continue

        status = "Pendente"
        data_pagamento = None
        dias_para_pagar = None

        if fase_atual == FASE_PAGOU:
            status = "Revertido"

            data_pagamento = obter_data_pagamento(
                node.get("phases_history")
            )

            if data_pagamento:
                dias_para_pagar = (
                    data_pagamento.date()
                    - data_vencimento.date()
                ).days

        elif fase_atual == FASE_CHURN:
            status = "Churn"

        dados.append({
            "Card": node["title"],
            "Fase atual": fase_atual,
            "Status": status,
            "Vencimento": data_vencimento,
            "Mês": data_vencimento.strftime("%m/%Y"),
            "Mês número": data_vencimento.month,
            "Ticket": valor_ticket,
            "Data pagamento": data_pagamento,
            "Dias para pagar": dias_para_pagar
        })

    return pd.DataFrame(dados)


def exibir_metricas_anuais(df):
    total_cards = len(df)

    total_revertido = len(df[df["Status"] == "Revertido"])
    total_pendente = len(df[df["Status"] == "Pendente"])
    total_churn = len(df[df["Status"] == "Churn"])

    ticket_total = df["Ticket"].sum()
    ticket_revertido = df[df["Status"] == "Revertido"]["Ticket"].sum()
    ticket_pendente = df[df["Status"] == "Pendente"]["Ticket"].sum()
    ticket_churn = df[df["Status"] == "Churn"]["Ticket"].sum()

    taxa_reversao_qtd = (
        total_revertido / total_cards * 100
    ) if total_cards else 0

    taxa_reversao_ticket = (
        ticket_revertido / ticket_total * 100
    ) if ticket_total else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total inadimplente", total_cards)

    with col2:
        st.metric("Revertidos", total_revertido)

    with col3:
        st.metric("Pendentes", total_pendente)

    with col4:
        st.metric("Churn", total_churn)

    st.divider()

    col5, col6, col7, col8 = st.columns(4)

    with col5:
        st.metric("Ticket total", formatar_reais(ticket_total))

    with col6:
        st.metric("Ticket revertido", formatar_reais(ticket_revertido))

    with col7:
        st.metric("Ticket pendente", formatar_reais(ticket_pendente))

    with col8:
        st.metric("Ticket perdido", formatar_reais(ticket_churn))

    st.divider()

    col9, col10 = st.columns(2)

    with col9:
        st.metric("Taxa reversão por quantidade", f"{taxa_reversao_qtd:.1f}%")

    with col10:
        st.metric("Taxa reversão por ticket", f"{taxa_reversao_ticket:.1f}%")


def exibir_comparativo_mensal(df):
    st.subheader("Comparação mês a mês")

    resumo = (
        df
        .groupby(["Mês número", "Mês"])
        .agg(
            Total=("Card", "count"),
            Revertidos=("Status", lambda x: (x == "Revertido").sum()),
            Pendentes=("Status", lambda x: (x == "Pendente").sum()),
            Churn=("Status", lambda x: (x == "Churn").sum()),
            Ticket_total=("Ticket", "sum"),
            Ticket_revertido=("Ticket", lambda x: x[df.loc[x.index, "Status"] == "Revertido"].sum()),
            Ticket_pendente=("Ticket", lambda x: x[df.loc[x.index, "Status"] == "Pendente"].sum()),
            Media_dias_para_pagar=("Dias para pagar", "mean")
        )
        .reset_index()
        .sort_values("Mês número")
    )

    resumo["Taxa reversão qtd"] = (
        resumo["Revertidos"] / resumo["Total"] * 100
    ).round(1).astype(str) + "%"

    resumo["Taxa reversão ticket"] = (
        resumo["Ticket_revertido"] / resumo["Ticket_total"] * 100
    ).fillna(0).round(1).astype(str) + "%"

    resumo["Média dias p/ pagar"] = (
        resumo["Media_dias_para_pagar"]
        .fillna(0)
        .round(1)
    )

    resumo["Ticket total"] = resumo["Ticket_total"].apply(formatar_reais)
    resumo["Ticket revertido"] = resumo["Ticket_revertido"].apply(formatar_reais)
    resumo["Ticket pendente"] = resumo["Ticket_pendente"].apply(formatar_reais)

    tabela = resumo[
        [
            "Mês",
            "Total",
            "Revertidos",
            "Pendentes",
            "Churn",
            "Taxa reversão qtd",
            "Taxa reversão ticket",
            "Ticket total",
            "Ticket revertido",
            "Ticket pendente",
            "Média dias p/ pagar"
        ]
    ]

    st.dataframe(tabela, use_container_width=True)

    st.subheader("Evolução do ticket inadimplente")

    grafico_ticket = resumo.set_index("Mês")[
        [
            "Ticket_total",
            "Ticket_revertido",
            "Ticket_pendente"
        ]
    ]

    grafico_ticket = grafico_ticket.rename(columns={
        "Ticket_total": "Ticket total",
        "Ticket_revertido": "Ticket revertido",
        "Ticket_pendente": "Ticket pendente"
    })

    st.line_chart(grafico_ticket)

    st.subheader("Evolução da quantidade de cards")

    grafico_qtd = resumo.set_index("Mês")[
        [
            "Total",
            "Revertidos",
            "Pendentes",
            "Churn"
        ]
    ]

    st.line_chart(grafico_qtd)


def exibir_inadimplencia_anual():
    st.header("Inadimplência Anual")

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))

    ano = st.selectbox(
        "Selecione o ano:",
        [2026, 2027, 2028, 2029, 2030],
        index=0 if hoje.year == 2026 else 0
    )

    token = st.secrets["PIPEFY_TOKEN"]
    pipe_id = st.secrets["PIPEFY_PIPE_ID"]

    cards = buscar_cards_pipefy(token, pipe_id)

    st.caption(f"Cards carregados do Pipefy: {len(cards)}")

    df = preparar_dados_anual(cards, ano)

    if df.empty:
        st.warning(f"Nenhum card encontrado para {ano}.")
        return

    exibir_metricas_anuais(df)

    st.divider()
    exibir_comparativo_mensal(df)
