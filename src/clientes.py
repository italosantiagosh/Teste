"""Pesquisa e seleção de clientes nos relatórios processados."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from src.utils import normalizar_cnpj, normalizar_texto

logger = logging.getLogger("automacao_transportadora")


def buscar_por_cnpj(df: pd.DataFrame, cnpj_busca: str, coluna_cnpj: str = "cnpj") -> pd.DataFrame:
    if coluna_cnpj not in df.columns:
        return df.iloc[0:0].copy()
    alvo = normalizar_cnpj(cnpj_busca)
    if not alvo:
        return df.iloc[0:0].copy()
    serie = df[coluna_cnpj].map(normalizar_cnpj)
    return df.loc[serie == alvo].copy()


def buscar_por_nome(df: pd.DataFrame, nome_busca: str, coluna_nome: str = "cliente") -> pd.DataFrame:
    if coluna_nome not in df.columns:
        raise ValueError(f"Coluna de cliente não encontrada: {coluna_nome}")
    alvo = normalizar_texto(nome_busca)
    if not alvo:
        return df.iloc[0:0].copy()
    serie = df[coluna_nome].fillna("").map(normalizar_texto)
    return df.loc[serie.str.contains(alvo, regex=False, na=False)].copy()


def listar_clientes_encontrados(df: pd.DataFrame, coluna_nome: str = "cliente", coluna_cnpj: str = "cnpj") -> pd.DataFrame:
    colunas = [coluna_nome]
    if coluna_cnpj in df.columns:
        colunas.append(coluna_cnpj)
    resultado = df[colunas].drop_duplicates().copy()
    return resultado.sort_values(colunas, na_position="last").reset_index(drop=True)


def selecionar_cliente_interativo(
    df: pd.DataFrame,
    coluna_nome: str = "cliente",
    coluna_cnpj: str = "cnpj",
) -> tuple[pd.DataFrame, dict[str, str]]:
    termo = input("Digite parte do nome do cliente ou o CNPJ: ").strip()
    if not termo:
        raise ValueError("Nenhum cliente informado.")

    apenas_digitos = "".join(c for c in termo if c.isdigit())
    if len(apenas_digitos) >= 8 and coluna_cnpj in df.columns:
        encontrados = buscar_por_cnpj(df, termo, coluna_cnpj)
    else:
        encontrados = buscar_por_nome(df, termo, coluna_nome)

    if encontrados.empty:
        raise ValueError("Nenhum cliente encontrado.")

    opcoes = listar_clientes_encontrados(encontrados, coluna_nome, coluna_cnpj)
    print("\nClientes encontrados:")
    for indice, linha in opcoes.iterrows():
        cnpj = str(linha.get(coluna_cnpj, "")).strip()
        complemento = f" | {cnpj}" if cnpj and cnpj.lower() != "nan" else ""
        print(f"{indice + 1} - {linha[coluna_nome]}{complemento}")

    if len(opcoes) == 1:
        escolha = 0
    else:
        resposta = input("Escolha o número do cliente: ").strip()
        if not resposta.isdigit() or not (1 <= int(resposta) <= len(opcoes)):
            raise ValueError("Escolha inválida.")
        escolha = int(resposta) - 1

    selecionado = opcoes.iloc[escolha]
    nome = str(selecionado[coluna_nome])
    filtro = df[coluna_nome].astype(str) == nome
    cnpj = ""
    if coluna_cnpj in df.columns and coluna_cnpj in selecionado.index:
        cnpj = str(selecionado.get(coluna_cnpj, "")).strip()
        if cnpj and cnpj.lower() != "nan":
            filtro &= df[coluna_cnpj].astype(str) == cnpj

    dados = df.loc[filtro].copy()
    info = {"nome": nome, "cnpj": "" if cnpj.lower() == "nan" else cnpj}
    return dados, info


def salvar_selecao(dados: pd.DataFrame, info: dict[str, str], pasta_saida: Path) -> tuple[Path, Path]:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    planilha = pasta_saida / "cliente_selecionado.xlsx"
    metadados = pasta_saida / "cliente_selecionado.json"
    dados.to_excel(planilha, index=False)
    metadados.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return planilha, metadados
