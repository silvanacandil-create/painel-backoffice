"""Sincronizacao incremental Pipefy -> Supabase com checkpoint centralizado.

Requer carga_inicial_pipefy_supabase.py na mesma pasta e as quatro
variaveis de ambiente ja configuradas. Nao executa a carga completa.
"""
import json
import time
from datetime import datetime, timedelta, timezone

from carga_inicial_pipefy_supabase import (
    PIPEFY_TOKEN, PIPEFY_PIPE_ID, PIPEFY_ENDPOINT,
    SUPABASE_URL, SUPABASE_KEY, PAGE_SIZE, BATCH_SIZE,
    preparar, requisicao, gravar_lote, contar_registros,
)

TABELA_LOG = f"{SUPABASE_URL}/rest/v1/sincronizacoes_pipefy"
MARGEM = timedelta(minutes=5)
FALLBACK_INICIO = datetime.fromisoformat('2026-11-24T00:07:39.743862+00:00')

QUERY = '''
query ($pipeId: ID!, $first: Int!, $after: String, $dataInicio: String!) {
  allCards(pipeId: $pipeId, first: $first, after: $after,
    filter: {field: "updated_at", operator: gte, value: $dataInicio}) {
    edges {
      cursor
      node {
        id title url created_at updated_at
        current_phase { name }
        phases_history {
          firstTimeIn lastTimeIn lastTimeOut phase { name }
        }
        fields { name value }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
'''


def headers(prefer=None):
    h = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
    }
    if prefer:
        h['Prefer'] = prefer
    return h


def ultima_concluida():
    resposta = requisicao(
        'GET', TABELA_LOG,
        headers=headers(),
        params={
            'select': 'id,iniciado_em,finalizado_em',
            'status': 'eq.concluido',
            'order': 'iniciado_em.desc',
            'limit': '1',
        },
    )
    registros = resposta.json()
    if not registros:
        print('AVISO: nenhum checkpoint no Supabase; usando inicio da carga inicial.')
        return FALLBACK_INICIO
    return datetime.fromisoformat(registros[0]['iniciado_em'].replace('Z', '+00:00'))


def iniciar_execucao(inicio):
    # O indice unico parcial no banco impede dois registros 'executando'.
    resposta = requisicao(
        'POST', TABELA_LOG,
        headers=headers('return=representation'),
        json=[{
            'tipo': 'incremental',
            'iniciado_em': inicio.isoformat(),
            'status': 'executando',
            'cards_processados': 0,
        }],
    )
    linhas = resposta.json()
    if not linhas or 'id' not in linhas[0]:
        raise RuntimeError('Supabase nao retornou o ID da sincronizacao.')
    return linhas[0]['id']


def finalizar_execucao(execucao_id, status, quantidade, erro=None):
    payload = {
        'status': status,
        'finalizado_em': datetime.now(timezone.utc).isoformat(),
        'cards_processados': quantidade,
        'mensagem_erro': str(erro)[:1000] if erro else None,
    }
    requisicao(
        'PATCH', TABELA_LOG,
        headers=headers('return=minimal'),
        params={'id': f'eq.{execucao_id}', 'status': 'eq.executando'},
        json=payload,
    )


def sincronizar(desde):
    cursor = None
    ids_vistos = set()
    pagina = 0
    while True:
        resposta = requisicao(
            'POST', PIPEFY_ENDPOINT,
            headers={
                'Authorization': f'Bearer {PIPEFY_TOKEN}',
                'Content-Type': 'application/json',
            },
            json={
                'query': QUERY,
                'variables': {
                    'pipeId': str(PIPEFY_PIPE_ID),
                    'first': PAGE_SIZE,
                    'after': cursor,
                    'dataInicio': desde.isoformat(),
                },
            },
        )
        dados = resposta.json()
        if dados.get('errors'):
            raise RuntimeError('Erro GraphQL: ' + json.dumps(dados['errors'], ensure_ascii=False)[:1000])
        resultado = (dados.get('data') or {}).get('allCards')
        if resultado is None:
            raise RuntimeError('Resposta Pipefy sem allCards.')

        edges = resultado.get('edges') or []
        novos = []
        for edge in edges:
            card_id = str(edge['node']['id'])
            if card_id not in ids_vistos:
                novos.append(preparar(edge))
                ids_vistos.add(card_id)
        for i in range(0, len(novos), BATCH_SIZE):
            gravar_lote(novos[i:i + BATCH_SIZE])

        pagina += 1
        print(f'Pagina {pagina}: {len(edges)} retornados; {len(novos)} distintos; total {len(ids_vistos)}', flush=True)
        info = resultado['pageInfo']
        if not info.get('hasNextPage'):
            return len(ids_vistos)
        proximo = info.get('endCursor')
        if not proximo or proximo == cursor:
            raise RuntimeError('Paginacao sem cursor valido.')
        cursor = proximo
        time.sleep(0.3)


def main():
    inicio = datetime.now(timezone.utc)
    desde = ultima_concluida() - MARGEM
    print('SINCRONIZACAO INCREMENTAL COM CHECKPOINT NO SUPABASE')
    print('Buscar desde (UTC):', desde.isoformat())
    print('Inicio desta execucao (UTC):', inicio.isoformat())
    try:
        execucao_id = iniciar_execucao(inicio)
    except Exception as erro:
        print('\nNAO FOI POSSIVEL INICIAR:', erro)
        print('Se ja houver uma execucao em andamento, verifique a tabela sincronizacoes_pipefy.')
        print('Nao remova uma trava sem confirmar que a outra execucao realmente terminou.')
        raise SystemExit(1)

    quantidade = 0
    try:
        quantidade = sincronizar(desde)
        finalizar_execucao(execucao_id, 'concluido', quantidade)
    except Exception as erro:
        print('\nERRO NA SINCRONIZACAO:', erro)
        try:
            finalizar_execucao(execucao_id, 'erro', quantidade, erro)
        except Exception as erro_log:
            print('ATENCAO: falha ao registrar erro no Supabase:', erro_log)
            print('Verifique se ficou uma execucao presa como executando.')
        raise SystemExit(1)

    print('\nSINCRONIZACAO CONCLUIDA!')
    print('Cards distintos atualizados:', quantidade)
    print('Total na tabela:', contar_registros())
    print('Registro da execucao no Supabase: ID', execucao_id)
    print('Checkpoint centralizado: OK')
    print('ATENCAO: exclusoes e saidas do pipe exigem reconciliacao separada.')


if __name__ == '__main__':
    main()
