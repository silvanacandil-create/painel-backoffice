"""Compatibilidade com as paginas existentes: cards lidos do Supabase.

A assinatura da funcao foi mantida para nao alterar as paginas que ja
chamam buscar_cards_pipefy(token, pipe_id). Esses argumentos nao sao usados.
"""

import os

import requests
import streamlit as st


COLUNAS = "card_id,titulo_card,url_card,fase,fields_json,phases_history_json,criado_em,atualizado_pipefy_em"
TAMANHO_PAGINA = 1000


def _config(nome):
    valor = os.environ.get(nome)
    if not valor:
        try:
            valor = st.secrets.get(nome)
        except (KeyError, FileNotFoundError):
            valor = None
    if not valor:
        raise RuntimeError(f"Configure {nome} nos Secrets do aplicativo Streamlit.")
    return str(valor).strip()


@st.cache_data(ttl=300, show_spinner="Carregando cards do Supabase...")
def buscar_cards_pipefy(token=None, pipe_id=None):
    """Devolve edges no formato anterior do Pipefy, mas lendo o Supabase.

    O token e o pipe_id permanecem na assinatura por compatibilidade.
    """
    url = _config("SUPABASE_URL").rstrip("/") + "/rest/v1/inadimplencia_cards"
    chave = _config("SUPABASE_KEY")
    headers = {
        "apikey": chave,
        "Authorization": f"Bearer {chave}",
        "Accept": "application/json",
    }

    todos = []
    inicio = 0
    with requests.Session() as sessao:
        while True:
            resposta = sessao.get(
                url,
                headers=headers,
                params={
                    "select": COLUNAS,
                    "order": "card_id.asc",
                    "limit": TAMANHO_PAGINA,
                    "offset": inicio,
                },
                timeout=60,
            )
            resposta.raise_for_status()
            registros = resposta.json()
            if not isinstance(registros, list):
                raise RuntimeError("Resposta inesperada do Supabase.")

            for registro in registros:
                todos.append({
                    "cursor": None,
                    "node": {
                        "id": registro["card_id"],
                        "title": registro.get("titulo_card"),
                        "url": registro.get("url_card"),
                        "created_at": registro.get("criado_em"),
                        "updated_at": registro.get("atualizado_pipefy_em"),
                        "current_phase": {"name": registro["fase"]} if registro.get("fase") else None,
                        "phases_history": registro.get("phases_history_json") or [],
                        "fields": registro.get("fields_json") or [],
                    },
                })

            if len(registros) < TAMANHO_PAGINA:
                break
            inicio += TAMANHO_PAGINA

    return todos
