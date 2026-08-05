"""
Etapa 4 — Captura da tabela de motoristas (tela "023 - Consulta e
reimpressão de Manifesto" do sistema SSW).

A tabela tem id fixo `tblsr` e, pelo exemplo capturado, não usa
paginação/rolagem — todos os registros do período consultado já vêm no
HTML de uma vez. Por isso a captura é simples: pegar o `outerHTML` do
elemento com id `tblsr` via JavaScript (mais confiável que tentar ler
célula por célula pelo Selenium) e processar esse HTML com
BeautifulSoup — sem depender do navegador para o parsing em si.

Essa separação (captura via navegador x. parsing do HTML) permite testar
o parsing sozinho, com um HTML real salvo em disco, sem precisar abrir
navegador nenhum.
"""

from __future__ import annotations

import logging

import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger("automacao_transportadora")

# Ordem das colunas conforme os atributos i="0".."16" no cabeçalho real da
# tabela (ver testes/exemplo_tabela_motoristas.html). Se o sistema mudar a
# ordem das colunas, ajuste aqui.
COLUNAS_TABELA_MOTORISTAS = [
    "manifesto",
    "gaiola_pallet",
    "cavalo",
    "carreta",
    "motorista",
    "origem",
    "destino",
    "unid",
    "qt_ctrcs",
    "peso_calculo",
    "peso_real",
    "saida",
    "prev_chegada",
    "chegada",
    "ciot",
    "awb",
    "situacao_mdfe",
]

ID_TABELA = "tblsr"


def _texto_celula(td) -> str:
    """Extrai o texto de uma célula <td>, tratando '&nbsp;' como vazio."""
    texto = td.get_text(strip=True)
    # BeautifulSoup já converte '&nbsp;' em '\xa0' — normaliza para vazio.
    texto = texto.replace("\xa0", "").strip()
    return texto


def parsear_tabela_motoristas(html_tabela: str) -> pd.DataFrame:
    """Converte o HTML da tabela (outerHTML do elemento `#tblsr`) em DataFrame.

    Não depende de navegador — pode ser testado com um HTML salvo em disco.

    Args:
        html_tabela: HTML completo da tabela, incluindo a linha de
            cabeçalho (será ignorada) e as linhas de dados.

    Returns:
        DataFrame com uma linha por manifesto, colunas conforme
        `COLUNAS_TABELA_MOTORISTAS`.
    """
    soup = BeautifulSoup(html_tabela, "html.parser")

    tabela = soup.find(id=ID_TABELA) or soup  # aceita já vir só o <table>
    linhas = tabela.find_all("tr")

    registros = []
    linhas_com_numero_diferente = 0

    for linha in linhas:
        celulas = linha.find_all("td", class_="srtd2")
        if not celulas:
            # é a linha de cabeçalho (usa class="srtit2") — ignora
            continue

        valores = [_texto_celula(td) for td in celulas]

        if len(valores) != len(COLUNAS_TABELA_MOTORISTAS):
            linhas_com_numero_diferente += 1
            logger.warning(
                "Linha com %d células (esperado %d) — registrada mesmo assim, "
                "preenchendo o que faltar com vazio. Conteúdo: %s",
                len(valores),
                len(COLUNAS_TABELA_MOTORISTAS),
                valores,
            )
            valores = (valores + [""] * len(COLUNAS_TABELA_MOTORISTAS))[
                : len(COLUNAS_TABELA_MOTORISTAS)
            ]

        registros.append(dict(zip(COLUNAS_TABELA_MOTORISTAS, valores)))

    df = pd.DataFrame(registros, columns=COLUNAS_TABELA_MOTORISTAS)

    logger.info(
        "Tabela de motoristas capturada: %d registros%s",
        len(df),
        f" ({linhas_com_numero_diferente} com formato inesperado)"
        if linhas_com_numero_diferente
        else "",
    )

    return df


