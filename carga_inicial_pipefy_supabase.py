import os
import re
import json
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests

PIPEFY_TOKEN = os.getenv('PIPEFY_TOKEN')
PIPEFY_PIPE_ID = os.getenv('PIPEFY_PIPE_ID')
SUPABASE_URL = (os.getenv('SUPABASE_URL') or '').rstrip('/')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not all((PIPEFY_TOKEN, PIPEFY_PIPE_ID, SUPABASE_URL, SUPABASE_KEY)):
    raise SystemExit('Configure PIPEFY_TOKEN, PIPEFY_PIPE_ID, SUPABASE_URL e SUPABASE_KEY no CMD.')

PIPEFY_ENDPOINT = 'https://api.pipefy.com/graphql'
SUPABASE_ENDPOINT = f'{SUPABASE_URL}/rest/v1/inadimplencia_cards'
PAGE_SIZE = 50
BATCH_SIZE = 50
MAX_ATTEMPTS = 4

QUERY = '''
query ($pipeId: ID!, $first: Int!, $after: String) {
  allCards(pipeId: $pipeId, first: $first, after: $after) {
    edges {
      cursor
      node {
        id
        title
        url
        created_at
        updated_at
        current_phase { name }
        phases_history {
          firstTimeIn
          lastTimeIn
          lastTimeOut
          phase { name }
        }
        fields { name value }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
'''


def campo(campos, nome):
    return next((c.get('value') for c in campos if c.get('name') == nome), None)


def valor_decimal(valor):
    if valor is None or str(valor).strip() == '':
        return None
    texto = str(valor).replace('R$', '').replace(' ', '').strip()
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    try:
        return str(Decimal(texto))
    except InvalidOperation:
        return None


def data_iso(valor):
    if not valor:
        return None
    for formato in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(valor).strip()[:10], formato).date().isoformat()
        except ValueError:
            continue
    return None


def preparar(edge):
    node = edge['node']
    campos = node.get('fields') or []
    link_produttivo = campo(campos, 'Link do Produttivo') or ''
    account_match = re.search(r'/accounts/(\d+)', str(link_produttivo))
    return {
        'card_id': str(node['id']),
        'cliente': campo(campos, 'Cliente') or node.get('title'),
        'cnpj_cpf': campo(campos, 'CNPJ/CPF'),
        'account_id': account_match.group(1) if account_match else None,
        'ticket': valor_decimal(campo(campos, 'Valor do ticket R$')),
        'data_vencimento': data_iso(campo(campos, 'Data de vencimento')),
        'fase': (node.get('current_phase') or {}).get('name'),
        'implementacao': campo(campos, 'Está em implementação?'),
        'intervalo': campo(campos, 'Intervalo da cobrança'),
        'porte': campo(campos, 'Porte/Tamanho da empresa'),
        'contato': campo(campos, 'Contato'),
        'ae': campo(campos, 'AE'),
        'implementador': campo(campos, 'Implementador(a)'),
        'gerente_conta': campo(campos, 'Gerente de conta'),
        'link_fatura': campo(campos, 'Link da fatura vencida'),
        'link_retencao': campo(campos, 'Link Pipe Retention'),
        'titulo_card': node.get('title'),
        'url_card': node.get('url'),
        'fields_json': campos,
        'phases_history_json': node.get('phases_history') or [],
        'criado_em': node.get('created_at'),
        'atualizado_pipefy_em': node.get('updated_at'),
        'sincronizado_em': datetime.now(timezone.utc).isoformat(),
    }


def requisicao(method, url, **kwargs):
    for tentativa in range(1, MAX_ATTEMPTS + 1):
        try:
            resposta = requests.request(method, url, timeout=90, **kwargs)
            if resposta.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f'HTTP {resposta.status_code}: {resposta.text[:300]}')
            resposta.raise_for_status()
            return resposta
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as erro:
            if tentativa == MAX_ATTEMPTS or (
                isinstance(erro, requests.HTTPError)
                and 'HTTP 4' in str(erro)
                and 'HTTP 429' not in str(erro)
            ):
                raise
            espera = min(2 ** tentativa, 30)
            print(f'  Falha temporaria: {erro}. Nova tentativa em {espera}s...', flush=True)
            time.sleep(espera)


def gravar_lote(lote):
    if not lote:
        return
    resposta = requisicao(
        'POST', SUPABASE_ENDPOINT,
        headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates,return=minimal',
        },
        json=lote,
    )
    if not resposta.ok:
        raise RuntimeError(resposta.text[:1000])


def contar_registros():
    resposta = requisicao(
        'GET', SUPABASE_ENDPOINT,
        headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'count=exact',
        },
        params={'select': 'card_id', 'limit': '1'},
    )
    return resposta.headers.get('Content-Range', '(indisponivel)')


def main():
    inicio = datetime.now(timezone.utc)
    print(f'Inicio da carga (UTC): {inicio.isoformat()}')
    print('A consulta sera completa, sem filtro por data.')
    cursor = None
    pagina = 0
    total_processados = 0
    ids_vistos = set()

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
                },
            },
        )
        dados = resposta.json()
        if dados.get('errors'):
            print(json.dumps(dados['errors'], indent=2, ensure_ascii=False))
            raise RuntimeError('Pipefy retornou erros GraphQL. Carga interrompida.')
        resultado = (dados.get('data') or {}).get('allCards')
        if resultado is None:
            raise RuntimeError('Resposta sem allCards. Carga interrompida.')

        edges = resultado.get('edges') or []
        novos = []
        for edge in edges:
            card_id = str(edge['node']['id'])
            if card_id not in ids_vistos:
                novos.append(preparar(edge))
                ids_vistos.add(card_id)

        for inicio_lote in range(0, len(novos), BATCH_SIZE):
            gravar_lote(novos[inicio_lote:inicio_lote + BATCH_SIZE])

        pagina += 1
        total_processados += len(novos)
        info = resultado['pageInfo']
        print(f'Pagina {pagina}: {len(edges)} retornados; {len(novos)} novos; total {total_processados}', flush=True)
        if not info.get('hasNextPage'):
            break
        proximo_cursor = info.get('endCursor')
        if not proximo_cursor or proximo_cursor == cursor:
            raise RuntimeError('Paginacao sem cursor valido. Carga interrompida.')
        cursor = proximo_cursor
        time.sleep(0.3)

    print('\nCARGA INICIAL FINALIZADA!')
    print(f'Cards distintos processados: {total_processados}')
    print(f'Total na tabela (Content-Range): {contar_registros()}')
    print(f'Inicio UTC para reconciliacao incremental: {inicio.isoformat()}')
    print('IMPORTANTE: Guarde a data de inicio. Antes de trocar o painel, sincronize alteracoes desde ela.')
    print('O total da tabela pode diferir do total processado se ja havia registros anteriores.')


if __name__ == '__main__':
    try:
        main()
    except Exception as erro:
        print(f'\nCARGA INTERROMPIDA: {erro}')
        print('Os lotes ja gravados permanecem no Supabase. Nao altere o painel ainda.')
        raise SystemExit(1)
