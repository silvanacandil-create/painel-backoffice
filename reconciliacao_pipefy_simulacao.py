"""Simulacao de reconciliacao Pipefy x Supabase. SOMENTE LEITURA.

Requer variaveis: PIPEFY_TOKEN, PIPEFY_PIPE_ID, SUPABASE_URL, SUPABASE_KEY.
Execute: py reconciliacao_pipefy_simulacao.py
"""
import os
import sys
import time
from datetime import datetime, timezone

import requests

PIPEFY_TOKEN = (os.getenv('PIPEFY_TOKEN') or '').strip()
PIPEFY_PIPE_ID = (os.getenv('PIPEFY_PIPE_ID') or '').strip()
SUPABASE_URL = (os.getenv('SUPABASE_URL') or '').strip().rstrip('/')
SUPABASE_KEY = (os.getenv('SUPABASE_KEY') or '').strip()

if not all((PIPEFY_TOKEN, PIPEFY_PIPE_ID, SUPABASE_URL, SUPABASE_KEY)):
    sys.exit('ERRO: Configure PIPEFY_TOKEN, PIPEFY_PIPE_ID, SUPABASE_URL e SUPABASE_KEY.')

PIPEFY_ENDPOINT = 'https://api.pipefy.com/graphql'
SUPABASE_ENDPOINT = f'{SUPABASE_URL}/rest/v1/inadimplencia_cards'
QUERY = '''
query ($pipeId: ID!, $first: Int!, $after: String) {
  allCards(pipeId: $pipeId, first: $first, after: $after) {
    edges { node { id } }
    pageInfo { hasNextPage endCursor }
  }
}
'''
SESSION = requests.Session()


def request(method, url, **kwargs):
    for attempt in range(1, 5):
        try:
            response = SESSION.request(method, url, timeout=90, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f'Erro temporario HTTP {response.status_code}')
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as error:
            if attempt == 4 or (isinstance(error, requests.HTTPError) and
                                getattr(getattr(error, 'response', None), 'status_code', None) in (400, 401, 403, 404)):
                raise
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError('Nao foi possivel completar a requisicao.')


def buscar_ids_pipefy():
    ids = set()
    cursor = None
    cursors = set()
    pagina = 0
    while True:
        response = request('POST', PIPEFY_ENDPOINT,
            headers={'Authorization': f'Bearer {PIPEFY_TOKEN}', 'Content-Type': 'application/json'},
            json={'query': QUERY, 'variables': {
                'pipeId': PIPEFY_PIPE_ID, 'first': 50, 'after': cursor}})
        data = response.json()
        if data.get('errors'):
            raise RuntimeError(f'Pipefy retornou erro GraphQL: {str(data["errors"])[:400]}')
        result = (data.get('data') or {}).get('allCards')
        if not isinstance(result, dict):
            raise RuntimeError('Resposta incompleta do Pipefy (allCards ausente).')
        edges = result.get('edges')
        info = result.get('pageInfo')
        if not isinstance(edges, list) or not isinstance(info, dict):
            raise RuntimeError('Resposta incompleta do Pipefy (paginacao ausente).')
        if info.get('hasNextPage') and not edges:
            raise RuntimeError('Pipefy informou proxima pagina, mas nao retornou cards.')
        for edge in edges:
            node = edge.get('node') or {}
            if node.get('id') is None:
                raise RuntimeError('Card sem ID retornado pelo Pipefy.')
            ids.add(str(node['id']))
        pagina += 1
        print(f'Pipefy pagina {pagina}: {len(edges)} cards; {len(ids)} IDs distintos', flush=True)
        if not info.get('hasNextPage'):
            break
        next_cursor = info.get('endCursor')
        if not next_cursor or next_cursor in cursors:
            raise RuntimeError('Cursor invalido ou repetido no Pipefy.')
        cursors.add(next_cursor)
        cursor = next_cursor
        time.sleep(0.2)
    if not ids:
        raise RuntimeError('Pipefy retornou zero cards. Simulacao cancelada.')
    return ids


def buscar_ids_supabase():
    ids = set()
    offset = 0
    tamanho = 500
    pagina = 0
    while True:
        response = request('GET', SUPABASE_ENDPOINT,
            headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
                     'Accept': 'application/json'},
            params={'select': 'card_id', 'order': 'card_id.asc',
                    'limit': str(tamanho), 'offset': str(offset)})
        rows = response.json()
        if not isinstance(rows, list):
            raise RuntimeError('Resposta invalida do Supabase.')
        for row in rows:
            if row.get('card_id') is None:
                raise RuntimeError('Registro sem card_id no Supabase.')
            ids.add(str(row['card_id']))
        pagina += 1
        print(f'Supabase pagina {pagina}: {len(rows)} cards; {len(ids)} IDs distintos', flush=True)
        if len(rows) < tamanho:
            break
        offset += tamanho
    if not ids:
        raise RuntimeError('Supabase retornou zero cards. Simulacao cancelada.')
    return ids


def main():
    print('RECONCILIACAO - SIMULACAO (SOMENTE LEITURA)')
    print('Inicio UTC:', datetime.now(timezone.utc).isoformat())
    ids_pipefy = buscar_ids_pipefy()
    ids_supabase = buscar_ids_supabase()
    ausentes_pipefy = sorted(ids_supabase - ids_pipefy)
    novos_pipefy = sorted(ids_pipefy - ids_supabase)
    print('\nRESULTADO DA SIMULACAO')
    print('IDs distintos no Pipefy:', len(ids_pipefy))
    print('IDs distintos no Supabase:', len(ids_supabase))
    print('No Supabase, mas ausentes no Pipefy:', len(ausentes_pipefy))
    print('No Pipefy, mas ausentes no Supabase:', len(novos_pipefy))
    print('Exemplos de IDs ausentes no Pipefy (ate 15):', ', '.join(ausentes_pipefy[:15]) or 'nenhum')
    print('Exemplos de IDs ausentes no Supabase (ate 15):', ', '.join(novos_pipefy[:15]) or 'nenhum')
    print('NENHUM REGISTRO FOI ALTERADO.')
    print('ATENCAO: ausencia no pipe pode significar exclusao, movimentacao ou falha de visibilidade.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('SIMULACAO INTERROMPIDA:', str(exc)[:500], file=sys.stderr)
        sys.exit(1)
