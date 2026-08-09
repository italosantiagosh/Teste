"""Testes do módulo `mensagem`: filtro de cargas 'saída para entrega'
antigas e formato da mensagem (sem a previsão no texto)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd

from src import mensagem


def _pedido(**kwargs) -> dict:
    base = {
        "pedido": "1001",
        "cliente": "Cliente Teste",
        "remetente": "Remetente Teste",
        "pagador": "Pagador Teste",
        "cidade": "Natal",
        "nf": "555",
        "peso_real": "10,5",
        "volumes": "1",
        "valor_frete": "100,00",
        "motorista": "Fulano de Tal",
        "status": "Em transito",
    }
    base.update(kwargs)
    return base


def test_filtrar_remove_saida_para_entrega_antiga_sem_data_no_texto():
    # Caso real: "Saida para entrega na cidade de X." não tem NENHUMA data
    # escrita no texto — só a coluna 'data_ultima_ocorrencia' (vinda do
    # sistema) tem essa informação.
    df = pd.DataFrame([
        _pedido(
            pedido="1001",
            status="Saida para entrega na cidade de ALTO DO RODRIGUES.",
            data_ultima_ocorrencia="05/08/2026",
        ),
        _pedido(pedido="1002", status="Em transito"),
    ])
    filtrado = mensagem.filtrar_pedidos_para_mensagem(df, data_referencia=date(2026, 8, 9))
    assert set(filtrado["pedido"]) == {"1002"}


def test_filtrar_remove_saida_para_entrega_antiga_com_data_no_texto():
    df = pd.DataFrame([
        _pedido(pedido="1001", status="Saida para entrega em 05/08/26, 09:00h."),
        _pedido(pedido="1002", status="Em transito"),
    ])
    filtrado = mensagem.filtrar_pedidos_para_mensagem(df, data_referencia=date(2026, 8, 9))
    assert set(filtrado["pedido"]) == {"1002"}


def test_filtrar_mantem_saida_para_entrega_recente():
    df = pd.DataFrame([
        _pedido(pedido="1001", status="Saiu para entrega na cidade de X.", data_ultima_ocorrencia="08/08/2026"),
    ])
    filtrado = mensagem.filtrar_pedidos_para_mensagem(df, data_referencia=date(2026, 8, 9))
    assert set(filtrado["pedido"]) == {"1001"}


def test_filtrar_mantem_status_sem_relacao_com_saida_para_entrega():
    df = pd.DataFrame([
        _pedido(pedido="1001", status="Pendente ha 10 dias sem nenhuma movimentacao"),
    ])
    filtrado = mensagem.filtrar_pedidos_para_mensagem(df, data_referencia=date(2026, 8, 9))
    assert set(filtrado["pedido"]) == {"1001"}


def test_filtrar_dataframe_vazio_nao_quebra():
    df = pd.DataFrame(columns=["pedido", "status"])
    filtrado = mensagem.filtrar_pedidos_para_mensagem(df)
    assert filtrado.empty


def test_filtrar_remove_situacao_em_conferencia_independente_da_data():
    df = pd.DataFrame([
        _pedido(
            pedido="1001",
            status="MERCADORIA EM CONFERENCIA NO CLIENTE EM 09/08/26 09:00H (OPC 038).",
            data_ultima_ocorrencia="09/08/2026",  # hoje mesmo, mas já é pra excluir
        ),
        _pedido(pedido="1002", status="Em transito"),
    ])
    filtrado = mensagem.filtrar_pedidos_para_mensagem(df, data_referencia=date(2026, 8, 9))
    assert set(filtrado["pedido"]) == {"1002"}


def test_filtrar_remove_entrega_realizada():
    df = pd.DataFrame([
        _pedido(pedido="1001", status="Entrega realizada ao destinatario."),
        _pedido(pedido="1002", status="Em transito"),
    ])
    filtrado = mensagem.filtrar_pedidos_para_mensagem(df, data_referencia=date(2026, 8, 9))
    assert set(filtrado["pedido"]) == {"1002"}


def test_mensagem_nao_contem_previsao():
    df = pd.DataFrame([_pedido(previsao_entrega="20/08/2026")])
    texto = mensagem.montar_mensagem_clientes(df)
    assert "Previsão" not in texto
    assert "*Situação:* Em transito" in texto


def test_mensagem_contem_dados_da_carga():
    df = pd.DataFrame([_pedido()])
    texto = mensagem.montar_mensagem_clientes(df)
    assert "*Remetente:* Remetente Teste" in texto
    assert "*Pagador:* Pagador Teste" in texto
    assert "*NF:* 555" in texto
    assert "*Peso:* 10,50 kg" in texto
    assert "*Vr Frete:* R$ 100,00" in texto


def test_mensagem_titulo_em_negrito():
    df = pd.DataFrame([_pedido()])
    texto = mensagem.montar_mensagem_clientes(df, data_referencia="09/08/2026")
    assert "*POSIÇÃO DE CARGAS — 09/08/2026*" in texto
