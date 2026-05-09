import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from services.pipefy import buscar_cards_pipefy

from utils.formatacao import (
    formatar_reais,
    converter_valor_brasileiro,
    converter_data_brasileira
)

CAMPO_VALOR_TICKET = "Valor do ticket R$"
CAMPO_DATA_VENCIMENTO = "Data de vencimento"
CAMPO_PORTE_EMPRESA = "Porte/Tamanho da empresa"

FASE_PAGOU = "Pagou"
FASE_CHURN = "Churn + Encerrar contrato"


def obter_valor_campo(fields, nome_campo):
    for campo in fields:
        if campo["name"] == nome_campo:
            return campo["value"]
    return None


def obter_fase_anterior_ao_pagou(phases_history):
    if not phases_history:
        return "Não identificado"

    historico = []

    for item in phases_history:
        fase = item.get("phase", {}).get("name")
        entrada = item.get("firstTimeIn") or item.get("lastTimeIn")

        if fase and entrada:
            historico.append({
                "fase": fase,
                "entrada": entrada
            })

    historico = sorted(historico, key=lambda x: x["entrada"])

    for indice, item in enumerate(historico):
        if item["fase"] == FASE_PAGOU and indice > 0:
            return historico[indice - 1]["fase"]

    return "Não identificado"


def preparar_dados_cards(cards, mes, ano):
    dados_cards = []

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

        porte_empresa = obter_valor_campo(fields, CAMPO_PORTE_EMPRESA) or "Não informado"

        if not data_vencimento:
            continue

        if data_vencimento.month != mes or data_vencimento.year != ano:
            continue

        status = "Pendente"
        fase_antes_pagou = ""

        if fase_atual == FASE_PAGOU:
            status = "Revertido"
            fase_antes_pagou = obter_fase_anterior_ao_pagou(
                node.get("phases_history")
            )

        elif fase_atual == FASE_CHURN:
            status = "Churn"

        dados_cards.append({
            "Card": node["title"],
            "URL": node.get("url"),
            "Fase atual": fase_atual,
            "Status": status,
            "Fase antes de pagar": fase_antes_pagou,
            "Vencimento": data_vencimento.strftime("%d/%m/%Y"),
            "Ticket": valor_ticket,
            "Porte": porte_empresa
        })

    return pd.DataFrame(dados_cards)


def exibir_metricas_gerais(df):
    total_mes = len(df)

    total_revertido = len(df[df["Status"] == "Revertido"])
    total_pendente = len(df[df["Status"] == "Pendente"])
    total_churn = len(df[df["Status"] == "Churn"])

    ticket_total = df["Ticket"].sum()
    ticket_revertido = df[df["Status"] == "Revertido"]["Ticket"].sum()
    ticket_pendente = df[df["Status"] == "Pendente"]["Ticket"].sum()
    ticket_perdido = df[df["Status"] == "Churn"]["Ticket"].sum()

    taxa_reversao = (total_revertido / total_mes * 100) if total_mes else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total do mês", total_mes)

    with col2:
        st.metric("Total revertido", total_revertido)

    with col3:
        st.metric("Total pendente", total_pendente)

    with col4:
        st.metric("Taxa de reversão", f"{taxa_reversao:.1f}%")

    st.divider()

    col5, col6, col7 = st.columns(3)

    with col5:
        st.metric("Ticket total", formatar_reais(ticket_total))

    with col6:
        st.metric("Ticket revertido", formatar_reais(ticket_revertido))

    with col7:
        st.metric("Ticket pendente", formatar_reais(ticket_pendente))

    if total_churn > 0:
        st.divider()

        col8, col9 = st.columns(2)

        with col8:
            st.metric("Churn", total_churn)

        with col9:
            st.metric("Ticket perdido", formatar_reais(ticket_perdido))


def exibir_metricas_fase_pagamento(df):
    df_revertido = df[df["Status"] == "Revertido"].copy()

    if df_revertido.empty:
        st.info("Ainda não há cards revertidos neste mês.")
        return

    st.subheader("Em qual fase os clientes mais pagaram?")

    resumo_fase = (
        df_revertido
        .groupby("Fase antes de pagar")
        .agg(
            Quantidade=("Card", "count"),
            Ticket_revertido=("Ticket", "sum")
        )
        .reset_index()
        .sort_values("Quantidade", ascending=False)
    )

    resumo_fase["Ticket revertido"] = resumo_fase["Ticket_revertido"].apply(formatar_reais)
    resumo_fase = resumo_fase.drop(columns=["Ticket_revertido"])

    st.dataframe(resumo_fase, use_container_width=True)


def exibir_metricas_porte(df):
    st.subheader("Inadimplência por porte da empresa")

    resumo_porte = (
        df
        .groupby("Porte")
        .agg(
            Total=("Card", "count"),
            Pendentes=("Status", lambda x: (x == "Pendente").sum()),
            Revertidos=("Status", lambda x: (x == "Revertido").sum()),
            Churn=("Status", lambda x: (x == "Churn").sum()),
            Ticket_total=("Ticket", "sum"),
            Ticket_pendente=("Ticket", lambda x: x[df.loc[x.index, "Status"] == "Pendente"].sum()),
            Ticket_revertido=("Ticket", lambda x: x[df.loc[x.index, "Status"] == "Revertido"].sum())
        )
        .reset_index()
    )

    resumo_porte["Taxa de pendência"] = (
        resumo_porte["Pendentes"] / resumo_porte["Total"] * 100
    ).round(1).astype(str) + "%"

    resumo_porte["Taxa de reversão"] = (
        resumo_porte["Revertidos"] / resumo_porte["Total"] * 100
    ).round(1).astype(str) + "%"

    resumo_porte["Ticket total"] = resumo_porte["Ticket_total"].apply(formatar_reais)
    resumo_porte["Ticket pendente"] = resumo_porte["Ticket_pendente"].apply(formatar_reais)
    resumo_porte["Ticket revertido"] = resumo_porte["Ticket_revertido"].apply(formatar_reais)

    resumo_porte = resumo_porte.drop(
        columns=["Ticket_total", "Ticket_pendente", "Ticket_revertido"]
    )

    resumo_porte = resumo_porte.sort_values("Total", ascending=False)

    st.dataframe(resumo_porte, use_container_width=True)

    porte_mais_devedor = resumo_porte.iloc[0]["Porte"] if not resumo_porte.empty else None

    if porte_mais_devedor:
        st.info(f"O porte com mais inadimplência no mês foi: **{porte_mais_devedor}**.")


def exibir_inadimplencia():
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

    cards = buscar_cards_pipefy(token, pipe_id)

    st.caption(f"Cards carregados do Pipefy: {len(cards)}")

    df = preparar_dados_cards(cards, mes, ano)

    if df.empty:
        st.warning("Nenhum card encontrado para o mês selecionado.")
        return

    exibir_metricas_gerais(df)

    st.divider()
    exibir_metricas_fase_pagamento(df)

    st.divider()
    exibir_metricas_porte(df)

    st.divider()
    st.subheader("Cards considerados no cálculo")
    st.dataframe(df, use_container_width=True)
