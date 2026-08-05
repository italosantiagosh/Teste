"""
Etapa 3 — Tratamento da planilha principal de pedidos/entregas.

Este módulo NÃO acessa navegador nem sistema real: recebe um caminho de
arquivo (planilha já baixada) e devolve um DataFrame tratado, além de
registrar no log tudo que foi alterado/removido — nada é descartado
silenciosamente.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config import COLUNAS, SAIDA_DIR
from src.utils import normalizar_cnpj, formatar_cnpj, normalizar_identificador, normalizar_texto

logger = logging.getLogger("automacao_transportadora")


def ler_planilha(caminho_arquivo: Path) -> pd.DataFrame:
    """Lê o relatório baixado, identificando corretamente o cabeçalho.

    Suporta dois formatos:
      - .xlsx: cabeçalho na primeira linha (padrão pandas.read_excel).
      - .csv: formato específico do relatório do sistema SSW — a
        primeira linha é um título do relatório (não é cabeçalho), a
        segunda linha traz os nomes das colunas, o separador é ';' e o
        encoding é latin1. Cada linha (título, cabeçalho e dados) começa
        com uma coluna marcadora ('0', '1' ou '2') que é descartada.

    Args:
        caminho_arquivo: caminho do arquivo baixado (.xlsx ou .csv).

    Returns:
        DataFrame com os dados brutos (ainda sem tratamento).

    Raises:
        FileNotFoundError: se o arquivo não existir.
        ValueError: se a extensão do arquivo não for suportada.
    """
    if not caminho_arquivo.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")

    extensao = caminho_arquivo.suffix.lower()

    if extensao == ".xlsx":
        df = pd.read_excel(caminho_arquivo, dtype=str)
    elif extensao == ".csv":
        df = pd.read_csv(
            caminho_arquivo,
            sep=";",
            skiprows=1,  # pula a linha de título do relatório
            encoding="latin1",
            dtype=str,
            engine="python",
        )
        # A primeira coluna é apenas o marcador de tipo de linha ('1' no
        # cabeçalho lido, '2' em cada linha de dado) — não é dado real.
        primeira_coluna = df.columns[0]
        df = df.drop(columns=[primeira_coluna])
        # Colunas "Unnamed: N" surgem de ';' sobrando no fim de cada linha
        # do CSV (sem cabeçalho correspondente) — são descartadas se vazias.
        colunas_unnamed_vazias = [
            c for c in df.columns if c.startswith("Unnamed:") and df[c].isna().all()
        ]
        if colunas_unnamed_vazias:
            df = df.drop(columns=colunas_unnamed_vazias)
    else:
        raise ValueError(
            f"Extensão de arquivo não suportada: '{extensao}'. Use .xlsx ou .csv."
        )

    logger.info(
        "Planilha lida: %s | %d linhas | %d colunas",
        caminho_arquivo.name,
        len(df),
        len(df.columns),
    )
    return df


def remover_linhas_vazias(df: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas completamente vazias."""
    linhas_antes = len(df)
    df = df.dropna(how="all")
    removidas = linhas_antes - len(df)
    if removidas:
        logger.info("Linhas completamente vazias removidas: %d", removidas)
    return df


def remover_colunas_desnecessarias(df: pd.DataFrame) -> pd.DataFrame:
    """Remove as colunas configuradas em `colunas_excluir`, avisando se alguma
    não existir na planilha (sinal de que a configuração pode estar desatualizada).
    """
    colunas_configuradas = set(COLUNAS.colunas_excluir)
    colunas_existentes = colunas_configuradas & set(df.columns)
    colunas_ausentes = colunas_configuradas - set(df.columns)

    if colunas_ausentes:
        logger.warning(
            "Colunas configuradas para exclusão mas não encontradas na planilha: %s",
            sorted(colunas_ausentes),
        )

    if colunas_existentes:
        df = df.drop(columns=list(colunas_existentes))
        logger.info("Colunas removidas: %s", sorted(colunas_existentes))

    return df


def renomear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas conforme `mapa_renomeacao`, avisando sobre colunas
    esperadas que não foram encontradas na origem.
    """
    mapa = COLUNAS.mapa_renomeacao
    colunas_origem_ausentes = set(mapa.keys()) - set(df.columns)

    if colunas_origem_ausentes:
        logger.warning(
            "Colunas esperadas (nome original) não encontradas na planilha: %s",
            sorted(colunas_origem_ausentes),
        )

    df = df.rename(columns=mapa)
    return df


def reorganizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Reordena as colunas conforme `ordem_final`.

    Colunas presentes na configuração mas ausentes no DataFrame são
    ignoradas (com aviso). Colunas do DataFrame que não constam na
    configuração são mantidas ao final, para não perder dado nenhum.
    """
    ordem_configurada = COLUNAS.ordem_final
    ordem_presente = [c for c in ordem_configurada if c in df.columns]
    ordem_ausente = [c for c in ordem_configurada if c not in df.columns]
    extras = [c for c in df.columns if c not in ordem_configurada]

    if ordem_ausente:
        logger.warning(
            "Colunas configuradas em 'ordem_final' mas ausentes após renomeação: %s",
            ordem_ausente,
        )
    if extras:
        logger.info(
            "Colunas fora de 'ordem_final' mantidas ao final: %s", extras
        )

    return df[ordem_presente + extras]


