"""Dispara e acompanha sincronizacao Pipefy via GitHub Actions."""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import requests
import streamlit as st

OWNER = "silvanacandil-create"
REPO = "painel-backoffice"
WORKFLOW = "sincronizar_pipefy.yml"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"


def _token():
    valor = os.environ.get("GITHUB_ACTIONS_TOKEN")
    if not valor:
        try:
            valor = st.secrets.get("GITHUB_ACTIONS_TOKEN")
        except (KeyError, FileNotFoundError):
            valor = None
    if not valor or not str(valor).strip():
        raise RuntimeError("Configure GITHUB_ACTIONS_TOKEN nos Secrets do Streamlit.")
    return str(valor).strip()


def executar_sincronizacao(timeout_segundos=180):
    """Solicita execucao e espera a run com identificador unico terminar."""
    requisicao_id = str(uuid.uuid4())
    inicio = datetime.now(timezone.utc)
    cabecalhos = {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with requests.Session() as sessao:
        resp = sessao.post(
            f"{API}/actions/workflows/{WORKFLOW}/dispatches",
            headers=cabecalhos,
            json={"ref": "main", "inputs": {"request_id": requisicao_id}},
            timeout=25,
        )
        if resp.status_code not in (204, 200):
            raise RuntimeError(f"GitHub recusou a solicitacao (HTTP {resp.status_code}): {resp.text[:300]}")

        prazo = time.monotonic() + timeout_segundos
        run_id = None
        url_execucao = None
        while time.monotonic() < prazo:
            if run_id is None:
                resp = sessao.get(
                    f"{API}/actions/workflows/{WORKFLOW}/runs",
                    headers=cabecalhos,
                    params={
                        "event": "workflow_dispatch",
                        "created": f">={ (inicio - timedelta(minutes=2)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
                        "per_page": 50,
                    },
                    timeout=25,
                )
                resp.raise_for_status()
                for run in resp.json().get("workflow_runs", []):
                    if requisicao_id in (run.get("display_title") or ""):
                        run_id = run["id"]
                        url_execucao = run.get("html_url")
                        break
            else:
                resp = sessao.get(f"{API}/actions/runs/{run_id}", headers=cabecalhos, timeout=25)
                resp.raise_for_status()
                run = resp.json()
                if run.get("status") == "completed":
                    if run.get("conclusion") != "success":
                        raise RuntimeError(f"Sincronizacao terminou com status {run.get('conclusion')}. Logs: {url_execucao}")
                    return url_execucao
            time.sleep(5)

    if run_id is None:
        raise TimeoutError("GitHub aceitou a solicitacao, mas a execucao nao apareceu a tempo. Confira a aba Actions antes de tentar novamente.")
    raise TimeoutError(f"A sincronizacao ainda nao terminou. Confira: {url_execucao}. Evite disparar novamente.")
