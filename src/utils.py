"""
Funções utilitárias de uso geral: normalização de texto, CNPJ, números de
pedido e configuração de logging.

Este módulo não deve importar nada de Selenium/PyAutoGUI — deve
permanecer testável sem qualquer dependência de navegador.
"""

from __future__ import annotations

import logging
import re
import sys
import unicodedata
from pathlib import Path


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def configurar_logging(logs_dir: Path, nome_arquivo: str = "automacao.log") -> logging.Logger:
    """Configura logging para arquivo (append) e console.

    Args:
        logs_dir: pasta onde o arquivo de log será salvo.
        nome_arquivo: nome do arquivo de log.

    Returns:
        Logger configurado, pronto para uso.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    caminho_log = logs_dir / nome_arquivo

    logger = logging.getLogger("automacao_transportadora")
    logger.setLevel(logging.INFO)

    # Evita adicionar handlers duplicados se a função for chamada mais de uma vez
    if not logger.handlers:
        formato = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )

        handler_arquivo = logging.FileHandler(caminho_log, encoding="utf-8")
        handler_arquivo.setFormatter(formato)
        logger.addHandler(handler_arquivo)

        # Em um executável do PyInstaller gerado sem console (janela sem
        # terminal), sys.stderr/stdout vêm como None - adicionar o
        # StreamHandler nesse caso derruba o programa no primeiro log.
        if sys.stderr is not None:
            handler_console = logging.StreamHandler()
            handler_console.setFormatter(formato)
            logger.addHandler(handler_console)

    return logger


# ---------------------------------------------------------------------------
# Normalização de CNPJ
# ---------------------------------------------------------------------------


def normalizar_cnpj(valor) -> str:
    """Remove qualquer caractere não numérico e o sufixo '.0' de floats.

    Usado para COMPARAÇÃO. Para exibição, usar `formatar_cnpj`.

    Args:
        valor: CNPJ em qualquer formato (str, int, float, None).

    Returns:
        String apenas com os dígitos do CNPJ (idealmente 14 dígitos).
        String vazia se o valor for nulo/vazio.
    """
    if valor is None:
        return ""

    texto = str(valor).strip()
    if texto == "" or texto.lower() == "nan":
        return ""

    # Remove sufixo '.0' que aparece quando o Excel/pandas lê o CNPJ como número
    texto = re.sub(r"\.0$", "", texto)

    apenas_digitos = re.sub(r"\D", "", texto)

    # Preserva zeros à esquerda: se após limpar sobrou menos que 14 dígitos
    # mas o valor original claramente representa um CNPJ, completa com zeros.
    if 0 < len(apenas_digitos) <= 14:
        apenas_digitos = apenas_digitos.zfill(14)

    return apenas_digitos


def formatar_cnpj(cnpj_normalizado: str) -> str:
    """Formata um CNPJ normalizado (14 dígitos) para exibição: 00.000.000/0000-00.

    Se o valor não tiver exatamente 14 dígitos, retorna-o sem alteração
    (evita mascarar dados inválidos silenciosamente).
    """
    if len(cnpj_normalizado) != 14:
        return cnpj_normalizado

    return (
        f"{cnpj_normalizado[0:2]}.{cnpj_normalizado[2:5]}.{cnpj_normalizado[5:8]}/"
        f"{cnpj_normalizado[8:12]}-{cnpj_normalizado[12:14]}"
    )


# ---------------------------------------------------------------------------
# Normalização de identificadores (pedido, carga, nota fiscal etc.)
# ---------------------------------------------------------------------------


def normalizar_identificador(valor) -> str:
    """Normaliza um identificador (pedido/carga/nota) para uso em cruzamentos.

    - Converte para texto.
    - Remove sufixo '.0' de floats vindos do Excel.
    - Remove espaços nas extremidades e espaços internos.
    - Preserva zeros à esquerda (não faz cast para int).

    Args:
        valor: identificador em qualquer formato.

    Returns:
        String normalizada. String vazia se o valor for nulo/vazio.
    """
    if valor is None:
        return ""

    texto = str(valor).strip()
    if texto == "" or texto.lower() == "nan":
        return ""

    texto = re.sub(r"\.0$", "", texto)
    texto = texto.replace(" ", "")

    return texto


# ---------------------------------------------------------------------------
# Normalização de texto (nomes de clientes, cidades etc.)
# ---------------------------------------------------------------------------


def normalizar_texto(valor: str) -> str:
    """Normaliza texto para comparação: minúsculas, sem acento, sem espaços extras.

    Não altera o valor original para exibição — usar apenas para comparar/buscar.
    """
    if valor is None:
        return ""

    texto = str(valor).strip()
    texto = re.sub(r"\s+", " ", texto)

    # Remove acentuação
    texto_sem_acento = unicodedata.normalize("NFKD", texto)
    texto_sem_acento = "".join(
        c for c in texto_sem_acento if not unicodedata.combining(c)
    )

    return texto_sem_acento.lower()


# ---------------------------------------------------------------------------
# Espera de download (usada na Etapa 2 — geração/download do relatório)
# ---------------------------------------------------------------------------


def listar_nomes_arquivos(pasta: "Path") -> set[str]:
    """Lista os nomes dos arquivos presentes em uma pasta agora — usar
    ANTES de disparar um download, para depois comparar com o que apareceu.
    """
    return {p.name for p in pasta.iterdir() if p.is_file()}


def aguardar_download_concluido(
    pasta: "Path",
    arquivos_antes: set[str],
    timeout_segundos: int = 60,
    intervalo_segundos: float = 1.0,
) -> "Path":
    """Aguarda um novo arquivo COMPLETO aparecer em `pasta`.

    Evita `time.sleep` fixo: verifica periodicamente até aparecer um
    arquivo que não existia antes (`arquivos_antes`) e que não está mais
    com extensão de download parcial (.crdownload/.tmp/.part).

    Args:
        pasta: pasta onde o navegador está configurado para baixar.
        arquivos_antes: nomes de arquivo presentes na pasta antes do
            download começar (ver `listar_nomes_arquivos`).
        timeout_segundos: tempo máximo total de espera.
        intervalo_segundos: intervalo entre verificações.

    Returns:
        Caminho do arquivo novo e completo.

    Raises:
        TimeoutError: se nenhum arquivo novo e completo aparecer a tempo.
    """
    import time as _time

    decorrido = 0.0
    while decorrido < timeout_segundos:
        atuais = listar_nomes_arquivos(pasta)
        novos = atuais - arquivos_antes
        completos = [
            n for n in novos if not n.endswith((".crdownload", ".tmp", ".part"))
        ]

        if completos:
            mais_recente = max(
                (pasta / n for n in completos), key=lambda p: p.stat().st_mtime
            )
            return mais_recente

        _time.sleep(intervalo_segundos)
        decorrido += intervalo_segundos

    raise TimeoutError(
        f"Nenhum arquivo novo e completo apareceu em '{pasta}' após "
        f"{timeout_segundos}s."
    )
