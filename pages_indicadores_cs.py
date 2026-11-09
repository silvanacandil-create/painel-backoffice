from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from services_pipefy import buscar_cards_pipefy
from utils_formatacao import converter_data_brasileira, converter_valor_brasileiro


CAMPO_DATA_VENCIMENTO = "Data de vencimento"
CAMPO_VALOR_TICKET = "Valor do ticket R$"
CAMPO_PORTE = "Porte/Tamanho da empresa"
CAMPO_CSM = "Gerente de conta"
CAMPO_ISM = "Implementador(a)"
CAMPO_AE = "AE"
CAMPO_IMPLEMENTACAO = "Está em implementação?"

FASE_PAGOU = "Pagou"
FASE_CHURN = "Churn + Encerrar contrato"
FASE_CHURN_AVISO_PREVIO = "Churn - Não pagou o aviso prévio"

MESES = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

ORDEM_PORTES = [
    "1 a 2", "3 a 4", "5 a 6",
    "7 a 12", "13 a 20", "21 a 50",
    "51 a 200", "201 a 1000", "Mais de 1000",
]

SQUADS = {
    "Squad 1 a 6": ["1 a 2", "3 a 4", "5 a 6"],
    "Squad 7 a 50": ["7 a 12", "13 a 20", "21 a 50"],
    "Squad 51+": ["51 a 200", "201 a 1000", "Mais de 1000"],
}


def obter_valor_campo(fields, nome_campo):
    for campo in fields or []:
        if campo.get("name") == nome_campo:
            return campo.get("value")
    return None


def normalizar_texto(valor, padrao="Não informado"):
    if valor is None:
        return padrao
    texto = str(valor).strip()
    return texto if texto else padrao


def identificar_fase_cs(valor):
    texto = normalizar_texto(valor, "Não").lower()
    return "Implementação" if texto in {"sim", "yes", "true", "1"} else "Retenção"


def identificar_squad(porte):
    for squad, portes in SQUADS.items():
        if porte in portes:
            return squad
    return "Não classificado"


@st.cache_data(ttl=300, show_spinner=False)
def preparar_base_indicadores(cards_serializados, ano):
    dados = []

    for card in cards_serializados:
        node = card.get("node", {})
        fields = node.get("fields", [])
        data_vencimento = converter_data_brasileira(
            obter_valor_campo(fields, CAMPO_DATA_VENCIMENTO)
        )

        if not data_vencimento or data_vencimento.year != ano:
            continue

        fase_atual = normalizar_texto(
            node.get("current_phase", {}).get("name"), "Não identificada"
        )

        if fase_atual == FASE_PAGOU:
            status = "Revertido"
        elif fase_atual == FASE_CHURN:
            status = "Cancelado"
        else:
            status = "Pendente"

        porte = normalizar_texto(obter_valor_campo(fields, CAMPO_PORTE))
        fase_cs = identificar_fase_cs(obter_valor_campo(fields, CAMPO_IMPLEMENTACAO))

        dados.append({
            "Card": normalizar_texto(node.get("title"), "Sem título"),
            "URL": node.get("url"),
            "Ano": data_vencimento.year,
            "Mês número": data_vencimento.month,
            "Mês": MESES[data_vencimento.month],
            "Vencimento": data_vencimento,
            "Status": status,
            "Fase atual": fase_atual,
            "Fase do CS": fase_cs,
            "Porte": porte,
            "Squad": identificar_squad(porte),
            "CSM": normalizar_texto(obter_valor_campo(fields, CAMPO_CSM)),
            "ISM": normalizar_texto(obter_valor_campo(fields, CAMPO_ISM)),
            "AE": normalizar_texto(obter_valor_campo(fields, CAMPO_AE)),
            "Ticket": converter_valor_brasileiro(
                obter_valor_campo(fields, CAMPO_VALOR_TICKET)
            ),
        })

    return pd.DataFrame(dados)


def filtrar_multiselect(df, coluna, valores):
    if valores:
        return df[df[coluna].isin(valores)]
    return df


def calcular_taxa(revertidos, total):
    return (revertidos / total * 100) if total else None


def formatar_numero(valor):
    if pd.isna(valor):
        return ""
    return f"{int(round(valor)):,}".replace(",", ".")


def formatar_percentual(valor):
    if pd.isna(valor):
        return ""
    return f"{valor:.1f}%".replace(".", ",")


