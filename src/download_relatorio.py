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


def _titulo_janela_ativa_windows() -> str:
    """Retorna o título da janela ativa no Windows; vazio em outros sistemas."""
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        tamanho = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
        buffer = ctypes.create_unicode_buffer(tamanho)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, tamanho)
        return buffer.value
    except Exception:
        return ""


def _preencher_salvar_com_windows(nome_arquivo: str, timeout: int = 12) -> bool:
    """Preenche a janela nativa Salvar como quando o SSW a exibe.

    Retorna True quando a janela foi detectada e confirmada. Em downloads
    automáticos, retorna False sem interferir na página do navegador.
    """
    import time as _time

    limite = _time.monotonic() + timeout
    while _time.monotonic() < limite:
        titulo = _titulo_janela_ativa_windows().lower()
        if "salvar como" in titulo or "save as" in titulo:
            import pyautogui as pa

            pa.hotkey("ctrl", "a")
            pa.write(nome_arquivo, interval=0.03)
            pa.press("enter")
            logger.info("Janela 'Salvar como' preenchida com: %s", nome_arquivo)
            return True
        _time.sleep(0.25)
    return False


def _formatar_data_ddmmyy(d: date) -> str:
    return d.strftime("%d%m%y")


def _definir_valor_campo(driver, campo_id: str, valor: str) -> None:
    """Define um campo do SSW e dispara os eventos usados pela tela."""
    driver.execute_script(
        """
        const el = document.getElementById(arguments[0]);
        if (!el) { throw new Error(`Campo não encontrado: ${arguments[0]}`); }
        if (el.readOnly) { el.readOnly = false; }
        el.focus();
        el.value = arguments[1];
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        el.dispatchEvent(new Event('blur', {bubbles: true}));
        """,
        campo_id,
        valor,
    )


