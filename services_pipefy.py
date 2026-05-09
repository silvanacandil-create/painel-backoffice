import requests
import streamlit as st


@st.cache_data(ttl=300)
def buscar_cards_pipefy(token, pipe_id):
    todos_cards = []
    cursor = None
    continuar = True

    while continuar:
        after = f', after: "{cursor}"' if cursor else ""

        query = f"""
        query {{
          allCards(pipeId: {pipe_id}, first: 50{after}) {{
            edges {{
              cursor
              node {{
                id
                title
                url
                current_phase {{
                  name
                }}
                phases_history {{
                  firstTimeIn
                  lastTimeIn
                  lastTimeOut
                  phase {{
                    name
                  }}
                }}
                fields {{
                  name
                  value
                }}
              }}
            }}
            pageInfo {{
              hasNextPage
              endCursor
            }}
          }}
        }}
        """

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

        resultado = dados["data"]["allCards"]

        todos_cards.extend(resultado["edges"])
        continuar = resultado["pageInfo"]["hasNextPage"]
        cursor = resultado["pageInfo"]["endCursor"]

    return todos_cards
