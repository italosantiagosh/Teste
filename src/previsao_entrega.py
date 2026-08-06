"""
Etapa 6 — Cálculo da previsão de entrega (implementado).

Regra definida pelo usuário, mais simples do que o esboço original do
planejamento:

    previsão = data de emissão + N dias corridos

    N = 5 dias, se o pedido já foi embarcado (já possui número de
        manifesto — coluna 'manifesto', vinda de 'Primeiro Manifesto'
        no relatório);
    N = 7 dias, se o pedido ainda não foi embarcado (coluna 'manifesto'
        vazia).

"Dias corridos" = não exclui sábado/domingo (diferente do esboço
original, que previa essa exclusão — foi desligada em
`config/regras_entrega.json` via `excluir_sabados_domingos: false`).

Se a data-base estiver ausente, a previsão fica marcada como
'PREVISÃO NÃO DEFINIDA' — nunca é inventada.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from config import REGRAS_ENTREGA, COLUNAS

logger = logging.getLogger("automacao_transportadora")

PREVISAO_NAO_DEFINIDA = "PREVISÃO NÃO DEFINIDA"


def calcular_previsao_entrega(data_base: date | None, embarcado: bool) -> date | str:
    """Calcula a previsão de entrega para um único pedido.

    Args:
        data_base: data de emissão do pedido (ou outra data-base configurada).
        embarcado: True se o pedido já possui número de manifesto.

    Returns:
        A data prevista (objeto `date`), ou a string
        'PREVISÃO NÃO DEFINIDA' quando `data_base` for None/NaT.
    """
    if data_base is None or (isinstance(data_base, float) and pd.isna(data_base)):
        return PREVISAO_NAO_DEFINIDA

    dias = (
        REGRAS_ENTREGA.get("dias_se_embarcado", 5)
        if embarcado
        else REGRAS_ENTREGA.get("dias_se_nao_embarcado", 7)
    )

    if hasattr(data_base, "date"):
        data_base = data_base.date()

    return data_base + timedelta(days=dias)


def calcular_previsao_dataframe(
    df: pd.DataFrame,
    coluna_saida: str = "previsao_entrega_calculada",
) -> pd.DataFrame:
    """Aplica `calcular_previsao_entrega` a todas as linhas do DataFrame.

    Usa `COLUNAS.col_data_emissao` como data-base e considera "embarcado"
    quando pelo menos uma das colunas de manifesto
    (`COLUNAS.col_chave_cruzamento` ou `COLUNAS.col_chave_cruzamento_fallback`
    — hoje, primeiro ou último manifesto) não está vazia.

    Args:
        df: DataFrame já tratado (saída de `tratamento_planilha`).
        coluna_saida: nome da coluna a criar com a previsão calculada.

    Returns:
        O mesmo DataFrame com a coluna de previsão calculada adicionada.
    """
    col_data = COLUNAS.col_data_emissao
    colunas_manifesto = [
        c for c in (COLUNAS.col_chave_cruzamento, COLUNAS.col_chave_cruzamento_fallback)
        if c in df.columns
    ]

    if col_data not in df.columns:
        logger.warning(
            "Coluna de data-base ('%s') não encontrada — previsão não calculada.",
            col_data,
        )
        df[coluna_saida] = PREVISAO_NAO_DEFINIDA
        return df

    if not colunas_manifesto:
        logger.warning(
            "Nenhuma coluna de manifesto ('%s'/'%s') encontrada — todos os "
            "pedidos serão tratados como NÃO embarcados.",
            COLUNAS.col_chave_cruzamento,
            COLUNAS.col_chave_cruzamento_fallback,
        )
        embarcado_serie = pd.Series(False, index=df.index)
    else:
        embarcado_serie = pd.Series(False, index=df.index)
        for col in colunas_manifesto:
            embarcado_serie |= df[col].notna() & (df[col].astype(str).str.strip() != "")

    previsoes = [
        calcular_previsao_entrega(data_base, embarcado)
        for data_base, embarcado in zip(df[col_data], embarcado_serie)
    ]
    df[coluna_saida] = previsoes

    qtd_nao_definida = sum(1 for p in previsoes if p == PREVISAO_NAO_DEFINIDA)
    if qtd_nao_definida:
        logger.warning(
            "%d pedidos ficaram com previsão NÃO DEFINIDA (data-base ausente).",
            qtd_nao_definida,
        )
    logger.info(
        "Previsão calculada para %d pedidos (%d embarcados, %d não embarcados).",
        len(df),
        int(embarcado_serie.sum()),
        int((~embarcado_serie).sum()),
    )

    return df