def tratar_cnpj(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza o CNPJ para comparação e cria uma coluna formatada para exibição."""
    col = COLUNAS.col_cnpj
    if col not in df.columns:
        logger.warning("Coluna de CNPJ ('%s') não encontrada — etapa ignorada.", col)
        return df

    df[col] = df[col].apply(normalizar_cnpj)
    df[f"{col}_formatado"] = df[col].apply(formatar_cnpj)
    return df


def tratar_identificadores(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza colunas de identificador (pedido e chave de cruzamento).

    O número do pedido não pode ser tratado como sempre numérico: quando a
    célula de origem é lida pelo Excel como número, `pandas.read_excel`
    devolve o texto com sufixo '.0' (ex.: '1002.0') mesmo pedindo
    `dtype=str`, porque a conversão para texto acontece depois da leitura
    do valor numérico da célula. Sem este passo, o pedido apareceria com
    '.0' na planilha tratada e possivelmente na mensagem final ao cliente,
    e dois pedidos iguais só com essa diferença de formato deixariam de
    ser identificados como duplicados.
    """
    colunas_identificador = {COLUNAS.col_pedido, COLUNAS.col_chave_cruzamento}

    for coluna in colunas_identificador:
        if coluna not in df.columns:
            continue
        antes = df[coluna].copy()
        df[coluna] = df[coluna].apply(normalizar_identificador)
        alterados = int((antes.fillna("") != df[coluna].fillna("")).sum())
        if alterados:
            logger.info(
                "Coluna '%s': %d valor(es) normalizado(s) (ex.: sufixo "
                "'.0' de conversão do Excel removido).",
                coluna,
                alterados,
            )

    return df


def _parse_data_robusta(serie: pd.Series) -> pd.Series:
    """Converte uma série de datas testando formatos explícitos, em ordem.

    Evita a ambiguidade do `dayfirst` do pandas quando a coluna mistura
    formatos (ex.: '01/08/2026' e '2026-08-01' na mesma planilha), que pode
    interpretar uma data ISO incorretamente. Cada valor é testado contra os
    formatos até um bater; se nenhum bater, o valor vira NaT.
    """
    formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]
    resultado = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")

    for fmt in formatos:
        pendentes = resultado.isna() & serie.notna()
        if not pendentes.any():
            break
        tentativa = pd.to_datetime(serie[pendentes], format=fmt, errors="coerce")
        resultado.loc[tentativa.index] = tentativa

    return resultado


def tratar_datas(df: pd.DataFrame) -> pd.DataFrame:
    """Converte a coluna de data de emissão para datetime, registrando falhas."""
    col = COLUNAS.col_data_emissao
    if col not in df.columns:
        logger.warning("Coluna de data ('%s') não encontrada — etapa ignorada.", col)
        return df

    antes_nulos = df[col].isna().sum()
    df[col] = _parse_data_robusta(df[col])
    depois_nulos = df[col].isna().sum()

    falhas_conversao = depois_nulos - antes_nulos
    if falhas_conversao > 0:
        logger.warning(
            "%d valores em '%s' não puderam ser convertidos para data.",
            falhas_conversao,
            col,
        )
    return df


def normalizar_textuais(df: pd.DataFrame) -> pd.DataFrame:
    """Remove espaços extras de todas as colunas de texto (não normaliza
    para minúsculas — isso é feito apenas em colunas auxiliares de busca).
    """
    for coluna in df.select_dtypes(include=["object", "str"]).columns:
        df[coluna] = df[coluna].apply(
            lambda v: v.strip() if isinstance(v, str) else v
        )
    return df


def identificar_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """Identifica pedidos duplicados (mesmo número de pedido), sem removê-los
    automaticamente. Adiciona a coluna 'duplicado' (True/False).
    """
    col = COLUNAS.col_pedido
    if col not in df.columns:
        logger.warning("Coluna de pedido ('%s') não encontrada — etapa ignorada.", col)
        return df

    df["duplicado"] = df.duplicated(subset=[col], keep=False)
    qtd_duplicados = int(df["duplicado"].sum())
    if qtd_duplicados:
        logger.warning("Pedidos duplicados encontrados: %d", qtd_duplicados)
    else:
        logger.info("Nenhum pedido duplicado encontrado.")

    return df


def tratar_planilha(caminho_arquivo: Path, salvar_intermediaria: bool = True) -> pd.DataFrame:
    """Executa o pipeline completo de tratamento da planilha principal.

    Args:
        caminho_arquivo: caminho do arquivo baixado.
        salvar_intermediaria: se True, salva uma versão intermediária logo
            após a leitura (útil para conferência).

    Returns:
        DataFrame tratado (versão final).
    """
    df = ler_planilha(caminho_arquivo)
    linhas_recebidas = len(df)

    if salvar_intermediaria:
        caminho_intermediario = SAIDA_DIR / f"{caminho_arquivo.stem}_bruto.xlsx"
        df.to_excel(caminho_intermediario, index=False)
        logger.info("Versão intermediária (bruta) salva em: %s", caminho_intermediario)

    df = remover_linhas_vazias(df)
    df = remover_colunas_desnecessarias(df)
    df = renomear_colunas(df)
    df = reorganizar_colunas(df)
    df = tratar_cnpj(df)
    df = tratar_identificadores(df)
    df = tratar_datas(df)
    df = normalizar_textuais(df)
    df = identificar_duplicados(df)

    caminho_final = SAIDA_DIR / f"{caminho_arquivo.stem}_tratado.xlsx"
    df.to_excel(caminho_final, index=False)

    logger.info(
        "Tratamento concluído | linhas recebidas: %d | linhas finais: %d | "
        "duplicados: %d | arquivo final: %s",
        linhas_recebidas,
        len(df),
        int(df.get("duplicado", pd.Series(dtype=bool)).sum()),
        caminho_final,
    )

    return df
