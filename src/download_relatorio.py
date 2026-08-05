"""
Etapa 2 (parte 2) — Geração e download do relatório de entregas.

Baseado no HTML real de três telas:

  1. `ssw0230` (opção 455, "Fretes Expedidos/Recebidos - CTRCs"): onde se
     preenche o período de emissão e se pede a geração do relatório.
       - Período de emissão: campos id="9" (início) e id="10" (fim),
         formato DDMMYY (6 dígitos).
       - Botão para gerar: id="40" (ícone "▶", mesmo padrão do login —
         onclick chama `ajaxEnvia('E1', 0)`).
       - Link "Ver fila": id="42" (`ajaxEnvia('', 1, 'ssw1440')`).

  2. `ssw1440` (fila de processamento): tabela com id `tblsr` (mesmo id
     usado na tabela de motoristas — mas colunas diferentes aqui):
     Sequência, Opção, Data/Hora Solicitação, Usuário, Unidade, Fone,
     Situação, Duração, e um link "Baixar" (`ajaxEnvia('DOW<sequencia>')`)
     quando a Situação é "Concluído".

  3. A pasta de download (`SISTEMA.pasta_downloads`, configurada em
     `sistema.criar_driver` para já ser a pasta 'entrada/' do projeto).

Fluxo: `sistema.navegar_para_opcao(driver, '455')` → preencher período →
clicar em gerar → clicar em "Ver fila" → aguardar ~10s → checar a fila
periodicamente até aparecer "Concluído" para o usuário configurado →
clicar em "Baixar" → aguardar o arquivo terminar de baixar.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from config import SISTEMA
from src import sistema
from src.utils import aguardar_download_concluido, listar_nomes_arquivos

logger = logging.getLogger("automacao_transportadora")

# IDs reais da tela de geração do relatório (form ssw0230, opção 455)
ID_CAMPO_DATA_EMISSAO_INICIO = "9"
ID_CAMPO_DATA_EMISSAO_FIM = "10"
ID_BOTAO_GERAR = "40"
ID_LINK_VER_FILA = "42"

# Id da tabela de fila (mesmo id usado na tabela de motoristas — telas
# diferentes, mas o sistema reaproveita o mesmo componente)
ID_TABELA_FILA = "tblsr"

SITUACAO_CONCLUIDO = "Concluído"


def _formatar_data_ddmmyy(d: date) -> str:
    return d.strftime("%d%m%y")


def preencher_periodo_emissao(driver, data_inicial: date, data_final: date) -> None:
    """Preenche o período de emissão na tela de geração do relatório.

    Args:
        driver: WebDriver já na tela ssw0230 (opção 455).
        data_inicial: data inicial do período de emissão.
        data_final: data final do período de emissão.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    timeout_espera = max(SISTEMA.timeout_padrao_segundos, 40)
    espera = WebDriverWait(driver, timeout_espera)

    try:
        campo_inicio = espera.until(
            EC.presence_of_element_located((By.ID, ID_CAMPO_DATA_EMISSAO_INICIO))
        )
    except Exception:
        logger.error(
            "Não achei o campo de data (id='%s') após %ds. URL atual: %s | Título: %s",
            ID_CAMPO_DATA_EMISSAO_INICIO,
            timeout_espera,
            driver.current_url,
            driver.title,
        )
        sistema.salvar_diagnostico_falha(driver, "preencher_periodo_emissao")
        raise
    campo_inicio.clear()
    campo_inicio.send_keys(_formatar_data_ddmmyy(data_inicial))

    campo_fim = driver.find_element(By.ID, ID_CAMPO_DATA_EMISSAO_FIM)
    campo_fim.clear()
    campo_fim.send_keys(_formatar_data_ddmmyy(data_final))

    logger.info(
        "Período de emissão preenchido: %s a %s",
        data_inicial.strftime("%d/%m/%Y"),
        data_final.strftime("%d/%m/%Y"),
    )


