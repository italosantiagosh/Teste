"""
Testes do módulo `tratamento_planilha`, usando apenas dados fictícios
gerados localmente. Não acessa o sistema real nem a internet.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import pytest

from src import tratamento_planilha as tp
from src.utils import normalizar_cnpj, formatar_cnpj, normalizar_identificador
from testes.gerar_planilha_ficticia import gerar as gerar_planilha_ficticia


@pytest.fixture(scope="module")
def caminho_planilha_ficticia() -> Path:
    return gerar_planilha_ficticia()


@pytest.fixture(scope="module")
def df_tratado(caminho_planilha_ficticia) -> pd.DataFrame:
    return tp.tratar_planilha(caminho_planilha_ficticia, salvar_intermediaria=True)


# ---------------------------------------------------------------------------
# Testes de normalização (unitários, isolados)
# ---------------------------------------------------------------------------


def test_normalizar_cnpj_com_pontuacao():
    assert normalizar_cnpj("11.222.333/0001-81") == "11222333000181"


def test_normalizar_cnpj_vindo_como_float_com_ponto_zero():
    assert normalizar_cnpj("12345678000195.0") == "12345678000195"


def test_normalizar_cnpj_preserva_zeros_a_esquerda():
    assert normalizar_cnpj("7526557000100") == "07526557000100"


def test_normalizar_cnpj_vazio_ou_nulo():
    assert normalizar_cnpj(None) == ""
    assert normalizar_cnpj("") == ""
    assert normalizar_cnpj("nan") == ""


def test_formatar_cnpj():
    assert formatar_cnpj("11222333000181") == "11.222.333/0001-81"


def test_normalizar_identificador_remove_ponto_zero():
    assert normalizar_identificador("1002.0") == "1002"


def test_normalizar_identificador_preserva_zeros_a_esquerda():
    assert normalizar_identificador("00123") == "00123"


def test_normalizar_identificador_remove_espacos():
    assert normalizar_identificador(" 1001 ") == "1001"


# ---------------------------------------------------------------------------
# Teste de integração do pipeline completo (com dados fictícios que usam os
# MESMOS nomes de coluna reais configurados em config/colunas.json)
# ---------------------------------------------------------------------------


def test_tratar_planilha_remove_linha_vazia(df_tratado):
    # 6 linhas geradas, 1 completamente vazia -> 5 linhas finais
    assert len(df_tratado) == 5


def test_tratar_planilha_remove_colunas_excluidas(df_tratado):
    for coluna_excluida in ["Numero da Nota Fiscal", "Peso Real em Kg", "Vendedor"]:
        assert coluna_excluida not in df_tratado.columns


def test_tratar_planilha_renomeia_colunas(df_tratado):
    for coluna_esperada in [
        "pedido", "cliente", "cidade", "data_emissao", "manifesto",
        "placa_cavalo", "status",
    ]:
        assert coluna_esperada in df_tratado.columns


def test_tratar_planilha_mantem_coluna_extra_nao_mapeada(df_tratado):
    # Coluna sem correspondência em 'ordem_final'/'mapa_renomeacao' não pode
    # ser descartada silenciosamente.
    assert "Observacao Extra" in df_tratado.columns


def test_tratar_planilha_sem_coluna_cnpj(df_tratado):
    # O relatório real (opção 455) não tem CNPJ - o pipeline deve seguir
    # sem quebrar, sem inventar a coluna.
    assert "cnpj" not in df_tratado.columns
    assert "cnpj_formatado" not in df_tratado.columns


def test_tratar_planilha_remove_ponto_zero_do_pedido(df_tratado):
    # A linha com CTRC gravado como número no Excel (1002) deve virar '1002'
    # e não '1002.0'.
    valores_pedido_1002 = df_tratado.loc[df_tratado["cliente"].str.contains("José"), "pedido"]
    assert set(valores_pedido_1002) == {"1002"}


def test_tratar_planilha_remove_ponto_zero_do_manifesto(df_tratado):
    # Um dos dois registros do pedido 1002 tem manifesto gravado como
    # número no Excel (45143) - deve virar '45143', não '45143.0'.
    manifestos = set(df_tratado.loc[df_tratado["pedido"] == "1002", "manifesto"])
    assert manifestos == {"", "45143"}


def test_tratar_planilha_preserva_zero_a_esquerda_do_pedido(df_tratado):
    linha = df_tratado.loc[df_tratado["cliente"].str.contains("Zero Padded")]
    assert linha["pedido"].iloc[0] == "00123"


def test_tratar_planilha_converte_data(df_tratado):
    assert pd.api.types.is_datetime64_any_dtype(df_tratado["data_emissao"])


def test_tratar_planilha_data_invalida_vira_nat(df_tratado):
    data_pedido_1003 = df_tratado.loc[df_tratado["pedido"] == "1003", "data_emissao"].iloc[0]
    assert pd.isna(data_pedido_1003)


def test_tratar_planilha_remove_espacos_extras_do_cliente(df_tratado):
    nome_cliente_1001 = df_tratado.loc[df_tratado["pedido"] == "1001", "cliente"].iloc[0]
    assert nome_cliente_1001 == nome_cliente_1001.strip()


def test_tratar_planilha_cliente_com_acento_preservado(df_tratado):
    nomes = set(df_tratado.loc[df_tratado["pedido"] == "1002", "cliente"])
    assert nomes == {"Comércio São José Ltda"}


def test_tratar_planilha_marca_duplicados_sem_remover(df_tratado):
    # Os dois registros do pedido 1002 só são iguais DEPOIS da normalização
    # ('1002.0' vs '1002') - a marcação de duplicado tem que enxergar isso.
    assert df_tratado["duplicado"].sum() == 2
    assert (df_tratado.loc[df_tratado["pedido"] == "1002", "duplicado"] == True).all()  # noqa: E712


def test_tratar_planilha_salva_arquivos_intermediario_e_final(caminho_planilha_ficticia, df_tratado):
    saida_dir = BASE_DIR / "saida"
    assert (saida_dir / f"{caminho_planilha_ficticia.stem}_bruto.xlsx").exists()
    assert (saida_dir / f"{caminho_planilha_ficticia.stem}_tratado.xlsx").exists()