def capturar_tabela_motoristas(driver) -> pd.DataFrame:
    """Captura a tabela de motoristas a partir de uma sessão Selenium ativa.

    Pressupõe que a página com a tabela já está aberta e carregada (ex.:
    após realizar a busca na tela 023). Pega o HTML via JavaScript
    (mais robusto que iterar elementos pelo Selenium célula a célula) e
    delega o parsing para `parsear_tabela_motoristas`.

    Args:
        driver: instância do WebDriver do Selenium, com a página já na
            tela de resultado da consulta de manifestos.

    Returns:
        DataFrame com os motoristas capturados.

    Raises:
        Exception: se o elemento #tblsr não existir na página (ex.: busca
            ainda não foi feita, ou o sistema mudou o id da tabela).
    """
    html_tabela = driver.execute_script(
        f"var el = document.getElementById('{ID_TABELA}'); "
        "return el ? el.outerHTML : null;"
    )

    if not html_tabela:
        raise RuntimeError(
            f"Elemento com id '{ID_TABELA}' não encontrado na página. "
            "Verifique se a busca de manifestos já foi realizada."
        )

    return parsear_tabela_motoristas(html_tabela)


# ---------------------------------------------------------------------------
# Busca por período (tela ssw0125, opção 023) — baseado no HTML real do
# formulário. Campos usados:
#   - t_sigla_origem: Unidade de origem (já vem preenchida com 'GRU')
#   - t_data_saida_ini / t_data_saida_fin: Período de saída, formato DDMMYY
#   - id="12": ícone "?" que dispara a busca (onclick chama ajaxEnvia('PER', 1))
# ---------------------------------------------------------------------------

ID_CAMPO_DATA_SAIDA_INICIO = "t_data_saida_ini"
ID_CAMPO_DATA_SAIDA_FIM = "t_data_saida_fin"
ID_BOTAO_PESQUISAR = "12"


def buscar_motoristas_por_periodo(
    driver,
    data_inicial,
    data_final,
    unidade: str | None = None,
    timeout: int | None = None,
) -> pd.DataFrame:
    """Fluxo completo: navega até a opção 023, preenche o período de
    saída, pesquisa e captura a tabela de motoristas resultante.

    Args:
        driver: WebDriver já logado.
        data_inicial: início do período de saída a consultar.
        data_final: fim do período de saída a consultar.
        unidade: unidade a usar na navegação (padrão: `SISTEMA.unidade_padrao`).
        timeout: segundos de espera explícita.

    Returns:
        DataFrame com os motoristas capturados (ver `parsear_tabela_motoristas`).
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    from config import SISTEMA
    from src import sistema

    timeout = timeout or SISTEMA.timeout_padrao_segundos

    sistema.navegar_para_opcao(driver, "023", unidade=unidade or SISTEMA.unidade_padrao)

    timeout_espera = max(timeout, 40)
    try:
        campo_inicio = WebDriverWait(driver, timeout_espera).until(
            EC.presence_of_element_located((By.ID, ID_CAMPO_DATA_SAIDA_INICIO))
        )
    except Exception:
        logger.error(
            "Não achei o campo de data (id='%s') após %ds. URL atual: %s | Título: %s",
            ID_CAMPO_DATA_SAIDA_INICIO,
            timeout_espera,
            driver.current_url,
            driver.title,
        )
        sistema.salvar_diagnostico_falha(driver, "buscar_motoristas_por_periodo")
        raise
    campo_inicio.clear()
    campo_inicio.send_keys(data_inicial.strftime("%d%m%y"))

    campo_fim = driver.find_element(By.ID, ID_CAMPO_DATA_SAIDA_FIM)
    campo_fim.clear()
    campo_fim.send_keys(data_final.strftime("%d%m%y"))

    botao_pesquisar = driver.find_element(By.ID, ID_BOTAO_PESQUISAR)
    botao_pesquisar.click()

    logger.info(
        "Busca de motoristas solicitada: %s a %s",
        data_inicial.strftime("%d/%m/%Y"),
        data_final.strftime("%d/%m/%Y"),
    )

    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.ID, ID_TABELA))
    )

    return capturar_tabela_motoristas(driver)
