"""Cruzamento da planilha de entregas com a tabela de manifestos/motoristas."""

from __future__ import annotations

import logging
import re

import pandas as pd

logger = logging.getLogger("automacao_transportadora")


def normalizar_manifesto(valor: object) -> str:
    """Normaliza manifesto sem perder zeros ou dígito verificador.

    Exemplos equivalentes:
      ``GRU 002423-6`` -> ``GRU0024236``
      ``GRU0024236``   -> ``GRU0024236``
    """
    if valor is None or pd.isna(valor):
        return ""
    texto = str(valor).strip().upper()
    if not texto or texto == "NAN":
        return ""
    texto = re.sub(r"\.0$", "", texto)
    return re.sub(r"[^A-Z0-9]", "", texto)


def _preparar_mapa_motoristas(
    df_motoristas: pd.DataFrame,
    coluna_chave: str,
) -> tuple[pd.DataFrame, set[str], pd.DataFrame]:
    """Prepara registros únicos e separa manifestos ambíguos."""
    motoristas = df_motoristas.copy()
    motoristas["_manifesto_normalizado"] = motoristas[coluna_chave].map(normalizar_manifesto)
    motoristas = motoristas[motoristas["_manifesto_normalizado"] != ""].copy()

    # Um mesmo manifesto repetido com dados idênticos não é conflito real.
    colunas_identidade = [
        c for c in ["_manifesto_normalizado", "motorista", "cavalo", "carreta"]
        if c in motoristas.columns
    ]
    motoristas = motoristas.drop_duplicates(subset=colunas_identidade)

    qtd_motoristas = motoristas.groupby("_manifesto_normalizado")["motorista"].nunique(dropna=False)
    chaves_conflito = set(qtd_motoristas[qtd_motoristas > 1].index)

    conflitos = motoristas[
        motoristas["_manifesto_normalizado"].isin(chaves_conflito)
    ].drop(columns=["_manifesto_normalizado"], errors="ignore")

    validos = motoristas[
        ~motoristas["_manifesto_normalizado"].isin(chaves_conflito)
    ].drop_duplicates(subset=["_manifesto_normalizado"], keep="first")

    return validos, chaves_conflito, conflitos


