"""
Etapa 7 — Pesquisa de clientes (por CNPJ ou nome) dentro dos dados já
tratados e cruzados.

AINDA NÃO IMPLEMENTADO. Depende do resultado das Etapas 3, 5 e 6 estarem
disponíveis (planilha tratada + motorista + previsão).
"""

from __future__ import annotations

import logging

import pandas as pd

from src.utils import normalizar_cnpj, normalizar_texto

logger = logging.getLogger("automacao_transportadora")


def buscar_por_cnpj(df: pd.DataFrame, cnpj_busca: str, coluna_cnpj: str) -> pd.DataFrame:
    """Busca pedidos de um cliente pelo CNPJ (aceita com ou sem pontuação)."""
    raise NotImplementedError("Etapa 7 será desenvolvida após a Etapa 5/6.")


def buscar_por_nome(df: pd.DataFrame, nome_busca: str, coluna_nome: str) -> pd.DataFrame:
    """Busca pedidos de um cliente pelo nome, tolerando diferenças de
    maiúsculas/minúsculas, acentuação e espaços. Não faz correspondência
    automática entre nomes muito diferentes — nesse caso, deve retornar
    múltiplas opções para o usuário escolher.
    """
    raise NotImplementedError("Etapa 7 será desenvolvida após a Etapa 5/6.")
