import streamlit as st

from database.supabase import testar_conexao


def render():
    st.title("Fluxo de Caixa")

    if st.button("Testar conexão com Supabase"):
        try:
            dados = testar_conexao()

            st.success("Conexão realizada com sucesso!")

            st.write(dados)

        except Exception as e:
            st.error("Erro ao conectar ao Supabase")
            st.exception(e)
