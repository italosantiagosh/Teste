"""
Etapa 5 — Cruzamento entre a planilha principal (pedidos) e a tabela de
motoristas, usando o número do manifesto como chave.

Importante: a relação é N pedidos -> 1 manifesto -> 1 motorista (vários
pedidos costumam viajar no mesmo manifesto/carga). Por isso o merge é
"muitos-para-um" do lado dos pedidos. Um "conflito" acontece quando a
PRÓPRIA tabela de motoristas tem mais de um registro para o mesmo
manifesto (ex.: reimpressão/reprocessamento) — nesse caso, não é
escolhido automaticamente qual motorista vale; o registro fica separado
para conferência humana.
"""

from __future__ import annotations

import logging

import pandas as pd

from config import COLUNAS
from src.utils import normalizar_identificador

logger = logging.getLogger("automacao_transportadora")


def _normalizar_coluna_chave(serie: pd.Series) -> pd.Series:
    return serie.apply(normalizar_identificador)


def cruzar_pedidos_motoristas(
    df_pedidos: pd.DataFrame,
    df_motoristas: pd.DataFrame,
    coluna_chave_pedidos: str | None = None,
    coluna_chave_motoristas: str = "manifesto",
) -> dict[str, pd.DataFrame]:
    """Cruza pedidos com motoristas pela chave configurada.

    Args:
        df_pedidos: DataFrame de pedidos já tratado (Etapa 3), contendo a
            coluna `coluna_chave_pedidos` com a chave de cruzamento.
        df_motoristas: DataFrame capturado da tela de motoristas (Etapa 4),
            contendo a coluna `coluna_chave_motoristas` com o número do
            manifesto e as colunas de motorista/placa/status.
        coluna_chave_pedidos: nome da coluna-chave no DataFrame de pedidos.
            Se não informado, usa `config.COLUNAS.col_chave_cruzamento`
            (configurável em `config/colunas.json` — pedido, nota fiscal,
            número da carga, CT-e etc.).
        coluna_chave_motoristas: nome da coluna-chave no DataFrame de
            motoristas.

    Returns:
        Dicionário com as chaves:
          - 'com_motorista': pedidos com motorista associado com sucesso;
          - 'sem_motorista': pedidos cujo manifesto não foi encontrado na
            tabela de motoristas (ou cujo manifesto está em conflito);
          - 'motoristas_sem_pedido': registros de motoristas cujo manifesto
            não aparece em nenhum pedido;
          - 'conflitos': registros da tabela de motoristas onde o mesmo
            manifesto aparece mais de uma vez (não resolvido automaticamente).
    """
    coluna_chave_pedidos = coluna_chave_pedidos or COLUNAS.col_chave_cruzamento

    pedidos = df_pedidos.copy()
    motoristas = df_motoristas.copy()

    pedidos["_chave"] = _normalizar_coluna_chave(pedidos[coluna_chave_pedidos])
    motoristas["_chave"] = _normalizar_coluna_chave(motoristas[coluna_chave_motoristas])

    # 1) Identifica conflitos: manifesto duplicado na PRÓPRIA tabela de motoristas
    contagem_chave = motoristas["_chave"].value_counts()
    chaves_em_conflito = set(contagem_chave[contagem_chave > 1].index) - {""}

    conflitos = motoristas[motoristas["_chave"].isin(chaves_em_conflito)].drop(columns=["_chave"])
    motoristas_validos = motoristas[~motoristas["_chave"].isin(chaves_em_conflito)]

    if chaves_em_conflito:
        logger.warning(
            "Manifestos com mais de um registro de motorista (conflito, "
            "não resolvido automaticamente): %s",
            sorted(chaves_em_conflito),
        )

    # 2) Merge muitos-para-um: pedidos -> motoristas válidos (sem conflito)
    resultado = pedidos.merge(
        motoristas_validos,
        on="_chave",
        how="left",
        suffixes=("", "_motorista"),
        indicator=True,
    )

    # Pedidos cujo manifesto caiu em conflito também vão para "sem_motorista",
    # marcados explicitamente, para não ficarem escondidos entre os sem match.
    pedidos_em_conflito_mask = resultado["_chave"].isin(chaves_em_conflito)

    com_motorista = resultado[
        (resultado["_merge"] == "both") & (~pedidos_em_conflito_mask)
    ].drop(columns=["_chave", "_merge"])

    sem_motorista = resultado[
        (resultado["_merge"] == "left_only") | pedidos_em_conflito_mask
    ].drop(columns=["_chave", "_merge"])

    # 3) Motoristas (válidos) cujo manifesto não aparece em nenhum pedido
    chaves_pedidos = set(pedidos["_chave"]) - {""}
    motoristas_sem_pedido = motoristas_validos[
        ~motoristas_validos["_chave"].isin(chaves_pedidos)
    ].drop(columns=["_chave"])

    logger.info(
        "Cruzamento concluído | pedidos com motorista: %d | pedidos sem "
        "motorista/conflito: %d | motoristas sem pedido correspondente: %d | "
        "manifestos em conflito: %d",
        len(com_motorista),
        len(sem_motorista),
        len(motoristas_sem_pedido),
        len(chaves_em_conflito),
    )

    return {
        "com_motorista": com_motorista,
        "sem_motorista": sem_motorista,
        "motoristas_sem_pedido": motoristas_sem_pedido,
        "conflitos": conflitos,
    }