def montar_tabela_porte(df, porte, meses_selecionados):
    df_porte = df[df["Porte"] == porte]
    linhas = {
        "Total de inadimplentes": {},
        "Revertidos": {},
        "Cancelados": {},
        "Reversão (%)": {},
    }

    totais_mensais = []
    taxas_mensais = []

    for mes in meses_selecionados:
        recorte = df_porte[df_porte["Mês número"] == mes]
        total = len(recorte)
        revertidos = int((recorte["Status"] == "Revertido").sum())
        cancelados = int((recorte["Status"] == "Cancelado").sum())
        taxa = calcular_taxa(revertidos, total)
        nome_mes = MESES[mes]

        linhas["Total de inadimplentes"][nome_mes] = total
        linhas["Revertidos"][nome_mes] = revertidos
        linhas["Cancelados"][nome_mes] = cancelados
        linhas["Reversão (%)"][nome_mes] = taxa

        totais_mensais.append(total)
        if taxa is not None:
            taxas_mensais.append(taxa)

    soma = sum(totais_mensais)
    media = soma / len(meses_selecionados) if meses_selecionados else 0
    media_reversao = sum(taxas_mensais) / len(taxas_mensais) if taxas_mensais else None

    linhas["Total de inadimplentes"]["Soma"] = soma
    linhas["Total de inadimplentes"]["Média"] = media
    linhas["Total de inadimplentes"]["Média reversão"] = None

    for indicador in ["Revertidos", "Cancelados"]:
        linhas[indicador]["Soma"] = None
        linhas[indicador]["Média"] = None
        linhas[indicador]["Média reversão"] = None

    linhas["Reversão (%)"]["Soma"] = None
    linhas["Reversão (%)"]["Média"] = None
    linhas["Reversão (%)"]["Média reversão"] = media_reversao

    return pd.DataFrame.from_dict(linhas, orient="index")


def montar_tabela_squad(df, squad, meses_selecionados):
    portes = SQUADS[squad]
    df_squad = df[df["Porte"].isin(portes)]

    linhas = {
        "Total de inadimplentes": {},
        "Revertidos": {},
        "Cancelados": {},
        "Média de reversão dos portes (%)": {},
    }

    totais_mensais = []
    medias_reversao_mensais = []

    for mes in meses_selecionados:
        recorte_mes = df_squad[df_squad["Mês número"] == mes]
        total = len(recorte_mes)
        revertidos = int((recorte_mes["Status"] == "Revertido").sum())
        cancelados = int((recorte_mes["Status"] == "Cancelado").sum())

        taxas_portes = []
        for porte in portes:
            recorte_porte = recorte_mes[recorte_mes["Porte"] == porte]
            total_porte = len(recorte_porte)
            if total_porte:
                revertidos_porte = int((recorte_porte["Status"] == "Revertido").sum())
                taxas_portes.append(calcular_taxa(revertidos_porte, total_porte))

        media_reversao_portes = (
            sum(taxas_portes) / len(taxas_portes) if taxas_portes else None
        )
        nome_mes = MESES[mes]

        linhas["Total de inadimplentes"][nome_mes] = total
        linhas["Revertidos"][nome_mes] = revertidos
        linhas["Cancelados"][nome_mes] = cancelados
        linhas["Média de reversão dos portes (%)"][nome_mes] = media_reversao_portes

        totais_mensais.append(total)
        if media_reversao_portes is not None:
            medias_reversao_mensais.append(media_reversao_portes)

    soma = sum(totais_mensais)
    media = soma / len(meses_selecionados) if meses_selecionados else 0
    media_reversao = (
        sum(medias_reversao_mensais) / len(medias_reversao_mensais)
        if medias_reversao_mensais else None
    )

    linhas["Total de inadimplentes"]["Soma"] = soma
    linhas["Total de inadimplentes"]["Média"] = media
    linhas["Total de inadimplentes"]["Média reversão"] = None

    for indicador in ["Revertidos", "Cancelados"]:
        linhas[indicador]["Soma"] = None
        linhas[indicador]["Média"] = None
        linhas[indicador]["Média reversão"] = None

    linhas["Média de reversão dos portes (%)"]["Soma"] = None
    linhas["Média de reversão dos portes (%)"]["Média"] = None
    linhas["Média de reversão dos portes (%)"]["Média reversão"] = media_reversao

    return pd.DataFrame.from_dict(linhas, orient="index")