def cruzar_pedidos_motoristas(
    df_pedidos: pd.DataFrame,
    df_motoristas: pd.DataFrame,
    coluna_primeiro_manifesto: str = "primeiro_manifesto",
    coluna_ultimo_manifesto: str = "ultimo_manifesto",
    coluna_chave_motoristas: str = "manifesto",
) -> dict[str, pd.DataFrame]:
    """Associa motorista tentando o primeiro e depois o último manifesto.

    A tela 023 consultada em GRU normalmente corresponde ao primeiro manifesto.
    Por isso ele é a chave principal. O último manifesto funciona como fallback
    para cargas em que o primeiro esteja vazio ou não seja encontrado.

    São incluídas as colunas de auditoria:
      - ``manifesto_usado_motorista``
      - ``origem_vinculo_motorista`` (PRIMEIRO MANIFESTO / ÚLTIMO MANIFESTO)
    """
    for coluna in (coluna_primeiro_manifesto, coluna_ultimo_manifesto):
        if coluna not in df_pedidos.columns:
            raise ValueError(
                f"A planilha tratada não contém a coluna '{coluna}'. "
                f"Colunas existentes: {list(df_pedidos.columns)}"
            )
    if coluna_chave_motoristas not in df_motoristas.columns:
        raise ValueError(
            f"A tabela de motoristas não contém a coluna '{coluna_chave_motoristas}'."
        )
    if "motorista" not in df_motoristas.columns:
        raise ValueError("A tabela capturada não contém a coluna 'motorista'.")

    pedidos = df_pedidos.copy()
    validos, chaves_conflito, conflitos = _preparar_mapa_motoristas(
        df_motoristas, coluna_chave_motoristas
    )

    pedidos["_primeiro_norm"] = pedidos[coluna_primeiro_manifesto].map(normalizar_manifesto)
    pedidos["_ultimo_norm"] = pedidos[coluna_ultimo_manifesto].map(normalizar_manifesto)

    colunas_dados = [
        c for c in [
            "motorista", "cavalo", "carreta", "origem", "destino", "unid",
            "saida", "prev_chegada", "chegada", "situacao_mdfe"
        ] if c in validos.columns
    ]
    mapa = validos.set_index("_manifesto_normalizado")[colunas_dados].to_dict("index")

    def escolher_manifesto(linha: pd.Series) -> tuple[str, str, str]:
        primeiro = linha["_primeiro_norm"]
        ultimo = linha["_ultimo_norm"]

        if primeiro in chaves_conflito:
            return primeiro, "PRIMEIRO MANIFESTO", "CONFLITO DE MANIFESTO"
        if primeiro and primeiro in mapa:
            return primeiro, "PRIMEIRO MANIFESTO", "ENCONTRADO"

        if ultimo in chaves_conflito:
            return ultimo, "ÚLTIMO MANIFESTO", "CONFLITO DE MANIFESTO"
        if ultimo and ultimo in mapa:
            return ultimo, "ÚLTIMO MANIFESTO", "ENCONTRADO"

        if not primeiro and not ultimo:
            return "", "", "SEM MANIFESTO"
        return primeiro or ultimo, "", "NÃO ENCONTRADO"

    escolhas = pedidos.apply(escolher_manifesto, axis=1, result_type="expand")
    escolhas.columns = ["_manifesto_escolhido", "origem_vinculo_motorista", "_status_vinculo"]
    pedidos = pd.concat([pedidos, escolhas], axis=1)

    pedidos["manifesto_usado_motorista"] = ""
    usa_primeiro = pedidos["origem_vinculo_motorista"].eq("PRIMEIRO MANIFESTO")
    usa_ultimo = pedidos["origem_vinculo_motorista"].eq("ÚLTIMO MANIFESTO")
    pedidos.loc[usa_primeiro, "manifesto_usado_motorista"] = pedidos.loc[
        usa_primeiro, coluna_primeiro_manifesto
    ].fillna("")
    pedidos.loc[usa_ultimo, "manifesto_usado_motorista"] = pedidos.loc[
        usa_ultimo, coluna_ultimo_manifesto
    ].fillna("")

    # Remove eventual coluna antiga e popula os dados capturados.
    pedidos = pedidos.drop(columns=colunas_dados, errors="ignore")
    for coluna in colunas_dados:
        pedidos[coluna] = pedidos["_manifesto_escolhido"].map(
            lambda chave, c=coluna: mapa.get(chave, {}).get(c) if chave in mapa else None
        )

    pedidos["motorista"] = pedidos.get("motorista", pd.Series(index=pedidos.index, dtype="object"))
    pedidos.loc[pedidos["_status_vinculo"] != "ENCONTRADO", "motorista"] = pedidos.loc[
        pedidos["_status_vinculo"] != "ENCONTRADO", "_status_vinculo"
    ]

    encontrado = pedidos["_status_vinculo"].eq("ENCONTRADO")
    com_motorista = pedidos[encontrado].copy()
    sem_motorista = pedidos[~encontrado].copy()

    chaves_usadas = set(pedidos.loc[encontrado, "_manifesto_escolhido"])
    motoristas_sem_pedido = validos[
        ~validos["_manifesto_normalizado"].isin(chaves_usadas)
    ].drop(columns=["_manifesto_normalizado"], errors="ignore")

    colunas_auxiliares = ["_primeiro_norm", "_ultimo_norm", "_manifesto_escolhido", "_status_vinculo"]
    for frame in (pedidos, com_motorista, sem_motorista):
        frame.drop(columns=colunas_auxiliares, inplace=True, errors="ignore")

    # Posiciona as colunas de auditoria e motorista perto dos manifestos.
    ordem_preferida = [
        "pedido", "cliente", "cidade", "data_emissao",
        coluna_primeiro_manifesto, coluna_ultimo_manifesto,
        "manifesto_usado_motorista", "origem_vinculo_motorista",
        "motorista", "placa_cavalo", "status", "previsao_entrega",
    ]
    for nome, frame in (("pedidos", pedidos), ("com", com_motorista), ("sem", sem_motorista)):
        presentes = [c for c in ordem_preferida if c in frame.columns]
        extras = [c for c in frame.columns if c not in presentes]
        reorganizado = frame[presentes + extras]
        if nome == "pedidos":
            pedidos = reorganizado
        elif nome == "com":
            com_motorista = reorganizado
        else:
            sem_motorista = reorganizado

    logger.info(
        "Cruzamento concluído | pedidos totais: %d | com motorista: %d | "
        "sem correspondência/conflito: %d | pelo primeiro manifesto: %d | "
        "pelo último manifesto: %d | motoristas sem pedido: %d | conflitos: %d",
        len(pedidos),
        len(com_motorista),
        len(sem_motorista),
        int((com_motorista["origem_vinculo_motorista"] == "PRIMEIRO MANIFESTO").sum()),
        int((com_motorista["origem_vinculo_motorista"] == "ÚLTIMO MANIFESTO").sum()),
        len(motoristas_sem_pedido),
        len(conflitos),
    )

    return {
        "relatorio_completo": pedidos,
        "com_motorista": com_motorista,
        "sem_motorista": sem_motorista,
        "motoristas_sem_pedido": motoristas_sem_pedido,
        "conflitos": conflitos,
    }
