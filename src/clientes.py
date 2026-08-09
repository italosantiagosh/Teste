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


# Colunas onde um nome de cliente pode aparecer: o relatório real não traz
# CNPJ, então a busca é sempre por nome, em qualquer um desses papéis
# (quem manda a carga, quem paga o frete ou quem recebe).
COLUNAS_NOME_CLIENTE = ("remetente", "pagador", "cliente")


def buscar_por_nome(
    df: pd.DataFrame,
    nome_busca: str,
    colunas_nome: "tuple[str, ...] | list[str]" = COLUNAS_NOME_CLIENTE,
) -> pd.DataFrame:
    colunas_presentes = [c for c in colunas_nome if c in df.columns]
    if not colunas_presentes:
        raise ValueError(f"Nenhuma coluna de cliente encontrada: {colunas_nome}")

    alvo = normalizar_texto(nome_busca)
    if not alvo:
        return df.iloc[0:0].copy()

    mascara = pd.Series(False, index=df.index)
    for coluna in colunas_presentes:
        mascara |= df[coluna].fillna("").map(normalizar_texto).str.contains(alvo, regex=False, na=False)

    return df.loc[mascara].copy()


def listar_clientes_encontrados(df: pd.DataFrame, coluna_nome: str = "cliente", coluna_cnpj: str = "cnpj") -> pd.DataFrame:
    colunas = [coluna_nome]
    if coluna_cnpj in df.columns:
        colunas.append(coluna_cnpj)
    resultado = df[colunas].drop_duplicates().copy()
    return resultado.sort_values(colunas, na_position="last").reset_index(drop=True)


def _nomes_distintos(df: pd.DataFrame, colunas_nome: "tuple[str, ...] | list[str]") -> list[str]:
    """Reúne os nomes distintos presentes nas colunas de cliente das linhas
    encontradas, para o operador escolher exatamente qual empresa juntar
    na mensagem."""
    nomes: set[str] = set()
    for coluna in colunas_nome:
        if coluna not in df.columns:
            continue
        nomes.update(v.strip() for v in df[coluna].dropna().astype(str) if v.strip())
    return sorted(nomes)


def selecionar_varios_clientes_interativo(
    df: pd.DataFrame,
    colunas_nome: "tuple[str, ...] | list[str]" = COLUNAS_NOME_CLIENTE,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Permite juntar as cargas de mais de um cliente (por nome) em uma
    única mensagem — útil quando uma mesma pessoa cuida de várias empresas.

    Pergunta um nome por vez; a cada nome adicionado, pergunta se o
    operador quer incluir mais algum antes de fechar a seleção.
    """
    colunas_presentes = [c for c in colunas_nome if c in df.columns]
    if not colunas_presentes:
        raise ValueError(
            "A planilha não contém colunas de cliente (remetente/pagador/destinatário)."
        )

    nomes_selecionados: list[str] = []
    partes: list[pd.DataFrame] = []

    while True:
        termo = input("Digite parte do nome do cliente: ").strip()
        if not termo:
            print("Nenhum nome informado.")
        else:
            encontrados = buscar_por_nome(df, termo, colunas_presentes)
            if encontrados.empty:
                print("Nenhum cliente encontrado com esse nome.")
            else:
                opcoes = _nomes_distintos(encontrados, colunas_presentes)
                print("\nNomes encontrados:")
                for indice, nome in enumerate(opcoes, 1):
                    print(f"{indice} - {nome}")

                resposta = input("Escolha o número do nome a adicionar: ").strip()
                if resposta.isdigit() and 1 <= int(resposta) <= len(opcoes):
                    nome_escolhido = opcoes[int(resposta) - 1]
                    if nome_escolhido in nomes_selecionados:
                        print(f"'{nome_escolhido}' já está na mensagem.")
                    else:
                        filtro = pd.Series(False, index=df.index)
                        for coluna in colunas_presentes:
                            filtro |= df[coluna].astype(str).str.strip() == nome_escolhido
                        partes.append(df.loc[filtro].copy())
                        nomes_selecionados.append(nome_escolhido)
                        print(f"'{nome_escolhido}' adicionado à mensagem.")
                else:
                    print("Escolha inválida — nada foi adicionado.")

        resposta_continuar = input(
            "Adicionar outro cliente à mensagem? (s/n): "
        ).strip().lower()
        if resposta_continuar != "s":
            break

    if not partes:
        raise ValueError("Nenhum cliente foi selecionado.")

    dados = pd.concat(partes).drop_duplicates()
    info = {"nome": " + ".join(nomes_selecionados), "nomes": nomes_selecionados}
    return dados, info


def salvar_selecao(dados: pd.DataFrame, info: dict[str, str], pasta_saida: Path) -> tuple[Path, Path]:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    planilha = pasta_saida / "cliente_selecionado.xlsx"
    metadados = pasta_saida / "cliente_selecionado.json"
    dados.to_excel(planilha, index=False)
    metadados.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return planilha, metadados