def formatar_tabela_visual(tabela):
    resultado = tabela.copy().astype(object)
    for indice in resultado.index:
        for coluna in resultado.columns:
            valor = resultado.loc[indice, coluna]
            if "reversão" in indice.lower() or coluna == "Média reversão":
                resultado.loc[indice, coluna] = formatar_percentual(valor)
            else:
                resultado.loc[indice, coluna] = formatar_numero(valor)
    return resultado


def montar_resumo_implantacao_retencao(df, meses_selecionados):
    linhas = {}
    for fase_cs in ["Implementação", "Retenção"]:
        valores = {}
        for mes in meses_selecionados:
            valores[MESES[mes]] = len(
                df[(df["Fase do CS"] == fase_cs) & (df["Mês número"] == mes)]
            )
        valores["Soma"] = sum(valores.values())
        valores["Média"] = (
            valores["Soma"] / len(meses_selecionados) if meses_selecionados else 0
        )
        linhas[fase_cs] = valores
    return pd.DataFrame.from_dict(linhas, orient="index")


def gerar_excel(df_filtrado, tabelas_squads, tabelas_portes, tabela_fases):
    arquivo = BytesIO()

    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        for squad, tabela in tabelas_squads.items():
            nome_aba = squad.replace("Squad ", "")[:31]
            formatar_tabela_visual(tabela).to_excel(writer, sheet_name=nome_aba)

        detalhes = []
        for porte, tabela in tabelas_portes.items():
            temp = formatar_tabela_visual(tabela).copy()
            temp.insert(0, "Porte", porte)
            temp.insert(1, "Indicador", temp.index)
            detalhes.append(temp.reset_index(drop=True))

        if detalhes:
            pd.concat(detalhes, ignore_index=True).to_excel(
                writer, sheet_name="Detalhamento por porte", index=False
            )

        formatar_tabela_visual(tabela_fases).to_excel(
            writer, sheet_name="Implementacao x Retencao"
        )

        base_exportacao = df_filtrado.copy()
        if not base_exportacao.empty:
            base_exportacao["Vencimento"] = base_exportacao["Vencimento"].dt.strftime("%d/%m/%Y")
        base_exportacao.to_excel(writer, sheet_name="Base filtrada", index=False)

    arquivo.seek(0)
    return arquivo.getvalue()


