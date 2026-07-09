import streamlit as st
from supabase import create_client


@st.cache_resource
def get_supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(url, key)


def testar_conexao():
    supabase = get_supabase_client()

    response = (
        supabase
        .table("movimentacoes")
        .select("id_origem")
        .limit(1)
        .execute()
    )

    return response.data
