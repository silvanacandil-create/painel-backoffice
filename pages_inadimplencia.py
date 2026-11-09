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
CAMPO_PORTE_EMPRESA = "Porte/Tamanho da empresa"

FASE_PAGOU = "Pagou"
FASE_CHURN = "Churn + Encerrar contrato"
FASE_CHURN_AVISO_PREVIO = "Churn - Não pagou o aviso prévio"


def obter_valor_campo(fields, nome_campo):
    for campo in fields:
        if campo["name"] == nome_campo:
            return campo["value"]
    return None


def obter_fase_anterior_ao_pagou(phases_history):
    if not phases_history:
        return "Não identificado"

    fases_ignorar = [
        "Aguardando Pagamento",
        "Follow-Up",
        "Follow up",
        "Follow up - Ultimato",
        "Respondeu",
        "CSM - Reversão"
    ]

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
        if item["fase"] == FASE_PAGOU:

            historico_anterior = historico[:indice]
            historico_anterior = list(reversed(historico_anterior))

            for fase_anterior in historico_anterior:
                nome_fase = fase_anterior["fase"]

                if nome_fase not in fases_ignorar:
                    return nome_fase

    return "Não identificado"


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


def obter_faixa_vencimento(data_vencimento):
    dia = data_vencimento.day

    if dia <= 10:
        return "01 a 10"
    elif dia <= 19:
        return "11 a 19"
    else:
        return "20 ao fim do mês"
