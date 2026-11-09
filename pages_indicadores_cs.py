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
