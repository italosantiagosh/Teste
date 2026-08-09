"""Testes do módulo `clientes`: a busca deve considerar só o
Destinatário (coluna 'cliente') — é quem o operador considera o cliente
de fato, mesmo que remetente/pagador sejam outra empresa."""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd

from src import clientes


def _df_exemplo() -> pd.DataFrame:
    return pd.DataFrame([
        {"pedido": "1001", "cliente": "Comercial Nordeste Ltda", "remetente": "Fornecedor A", "pagador": "Pagador X"},
        {"pedido": "1002", "cliente": "Outra Empresa Ltda", "remetente": "Comercial Nordeste Ltda", "pagador": "Pagador Y"},
    ])


def test_busca_encontra_pelo_destinatario():
    df = _df_exemplo()
    encontrados = clientes.buscar_por_nome(df, "comercial nordeste")
    assert set(encontrados["pedido"]) == {"1001"}


def test_busca_nao_considera_remetente_nem_pagador():
    df = _df_exemplo()
    # "Comercial Nordeste Ltda" também aparece como REMETENTE do pedido
    # 1002 — mas a busca é só pelo destinatário, então não deve trazer.
    encontrados = clientes.buscar_por_nome(df, "comercial nordeste")
    assert "1002" not in set(encontrados["pedido"])


def test_selecionar_varios_clientes_interativo_busca_por_destinatario(monkeypatch):
    df = _df_exemplo()
    respostas = iter(["comercial nordeste", "1", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(respostas))

    dados, info = clientes.selecionar_varios_clientes_interativo(df)
    assert set(dados["pedido"]) == {"1001"}
    assert info["nomes"] == ["Comercial Nordeste Ltda"]