def exibir_indicadores_cs():
    st.header("Indicadores para CS")
    st.caption("Comparativo de inadimplência por squad, porte e fase da carteira.")

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    anos = list(range(2026, max(2030, hoje.year) + 1))

    col_ano, col_inicio, col_fim = st.columns(3)
    with col_ano:
        ano = st.selectbox("Ano", anos, index=anos.index(hoje.year) if hoje.year in anos else 0)
    with col_inicio:
        mes_inicial = st.selectbox(
            "Mês inicial", list(MESES.keys()), format_func=lambda x: MESES[x], index=0
        )
    with col_fim:
        indice_fim = hoje.month - 1 if ano == hoje.year else 11
        mes_final = st.selectbox(
            "Mês final", list(MESES.keys()), format_func=lambda x: MESES[x], index=indice_fim
        )

    if mes_inicial > mes_final:
        st.warning("O mês inicial deve ser anterior ou igual ao mês final.")
        return

    token = st.secrets["PIPEFY_TOKEN"]
    pipe_id = st.secrets["PIPEFY_PIPE_ID"]

    with st.spinner("Carregando dados do Pipefy..."):
        cards = buscar_cards_pipefy(token, pipe_id)
        df = preparar_base_indicadores(cards, ano)

    if df.empty:
        st.warning(f"Nenhum card encontrado para {ano}.")
        return

    meses_selecionados = list(range(mes_inicial, mes_final + 1))
    df = df[df["Mês número"].isin(meses_selecionados)].copy()

    st.subheader("Filtros")
    linha1 = st.columns(3)
    with linha1[0]:
        filtro_csm = st.multiselect("CSM", sorted(df["CSM"].dropna().unique()))
    with linha1[1]:
        filtro_ism = st.multiselect("ISM", sorted(df["ISM"].dropna().unique()))
    with linha1[2]:
        filtro_ae = st.multiselect("AE", sorted(df["AE"].dropna().unique()))

    linha2 = st.columns(3)
    with linha2[0]:
        filtro_fase = st.multiselect(
            "Fase do CS", ["Implementação", "Retenção"]
        )
    with linha2[1]:
        filtro_squad = st.multiselect(
            "Squad", list(SQUADS.keys()), default=list(SQUADS.keys())
        )
    with linha2[2]:
        portes_disponiveis = [p for p in ORDEM_PORTES if p in set(df["Porte"])]
        filtro_porte = st.multiselect("Tamanho da empresa", portes_disponiveis)

    df_filtrado = filtrar_multiselect(df, "CSM", filtro_csm)
    df_filtrado = filtrar_multiselect(df_filtrado, "ISM", filtro_ism)
    df_filtrado = filtrar_multiselect(df_filtrado, "AE", filtro_ae)
    df_filtrado = filtrar_multiselect(df_filtrado, "Fase do CS", filtro_fase)
    df_filtrado = filtrar_multiselect(df_filtrado, "Squad", filtro_squad)
    df_filtrado = filtrar_multiselect(df_filtrado, "Porte", filtro_porte)

    if df_filtrado.empty:
        st.warning("Nenhum card encontrado com os filtros selecionados.")
        return

    # Contagem histórica: mantém todos os cards do período e filtros selecionados.
    total_cards = len(df_filtrado)
    cards_aviso_previo = int(
        (df_filtrado["Fase atual"] == FASE_CHURN_AVISO_PREVIO).sum()
    )

    # Exclui aviso prévio não pago apenas dos indicadores e da exportação.
    df_filtrado = df_filtrado[
        df_filtrado["Fase atual"] != FASE_CHURN_AVISO_PREVIO
    ].copy()
    cards_contabilizados = len(df_filtrado)

    st.divider()
    st.subheader("Visão geral dos cards")
    v1, v2, v3 = st.columns(3)
    v1.metric("Total de cards", total_cards)
    v2.metric("Cards contabilizados", cards_contabilizados)
    v3.metric("Churn - Aviso prévio não pago", cards_aviso_previo)
    st.caption("Referência: data de vencimento no período e filtros selecionados.")

    if df_filtrado.empty:
        st.info("Nenhum card contabilizado para os filtros selecionados. Os cards de aviso prévio permanecem registrados no Pipefy.")
        return

    st.divider()
    total = len(df_filtrado)
    total_implantacao = int((df_filtrado["Fase do CS"] == "Implementação").sum())
    total_retencao = int((df_filtrado["Fase do CS"] == "Retenção").sum())
    total_revertidos = int((df_filtrado["Status"] == "Revertido").sum())
    taxa_geral = calcular_taxa(total_revertidos, total) or 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de inadimplentes", total)
    c2.metric("Em implementação", total_implantacao)
    c3.metric("Em retenção", total_retencao)
    c4.metric("Reversão geral", f"{taxa_geral:.1f}%")

    st.subheader("Implementação x Retenção")
    tabela_fases = montar_resumo_implantacao_retencao(df_filtrado, meses_selecionados)
    st.dataframe(formatar_tabela_visual(tabela_fases), use_container_width=True)

    st.divider()
    st.subheader("Comparativo anual por squad")
    st.caption(
        "A média de reversão do squad é a média simples das taxas dos portes que o compõem. "
        "A média do período considera a quantidade de meses selecionados."
    )

    tabelas_squads = {}
    tabelas_portes = {}

    squads_exibidos = filtro_squad or list(SQUADS.keys())
    for squad in squads_exibidos:
        tabela_squad = montar_tabela_squad(df_filtrado, squad, meses_selecionados)
        tabelas_squads[squad] = tabela_squad

        with st.expander(squad, expanded=True):
            st.markdown("**Resumo do squad**")
            st.dataframe(formatar_tabela_visual(tabela_squad), use_container_width=True)

            st.markdown("**Detalhamento por tamanho de empresa**")
            portes = SQUADS[squad]
            if filtro_porte:
                portes = [p for p in portes if p in filtro_porte]

            for porte in portes:
                tabela_porte = montar_tabela_porte(df_filtrado, porte, meses_selecionados)
                tabelas_portes[porte] = tabela_porte
                st.markdown(f"##### {porte}")
                st.dataframe(formatar_tabela_visual(tabela_porte), use_container_width=True)

    excel = gerar_excel(
        df_filtrado=df_filtrado,
        tabelas_squads=tabelas_squads,
        tabelas_portes=tabelas_portes,
        tabela_fases=tabela_fases,
    )

    st.download_button(
        "📥 Exportar dados filtrados em Excel",
        data=excel,
        file_name=f"indicadores_cs_{ano}_{MESES[mes_inicial]}_{MESES[mes_final]}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