def solicitar_geracao_relatorio(
    driver,
    data_inicial: date,
    data_final: date,
    unidade: str | None = None,
) -> None:
    """Fluxo até pedir a geração: navega até a opção 455, preenche o
    período de emissão e clica no botão de gerar.

    Note:
        Não mexe nos demais filtros da tela (tipo de documento, frete
        etc.) nem no campo "Dados complementares" — ficam nos valores
        padrão do sistema. Se precisar de colunas extras no relatório
        (ex.: manifesto, ocorrências), isso é configurado manualmente
        uma vez no sistema e não muda por execução.
    """
    sistema.navegar_para_opcao(driver, "455", unidade=unidade or SISTEMA.unidade_padrao)
    preencher_periodo_emissao(driver, data_inicial, data_final)

    from selenium.webdriver.common.by import By

    def _clicar_gerar():
        botao = driver.find_element(By.ID, ID_BOTAO_GERAR)
        botao.click()

    try:
        _clicar_gerar()
    except Exception as e:
        from selenium.common.exceptions import UnexpectedAlertPresentException

        if not isinstance(e, UnexpectedAlertPresentException):
            raise
        sistema.executar_ignorando_alertas(driver, _clicar_gerar, contexto="gerar relatório")

    logger.info("Solicitação de geração enviada — relatório foi para a fila de processamento.")

    # Checagem extra: se o alerta apareceu de forma assíncrona logo após
    # o clique (sem estourar exceção na hora), aceita também.
    from selenium.common.exceptions import NoAlertPresentException, TimeoutException
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    try:
        WebDriverWait(driver, 3).until(EC.alert_is_present())
        alerta = driver.switch_to.alert
        logger.warning("Diálogo de confirmação apareceu: '%s' — aceitando.", alerta.text)
        alerta.accept()
    except (TimeoutException, NoAlertPresentException):
        pass  # nenhum diálogo apareceu — segue normalmente


def _parsear_linha_fila(tr) -> dict | None:
    """Extrai os dados de uma linha da tabela de fila (ver docstring do módulo)."""
    celulas = tr.find_all("td", class_="srtd2")
    if len(celulas) < 8:
        return None  # linha de cabeçalho ou formato inesperado

    valores = [c.get_text(strip=True).replace("\xa0", "") for c in celulas]
    link_baixar = celulas[8].find("a") if len(celulas) > 8 else None

    return {
        "sequencia": valores[0],
        "opcao": valores[1],
        "data_hora": valores[2],
        "usuario": valores[3].strip(),
        "unidade": valores[4],
        "situacao": valores[6],
        "duracao": valores[7],
        "tem_link_baixar": link_baixar is not None,
    }


def _obter_fila(driver) -> list[dict]:
    """Captura e faz o parsing da tabela de fila atual (via JS + BeautifulSoup,
    mesma técnica usada em `captura_motoristas`)."""
    html = driver.execute_script(
        f"var el = document.getElementById('{ID_TABELA_FILA}'); "
        "return el ? el.outerHTML : null;"
    )
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    linhas = []
    for tr in soup.find_all("tr"):
        registro = _parsear_linha_fila(tr)
        if registro:
            linhas.append(registro)
    return linhas


