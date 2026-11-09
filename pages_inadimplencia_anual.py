import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from services_pipefy import buscar_cards_pipefy
from utils_formatacao import (
    formatar_reais,
    converter_valor_brasileiro,
    converter_data_brasileira,
)

CAMPO_VALOR_TICKET = "Valor do ticket R$"
CAMPO_DATA_VENCIMENTO = "Data de vencimento"

FASE_PAGOU = "Pagou"
FASE_CHURN = "Churn + Encerrar contrato"
FASE_CHURN_AVISO_PREVIO = "Churn - Não pagou o aviso prévio"

COLUNAS = [
    "Card", "Fase atual", "Status", "Vencimento", "Mês", "Mês número",
    "Ticket", "Data pagamento", "Dias para pagar",
]


def obter_valor_campo(fields, nome_campo):
    for campo in fields or []:
        if campo.get("name") == nome_campo:
            return campo.get("value")
    return None


def obter_data_pagamento(phases_history):
    if not phases_history:
        return None
    for item in phases_history:
        fase = (item.get("phase") or {}).get("name")
        if fase == FASE_PAGOU:
            data_pagamento = item.get("firstTimeIn") or item.get("lastTimeIn")
            if data_pagamento:
                try:
                    return datetime.fromisoformat(data_pagamento.replace("Z", "+00:00"))
                except (TypeError, ValueError):
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
        if not data_vencimento or data_vencimento.year != ano:
            continue

        status = "Pendente"
        data_pagamento = None
        dias_para_pagar = None
        if fase_atual == FASE_PAGOU:
            status = "Revertido"
            data_pagamento = obter_data_pagamento(node.get("phases_history"))
            if data_pagamento:
                dias_para_pagar = (data_pagamento.date() - data_vencimento.date()).days
        elif fase_atual == FASE_CHURN:
            status = "Churn"
        elif fase_atual == FASE_CHURN_AVISO_PREVIO:
            status = "Aviso prévio não pago"

        dados.append({
            "Card": node["title"],
            "Fase atual": fase_atual,
            "Status": status,
            "Vencimento": data_vencimento,
            "Mês": data_vencimento.strftime("%m/%Y"),
            "Mês número": data_vencimento.month,
            "Ticket": valor_ticket,
            "Data pagamento": data_pagamento,
            "Dias para pagar": dias_para_pagar,
        })
    return pd.DataFrame(dados, columns=COLUNAS)


def exibir_visao_geral(df_total, df_contabilizado):
    st.subheader("Visão geral dos cards")
    total = len(df_total)
    contabilizados = len(df_contabilizado)
    excluidos = total - contabilizados
    col1, col2, col3 = st.columns(3)
