"""Reconcilia presenca de cards. Padrao: simulacao; --aplicar habilita gravacao.
Requer PIPEFY_TOKEN, PIPEFY_PIPE_ID, SUPABASE_URL, SUPABASE_KEY.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from reconciliacao_pipefy_simulacao import buscar_ids_pipefy, request

URL = (os.environ['SUPABASE_URL']).strip().rstrip('/') + '/rest/v1/inadimplencia_cards'
KEY = os.environ['SUPABASE_KEY'].strip()
HEADERS = {'apikey': KEY, 'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'}


def buscar_registros():
    registros = {}
    offset = 0
    while True:
        resposta = request('GET', URL, headers=HEADERS, params={
            'select': 'card_id,ativo_no_pipefy,primeira_ausencia_em',
            'order': 'card_id.asc', 'limit': '500', 'offset': str(offset)})
        lote = resposta.json()
        if not isinstance(lote, list):
            raise RuntimeError('Resposta invalida do Supabase')
        for registro in lote:
            identificador = str(registro['card_id'])
            if identificador in registros:
                raise RuntimeError('ID duplicado na paginacao do Supabase')
            registros[identificador] = registro
        if len(lote) < 500:
            break
        offset += 500
    if not registros:
        raise RuntimeError('Supabase vazio: abortando')
    return registros


def atualizar(id_card, campos):
    resposta = request('PATCH', URL, headers={**HEADERS, 'Prefer': 'return=representation'},
        params={'card_id': f'eq.{id_card}', 'select': 'card_id'}, json=campos)
    linhas = resposta.json()
    if not isinstance(linhas, list) or len(linhas) != 1:
        raise RuntimeError(f'Atualizacao nao confirmou exatamente um registro: {id_card}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--aplicar', action='store_true', help='Grava alteracoes no Supabase')
    args = parser.parse_args()
    agora = datetime.now(timezone.utc)
    print('MODO:', 'APLICAR' if args.aplicar else 'SIMULACAO', flush=True)
    ids_pipefy = buscar_ids_pipefy()
    registros = buscar_registros()
    ids_supabase = set(registros)
    ausentes = ids_supabase - ids_pipefy
    novos = ids_pipefy - ids_supabase
    print(f'Pipefy={len(ids_pipefy)} Supabase={len(registros)} Ausentes={len(ausentes)} Novos={len(novos)}')
    # Fail-closed: grandes divergencias podem sinalizar falha de visibilidade.
    if len(ausentes) > max(20, int(len(registros) * 0.02)):
        raise RuntimeError('Divergencia excessiva (>20 IDs ou >2%): revisao manual necessaria')
    if novos:
        raise RuntimeError('Ha IDs no Pipefy ausentes no Supabase. Execute sincronizacao incremental antes de reconciliar.')

    primeira = []
    segunda = []
    restaurados = []
    presentes = []
    for identificador, registro in registros.items():
        if identificador in ids_pipefy:
            presentes.append(identificador)
            if registro.get('ativo_no_pipefy') is False or registro.get('primeira_ausencia_em'):
                restaurados.append(identificador)
            continue
        data = registro.get('primeira_ausencia_em')
        if not data:
            primeira.append(identificador)
        else:
            instante = datetime.fromisoformat(data.replace('Z', '+00:00'))
            if agora - instante >= timedelta(days=6):
                segunda.append(identificador)
            else:
                primeira.append(identificador)

    print(f'Primeira ausencia/aguardando prazo={len(primeira)}; Confirmados apos 6 dias={len(segunda)}; Restauracoes={len(restaurados)}')
    print('Exemplos ausentes:', ', '.join(sorted(ausentes)[:10]) or 'nenhum')
    if not args.aplicar:
        print('SIMULACAO: nenhum registro alterado.')
        return

    # Presenca e avaliada somente depois que TODAS as paginas foram validadas.
    # Nao atualizamos timestamp dos cards presentes sem mudanca para evitar milhares de PATCHes.
    for identificador in sorted(ausentes):
        registro = registros[identificador]
        campos = {'ultima_verificacao_em': agora.isoformat()}
        if not registro.get('primeira_ausencia_em'):
            campos['primeira_ausencia_em'] = agora.isoformat()
        elif identificador in segunda:
            campos['ativo_no_pipefy'] = False
        atualizar(identificador, campos)
    for identificador in restaurados:
        atualizar(identificador, {'ativo_no_pipefy': True,
                                  'primeira_ausencia_em': None,
                                  'ultima_verificacao_em': agora.isoformat()})
    print('RECONCILIACAO APLICADA COM SUCESSO')
    print('Aviso: falhas durante gravacao podem deixar aplicacao parcial; proxima execucao reavalia os IDs.')


if __name__ == '__main__':
    try:
        main()
    except Exception as erro:
        print(f'RECONCILIACAO INTERROMPIDA: {erro}', file=sys.stderr)
        sys.exit(1)
