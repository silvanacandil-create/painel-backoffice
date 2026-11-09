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

    # Mantém a data de vencimento como referência do período.
    df_total = preparar_dados_cards(cards, mes, ano)

    if df_total.empty:
        st.warning("Nenhum card encontrado para o mês selecionado.")
        return

    # O histórico permanece no Pipefy, mas a fase abaixo não entra nos cálculos.
    df = df_total[
        df_total["Fase atual"] != FASE_CHURN_AVISO_PREVIO
    ].copy()

    total_cards = len(df_total)
    cards_contabilizados = len(df)
    cards_aviso_previo = total_cards - cards_contabilizados

    st.subheader("Visão geral dos cards")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total de cards", total_cards)

    with col2:
        st.metric("Cards contabilizados", cards_contabilizados)

    with col3:
        st.metric("Churn - Aviso prévio não pago", cards_aviso_previo)

    st.caption("Referência: data de vencimento no mês selecionado.")

    if df.empty:
        st.info("Todos os cards do período estão na fase de aviso prévio não pago; não há cards contabilizados nos demais indicadores.")
        return

    st.divider()
    exibir_metricas_gerais(df)

    st.divider()
    exibir_metricas_faixa_vencimento(df)

    st.divider()
    exibir_metricas_fase_pagamento(df)

    st.divider()
    exibir_metricas_porte(df)