def preencher_filtros_relatorio(driver, data_inicial: date, data_final: date) -> None:
    """Preenche todos os filtros da opção 455 conforme o relatório usado.

    Valores equivalentes ao preenchimento manual informado pelo usuário:
    unidade expedidora, sem regional/UF/cliente, período de emissão,
    documentos e fretes todos, somente pendentes, saída Excel e dados
    complementares A/B/H.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    timeout_espera = max(SISTEMA.timeout_padrao_segundos, 40)
    try:
        WebDriverWait(driver, timeout_espera).until(
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
        sistema.salvar_diagnostico_falha(driver, "preencher_filtros_relatorio")
        raise

    valores = {
        "3": "E",          # unidade: expedidora
        "reg_sigla": "",  # regional
        "reg_tipo": "",
        "4": "",          # UF
        "5": "",
        "7": "",          # cliente
        "8": "",
        "9": _formatar_data_ddmmyy(data_inicial),
        "10": _formatar_data_ddmmyy(data_final),
        "11": "",         # autorização
        "12": "",
        "13": "",         # previsão
        "14": "",
        "15": "",         # entrega
        "16": "",
        "18": "T",        # tipo do documento
        "19": "T",        # tipo de frete
        "20": "S",        # imposto repassado
        "21": "T",        # liquidação
        "22": "P",        # entrega pendente
        "23": "A",        # pagamento à vista: ambos
        "25": "T",        # cálculo/tabela
        "26": "A",
        "27": "A",
        "28": "T",
        "ibscbs": "A",
        "29": "A",
        "30": "A",
        "32": "",         # vendedor
        "34": "",         # placa
        "35": "E",        # Excel
        "37": "A",        # complementares
        "38": "B",
        "39": "H",
    }

    for campo_id, valor in valores.items():
        _definir_valor_campo(driver, campo_id, valor)

    logger.info(
        "Filtros preenchidos: emissão %s a %s | entrega=P | arquivo=E | complementares=A/B/H.",
        data_inicial.strftime("%d/%m/%Y"),
        data_final.strftime("%d/%m/%Y"),
    )


# Mantém o nome antigo para compatibilidade com outros módulos.
def preencher_periodo_emissao(driver, data_inicial: date, data_final: date) -> None:
    preencher_filtros_relatorio(driver, data_inicial, data_final)

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

    # O SSW mostra um painel HTML (não é alert do navegador) com o link
    # "Abrir a opção 156 agora". Clicamos nesse link para ir direto à fila.
    from selenium.common.exceptions import NoAlertPresentException, TimeoutException
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    # Fallback para algum alert real que possa surgir em versões diferentes.
    try:
        WebDriverWait(driver, 2).until(EC.alert_is_present())
        alerta = driver.switch_to.alert
        logger.warning("Alerta do navegador apareceu: '%s' — aceitando.", alerta.text)
        alerta.accept()
    except (TimeoutException, NoAlertPresentException):
        pass

    try:
        link_opcao_156 = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//a[contains(normalize-space(.), 'Abrir a opção 156 agora') "
                    "or contains(normalize-space(.), 'Abrir a opcao 156 agora')]",
                )
            )
        )
        logger.info(
            "Relatório enviado. Aguardando 10s antes de abrir a opção 156..."
        )
        time.sleep(10)
        driver.execute_script("arguments[0].click();", link_opcao_156)
        logger.info("Link 'Abrir a opção 156 agora' acionado após 10s.")

        # O SSW abre a fila em uma janela própria (igual às opções 455/023) -
        # sem trocar o foco do Selenium para ela, `driver.current_url` continua
        # apontando para a janela antiga e a espera nunca é satisfeita.
        sistema.focar_janela_por_url(driver, "/bin/ssw1440", timeout=40)
        logger.info("Tela da fila aberta pelo aviso de processamento: %s", driver.current_url)
    except (TimeoutException, TimeoutError):
        # Se o painel não aparecer, aguardar_e_baixar_relatorio usa o link
        # tradicional "Ver fila" como fallback.
        logger.warning(
            "O link 'Abrir a opção 156 agora' não foi encontrado ou a fila não abriu; "
            "será usado o fluxo alternativo pelo link 'Ver fila'."
        )


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


def _localizar_relatorio_mais_recente(driver, usuario: str):
    """Localiza a linha MAIS RECENTE da opção 455 para o usuário.

    Importante: não pula para uma linha antiga caso a mais recente ainda não
    tenha o link ``Baixar``. A fila é ordenada do registro mais novo para o
    mais antigo; portanto, a primeira linha correspondente é a única que deve
    ser acompanhada.

    Returns:
        Tupla ``(sequencia, situacao, link_baixar)``. O link pode ser ``None``
        enquanto o relatório mais recente ainda está processando.
    """
    from selenium.webdriver.common.by import By

    usuario_normalizado = usuario.strip().lower()
    linhas = driver.find_elements(By.XPATH, "//tr[td]")

    for linha in linhas:
        celulas = linha.find_elements(By.TAG_NAME, "td")
        if len(celulas) < 8:
            continue

        valores = [" ".join(c.text.split()) for c in celulas]
        opcao = valores[1].lower() if len(valores) > 1 else ""
        usuario_linha = valores[3].strip().lower() if len(valores) > 3 else ""

        if "455 - fretes expedidos/recebidos" not in opcao:
            continue
        if usuario_normalizado and usuario_linha != usuario_normalizado:
            continue

        sequencia = valores[0].strip()
        situacao = valores[6].strip() if len(valores) > 6 else ""
        links = linha.find_elements(
            By.XPATH,
            ".//a[contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÀÂÃÉÊÍÓÔÕÚÇ', "
            "'abcdefghijklmnopqrstuvwxyzáàâãéêíóôõúç'), 'baixar')]",
        )
        link_baixar = links[0] if links else None
        return sequencia, situacao, link_baixar

    return None, None, None

def _atualizar_fila(driver) -> None:
    """Aciona o link Atualizar da fila sem depender de clique físico."""
    from selenium.webdriver.common.by import By

    links = driver.find_elements(
        By.XPATH,
        "//a[normalize-space()='Atualizar' or contains(normalize-space(.), 'Atualizar')]",
    )
    if links:
        driver.execute_script("arguments[0].click();", links[0])
    else:
        driver.refresh()


def aguardar_e_baixar_relatorio(
    driver,
    usuario: str,
    pasta_downloads: Path | None = None,
    espera_inicial_segundos: int = 10,
    timeout_total_segundos: int = 120,
    intervalo_verificacao_segundos: int = 10,
    data_referencia: date | None = None,
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
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    # Se o aviso "Abrir a opção 156 agora" já foi acionado, estaremos na fila.
    ja_esta_na_fila = (
        '/bin/ssw1440' in driver.current_url.lower()
        or bool(driver.find_elements(By.ID, ID_TABELA_FILA))
    )

    if ja_esta_na_fila:
        logger.info(
            "A fila já está aberta após a espera de 10s feita no aviso; consultando agora."
        )
        espera_ja_realizada = True
    else:
        espera_ja_realizada = False
        # Fallback: espera o painel desaparecer e usa o link tradicional.
        logger.info("Aguardando %ds antes de abrir a fila pelo link tradicional...", espera_inicial_segundos)
        time.sleep(espera_inicial_segundos)

        try:
            WebDriverWait(driver, 60).until(
                lambda d: d.execute_script(
                    """
                    const p = document.getElementById('errorpanel');
                    if (!p) return true;
                    const s = getComputedStyle(p);
                    return s.visibility === 'hidden' || s.display === 'none' ||
                           Number(s.opacity) === 0 || p.offsetParent === null;
                    """
                )
            )
        except Exception:
            logger.warning("O painel de processamento continuou visível; tentando abrir a fila via JavaScript.")

        driver.execute_script(
            "if (typeof ajaxEnvia === 'function') { ajaxEnvia('', 1, 'ssw1440'); } "
            "else { document.getElementById('42').click(); }"
        )

        # Mesmo problema do painel: a fila abre em janela própria e o
        # Selenium precisa trocar de foco explicitamente para ela, senão
        # `driver.current_url`/`find_elements` continuam olhando para a
        # janela antiga (ssw0230) e a espera nunca é satisfeita.
        sistema.focar_janela_por_url(driver, "/bin/ssw1440", timeout=40)
        logger.info("Tela da fila aberta: %s", driver.current_url)

    tempo_decorrido = espera_inicial_segundos if not ja_esta_na_fila else 0
    sequencia_encontrada = None
    situacao_encontrada = None
    link_baixar = None

    while tempo_decorrido <= timeout_total_segundos:
        sequencia_encontrada, situacao_encontrada, link_baixar = (
            _localizar_relatorio_mais_recente(driver, usuario)
        )

        if sequencia_encontrada and link_baixar is not None:
            logger.info(
                "Relatório MAIS RECENTE concluído (sequência %s, situação %s).",
                sequencia_encontrada,
                situacao_encontrada,
            )
            break

        if sequencia_encontrada:
            logger.info(
                "O relatório mais recente é a sequência %s, mas ainda está '%s'. "
                "Não será baixado um relatório antigo. Atualizando em %ds...",
                sequencia_encontrada,
                situacao_encontrada or "sem situação",
                intervalo_verificacao_segundos,
            )
        else:
            logger.info(
                "Ainda não apareceu uma linha da opção 455 para o usuário '%s'. "
                "Atualizando em %ds...",
                usuario,
                intervalo_verificacao_segundos,
            )

        _atualizar_fila(driver)
        time.sleep(intervalo_verificacao_segundos)
        tempo_decorrido += intervalo_verificacao_segundos

    if link_baixar is None:
        sistema.salvar_diagnostico_falha(driver, "aguardar_e_baixar_relatorio")
        raise TimeoutError(
            f"Relatório do usuário '{usuario}' não apareceu concluído na "
            f"fila após {timeout_total_segundos}s."
        )

    arquivos_antes = listar_nomes_arquivos(pasta_downloads)

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link_baixar)
    time.sleep(0.5)
    try:
        driver.execute_script("window.focus();")
    except Exception:
        pass

    # 1) Tenta primeiro um clique "de verdade" via Selenium (protocolo do
    # navegador — Chrome trata isso como ativação real do usuário). Isso é
    # DIFERENTE de chamar a função JavaScript do link via execute_script:
    # aquilo não conta como gesto do usuário e pode não iniciar o download.
    # Só recorre ao clique físico do PyAutoGUI (coordenadas de tela) se o
    # clique do Selenium não fizer o arquivo aparecer.
    metodo_usado = None
    try:
        link_baixar.click()
        metodo_usado = "clique nativo do Selenium"
    except Exception as e:
        logger.warning("Clique nativo no link Baixar falhou (%s) — tentando ActionChains.", e)
        try:
            from selenium.webdriver.common.action_chains import ActionChains

            ActionChains(driver).move_to_element(link_baixar).pause(0.2).click().perform()
            metodo_usado = "ActionChains"
        except Exception as e2:
            logger.warning("ActionChains também falhou (%s).", e2)

    arquivo_baixado = None
    if metodo_usado:
        try:
            arquivo_baixado = aguardar_download_concluido(
                pasta_downloads, arquivos_antes, timeout_segundos=20,
            )
            logger.info(
                "Download da sequência %s iniciado com sucesso via %s.",
                sequencia_encontrada, metodo_usado,
            )
        except TimeoutError:
            logger.warning(
                "O %s não pareceu iniciar o download em 20s — tentando o "
                "clique físico (PyAutoGUI) como último recurso.",
                metodo_usado,
            )

    if arquivo_baixado is None:
        arquivo_baixado = _clicar_fisico_e_aguardar(
            driver, link_baixar, pasta_downloads, arquivos_antes, sequencia_encontrada
        )

    logger.info("Download concluído: %s", arquivo_baixado)
    return arquivo_baixado


def _clicar_fisico_e_aguardar(
    driver, link_baixar, pasta_downloads: Path, arquivos_antes: set[str], sequencia: str
) -> Path:
    """Último recurso: clique físico (PyAutoGUI) no centro do link Baixar.

    Usado apenas quando nem o clique nativo do Selenium nem o ActionChains
    fazem o download começar. As coordenadas de tela dependem da posição
    real da janela do Chrome — por isso ficam logadas em detalhe: se este
    fallback também falhar, esse log (com as coordenadas calculadas e a
    resolução que o PyAutoGUI está enxergando) é o que preciso para
    corrigir o cálculo sem adivinhar.
    """
    import pyautogui as pa

    rect = driver.execute_script(
        """
        const r = arguments[0].getBoundingClientRect();
        return {
            left: r.left, top: r.top, width: r.width, height: r.height,
            screenX: window.screenX, screenY: window.screenY,
            outerHeight: window.outerHeight, innerHeight: window.innerHeight,
            outerWidth: window.outerWidth, innerWidth: window.innerWidth
        };
        """,
        link_baixar,
    )

    # Diferenças entre a área externa e a área útil do Chrome. A maior parte
    # vertical corresponde à barra de título/endereço; a horizontal é dividida
    # entre as duas bordas da janela.
    borda_x = max(0, (rect["outerWidth"] - rect["innerWidth"]) / 2)
    topo_chrome = max(0, rect["outerHeight"] - rect["innerHeight"] - borda_x)
    clique_x = round(rect["screenX"] + borda_x + rect["left"] + rect["width"] / 2)
    clique_y = round(rect["screenY"] + topo_chrome + rect["top"] + rect["height"] / 2)

    logger.info(
        "Diagnóstico do clique físico — retângulo do link: %s | "
        "coordenada calculada: (%s, %s) | resolução vista pelo PyAutoGUI: %s.",
        rect, clique_x, clique_y, pa.size(),
    )

    time.sleep(0.5)
    pa.click(clique_x, clique_y)
    logger.info(
        "Clique físico realizado no link Baixar da sequência %s em (%s, %s).",
        sequencia, clique_x, clique_y,
    )

    # O Chrome salva com o nome original e extensão .sswweb. Depois que o
    # arquivo estiver fisicamente na pasta, ele será renomeado localmente.
    return aguardar_download_concluido(pasta_downloads, arquivos_antes, timeout_segundos=120)


def renomear_arquivo_padronizado(caminho_arquivo: Path, data_referencia: date) -> Path:
    """Renomeia o arquivo baixado para um padrão previsível.

    Ex.: 'relatorio030826.csv' -> 'relatorio_entregas_2026-08-03.csv'
    """
    novo_nome = f"relatorio{data_referencia.strftime('%d%m%y')}.csv"
    novo_caminho = caminho_arquivo.with_name(novo_nome)
    if caminho_arquivo.resolve() == novo_caminho.resolve():
        return caminho_arquivo
    if novo_caminho.exists():
        novo_caminho.unlink()
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
    arquivo = aguardar_e_baixar_relatorio(
        driver, usuario=usuario, data_referencia=data_final
    )
    return renomear_arquivo_padronizado(arquivo, data_referencia=data_final)