def aguardar_e_baixar_relatorio(
    driver,
    usuario: str,
    pasta_downloads: Path | None = None,
    espera_inicial_segundos: int = 10,
    timeout_total_segundos: int = 120,
    intervalo_verificacao_segundos: int = 10,
) -> Path:
    """Vai até a fila, aguarda o processamento e baixa o relatório mais
    recente do usuário informado assim que estiver "Concluído".

    Args:
        driver: WebDriver logo após `solicitar_geracao_relatorio`.
        usuario: nome do usuário a filtrar na fila (ex.: 'jose').
        pasta_downloads: pasta onde o arquivo deve aparecer. Usa
            `SISTEMA.pasta_downloads` se não informado.
        espera_inicial_segundos: espera antes da primeira checagem.
        timeout_total_segundos: tempo máximo total de espera.
        intervalo_verificacao_segundos: intervalo entre checagens.

    Returns:
        Caminho do arquivo baixado (ainda sem renomear).

    Raises:
        TimeoutError: se o relatório não ficar "Concluído" a tempo, ou se
            o arquivo não terminar de baixar a tempo.
    """
    pasta_downloads = Path(pasta_downloads or SISTEMA.pasta_downloads)

    from selenium.webdriver.common.by import By

    link_ver_fila = driver.find_element(By.ID, ID_LINK_VER_FILA)
    link_ver_fila.click()

    logger.info("Aguardando %ds antes de checar a fila...", espera_inicial_segundos)
    time.sleep(espera_inicial_segundos)

    tempo_decorrido = espera_inicial_segundos
    sequencia_encontrada = None

    while tempo_decorrido <= timeout_total_segundos:
        fila = _obter_fila(driver)
        candidatos = [
            item
            for item in fila
            if item["usuario"].lower() == usuario.lower()
            and item["situacao"] == SITUACAO_CONCLUIDO
            and item["tem_link_baixar"]
        ]

        if candidatos:
            # a fila vem ordenada do mais recente para o mais antigo
            sequencia_encontrada = candidatos[0]["sequencia"]
            logger.info("Relatório concluído encontrado (sequência %s).", sequencia_encontrada)
            break

        logger.info(
            "Ainda sem relatório concluído para '%s'. Aguardando mais %ds...",
            usuario,
            intervalo_verificacao_segundos,
        )
        time.sleep(intervalo_verificacao_segundos)
        tempo_decorrido += intervalo_verificacao_segundos

    if sequencia_encontrada is None:
        raise TimeoutError(
            f"Relatório do usuário '{usuario}' não apareceu concluído na "
            f"fila após {timeout_total_segundos}s."
        )

    arquivos_antes = listar_nomes_arquivos(pasta_downloads)

    link_baixar = driver.find_element(
        By.XPATH, f"//a[contains(@onclick, \"DOW{sequencia_encontrada}\")]"
    )
    link_baixar.click()
    logger.info("Download iniciado (sequência %s). Aguardando conclusão...", sequencia_encontrada)

    arquivo_baixado = aguardar_download_concluido(pasta_downloads, arquivos_antes)
    logger.info("Download concluído: %s", arquivo_baixado)

    return arquivo_baixado


def renomear_arquivo_padronizado(caminho_arquivo: Path, data_referencia: date) -> Path:
    """Renomeia o arquivo baixado para um padrão previsível.

    Ex.: 'relatorio030826.csv' -> 'relatorio_entregas_2026-08-03.csv'
    """
    novo_nome = f"relatorio_entregas_{data_referencia.strftime('%Y-%m-%d')}{caminho_arquivo.suffix}"
    novo_caminho = caminho_arquivo.with_name(novo_nome)
    caminho_arquivo.rename(novo_caminho)
    logger.info("Arquivo renomeado: %s -> %s", caminho_arquivo.name, novo_caminho.name)
    return novo_caminho


def baixar_relatorio(
    driver,
    data_inicial: date,
    data_final: date,
    usuario: str,
    unidade: str | None = None,
) -> Path:
    """Fluxo completo da Etapa 2 (parte 2): gera, aguarda e baixa o
    relatório, já renomeado de forma padronizada.

    Args:
        driver: WebDriver já logado (ver `sistema.fazer_login`).
        data_inicial: início do período de emissão a consultar.
        data_final: fim do período de emissão a consultar.
        usuario: usuário a filtrar na fila (ex.: 'jose').
        unidade: unidade a usar na navegação (padrão: `SISTEMA.unidade_padrao`).

    Returns:
        Caminho do arquivo final, renomeado.
    """
    solicitar_geracao_relatorio(driver, data_inicial, data_final, unidade=unidade)
    arquivo = aguardar_e_baixar_relatorio(driver, usuario=usuario)
    return renomear_arquivo_padronizado(arquivo, data_referencia=data_final)
