"""
Etapa 2 (parte 1) — Login no sistema SSW via Selenium.

Baseado no HTML real da tela de login (form id="frm", ação /bin/ssw0422):
  - input id="1" (name f1) = Domínio (ex.: 'CDI') — geralmente já vem
    com valor padrão; só é preenchido se `CREDENCIAIS.dominio` estiver
    definido.
  - input id="2" (name f2) = CPF — em uma sessão nova do navegador (sem
    o cookie de "Lembrar CPF") esse campo vem VAZIO e precisa ser
    preenchido, senão o login não avança.
  - input id="3" (name f3) = Usuário.
  - input id="4" (name f4, type password) = Senha.
  - Não existe um botão "Entrar" tradicional: o formulário é enviado ao
    pressionar Enter no campo de senha (comportamento típico de telas
    SSW controladas por JavaScript / ajaxEnvia).

Nenhuma credencial fica no código — todas vêm de variáveis de ambiente
(ver `config.CREDENCIAIS`), com fallback interativo via `getpass` para a
senha, caso ela não esteja definida no `.env`.
"""

from __future__ import annotations

import getpass
import logging

from config import CREDENCIAIS, SISTEMA

logger = logging.getLogger("automacao_transportadora")

# IDs reais dos campos, extraídos do HTML da tela de login (ssw0422)
ID_CAMPO_DOMINIO = "1"
ID_CAMPO_CPF = "2"
ID_CAMPO_USUARIO = "3"
ID_CAMPO_SENHA = "4"
ID_BOTAO_ENTRAR = "5"  # ícone de seta (▶); onclick chama ajaxEnvia('L', 0)


def criar_driver(pasta_download: "Path | None" = None):
    """Cria e configura o WebDriver do Chrome, já apontando os downloads
    para a pasta desejada (por padrão, `SISTEMA.pasta_downloads`, que é a
    pasta 'entrada/' do próprio projeto).

    Desliga o prompt de "Salvar como" e a checagem de Safe Browsing para
    download (que às vezes bloqueia .xlsx/.csv perguntando confirmação),
    para o download acontecer sem intervenção manual.

    Args:
        pasta_download: pasta de destino dos downloads. Usa
            `SISTEMA.pasta_downloads` se não informado.

    Returns:
        Instância de `selenium.webdriver.Chrome` pronta para uso.
    """
    from pathlib import Path as _Path

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    pasta_download = pasta_download or SISTEMA.pasta_downloads
    pasta_download = _Path(pasta_download)
    pasta_download.mkdir(parents=True, exist_ok=True)

    opcoes = Options()
    opcoes.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(pasta_download.resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            # False é o valor correto para NÃO bloquear/perguntar no
            # download (o nome do prefs é enganoso: diz respeito a deixar
            # a checagem de segurança silenciosa, não a habilitá-la).
            "safebrowsing.enabled": False,
        },
    )

    driver = webdriver.Chrome(options=opcoes)
    logger.info("Navegador iniciado. Downloads irão para: %s", pasta_download.resolve())
    return driver


def salvar_diagnostico_falha(driver, contexto: str) -> "Path | None":
    """Salva o HTML e uma captura de tela da página atual em
    `logs/diagnostico/`, com carimbo de data/hora.

    Usado como último recurso quando um elemento esperado (ex.: campo de
    data, link de download) não aparece a tempo — em vez de o usuário
    precisar abrir o DevTools manualmente, os arquivos gerados aqui podem
    ser enviados diretamente para análise.

    Args:
        driver: WebDriver ativo, na tela onde a falha ocorreu.
        contexto: texto curto identificando a falha (ex.:
            'preencher_periodo_emissao'), usado no nome dos arquivos.

    Returns:
        Caminho do arquivo HTML salvo, ou None se nem isso foi possível
        (ex.: navegador já foi fechado).
    """
    from datetime import datetime as _datetime

    from config import LOGS_DIR

    pasta = LOGS_DIR / "diagnostico"
    pasta.mkdir(parents=True, exist_ok=True)

    carimbo = _datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_base = f"{carimbo}_{contexto}".replace(" ", "_")
    caminho_html = pasta / f"{nome_base}.html"
    caminho_png = pasta / f"{nome_base}.png"

    html_salvo = False
    try:
        caminho_html.write_text(driver.page_source, encoding="utf-8")
        html_salvo = True
    except Exception:
        logger.warning("Não foi possível salvar o HTML de diagnóstico (contexto: %s).", contexto)

    try:
        driver.save_screenshot(str(caminho_png))
    except Exception:
        logger.warning("Não foi possível salvar a captura de tela de diagnóstico (contexto: %s).", contexto)

    if html_salvo:
        logger.error(
            "Diagnóstico da falha salvo em: %s (HTML) e %s (imagem, se possível). "
            "Envie esses dois arquivos para análise.",
            caminho_html,
            caminho_png,
        )
        return caminho_html

    return None


def executar_ignorando_alertas(driver, acao, max_tentativas: int = 3, contexto: str = "ação"):
    """Executa `acao()` (ex.: um clique ou execute_script), tratando o
    alerta nativo "Já existe uma requisição em andamento" onde quer que
    ele apareça — aceita e tenta de novo, com pausa crescente entre
    tentativas.

    Args:
        driver: WebDriver ativo.
        acao: função sem argumentos que executa a ação desejada (pode
            levantar `UnexpectedAlertPresentException`).
        max_tentativas: número máximo de tentativas.
        contexto: texto curto para identificar a ação nos logs (ex.:
            "navegação", "gerar relatório").

    Raises:
        TimeoutError: se o alerta continuar aparecendo após todas as
            tentativas.
    """
    import time as _time

    from selenium.common.exceptions import UnexpectedAlertPresentException

    for tentativa in range(1, max_tentativas + 1):
        try:
            acao()
            return
        except UnexpectedAlertPresentException as e:
            logger.warning(
                "Alerta durante %s (tentativa %d/%d): '%s' — aceitando e "
                "tentando de novo em alguns segundos.",
                contexto,
                tentativa,
                max_tentativas,
                e.alert_text,
            )
            try:
                driver.switch_to.alert.accept()
            except Exception:
                pass
            _time.sleep(5 * tentativa)

    raise TimeoutError(
        f"O alerta 'Já existe uma requisição em andamento' continuou "
        f"aparecendo durante '{contexto}' após {max_tentativas} tentativas. "
        "Pode ser necessário aguardar mais tempo ou verificar manualmente "
        "no sistema."
    )


def obter_credenciais() -> dict[str, str]:
    """Monta o dicionário de credenciais, pedindo interativamente o que
    estiver faltando (nunca grava nada em arquivo).

    Returns:
        Dicionário com as chaves 'dominio', 'cpf', 'usuario', 'senha'.
    """
    dominio = CREDENCIAIS.dominio
    cpf = CREDENCIAIS.cpf or input("CPF de login (obrigatório em sessão nova): ").strip()
    usuario = CREDENCIAIS.usuario or input("Usuário: ").strip()
    senha = CREDENCIAIS.senha or getpass.getpass("Senha (não fica visível ao digitar): ")

    return {"dominio": dominio, "cpf": cpf, "usuario": usuario, "senha": senha}


def fazer_login(driver, url: str | None = None, timeout: int | None = None) -> None:
    """Acessa a tela de login e autentica no sistema SSW.

    Args:
        driver: instância do WebDriver do Selenium (já criada pelo chamador).
        url: URL da tela de login. Usa `SISTEMA.url_sistema` se não informado.
        timeout: segundos de espera explícita. Usa `SISTEMA.timeout_padrao_segundos`
            se não informado.

    Raises:
        TimeoutError: se os campos de login não aparecerem a tempo, ou se
            a página não sair da tela de login após o envio (credenciais
            incorretas, ou estrutura da página mudou).
    """
    url = url or SISTEMA.url_sistema
    timeout = timeout or SISTEMA.timeout_padrao_segundos

    if not url:
        raise ValueError(
            "URL do sistema não configurada. Verifique se o arquivo '.env' "
            "existe na pasta do projeto (não '.env.txt' — erro comum ao "
            "salvar pelo Bloco de Notas no Windows) e se a linha "
            "URL_SISTEMA=... está preenchida."
        )

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    credenciais = obter_credenciais()

    logger.info("Abrindo tela de login em: %s", url)
    driver.get(url)

    espera = WebDriverWait(driver, timeout)

    campo_usuario = espera.until(
        EC.presence_of_element_located((By.ID, ID_CAMPO_USUARIO))
    )

    if credenciais["dominio"]:
        campo_dominio = driver.find_element(By.ID, ID_CAMPO_DOMINIO)
        campo_dominio.clear()
        campo_dominio.send_keys(credenciais["dominio"])

    campo_cpf = driver.find_element(By.ID, ID_CAMPO_CPF)
    if not campo_cpf.get_attribute("value"):
        # só preenche se estiver vazio — se o "Lembrar CPF" já preencheu,
        # não mexe (evita apagar um valor válido por engano)
        campo_cpf.send_keys(credenciais["cpf"])

    campo_usuario.clear()
    campo_usuario.send_keys(credenciais["usuario"])

    campo_senha = driver.find_element(By.ID, ID_CAMPO_SENHA)
    campo_senha.clear()
    campo_senha.send_keys(credenciais["senha"])

    logger.info("Formulário preenchido. Clicando no botão de login...")
    botao_entrar = driver.find_element(By.ID, ID_BOTAO_ENTRAR)
    botao_entrar.click()

    logger.info("Login enviado. Aguardando confirmação de troca de tela...")

    # Confirmação de sucesso: o campo de senha (elemento da tela de login)
    # deixa de existir no DOM quando a página muda para a área logada.
    try:
        espera.until(EC.staleness_of(campo_senha))
    except Exception as e:
        salvar_diagnostico_falha(driver, "fazer_login")
        raise TimeoutError(
            "A tela de login não mudou após o envio. Verifique se as "
            "credenciais estão corretas ou se a estrutura da página mudou."
        ) from e

    logger.info("Login realizado com sucesso.")


def aguardar_confirmacao_manual(mensagem: str = "Confirme que o login foi concluído e pressione Enter...") -> None:
    """Alternativa mais simples/robusta: abre o sistema e deixa o próprio
    usuário fazer login manualmente, só aguardando confirmação no terminal.

    Útil como fallback caso `fazer_login` pare de funcionar (ex.: o
    sistema mudou algo na tela) — evita travar o processo todo por causa
    de um único passo automatizável.
    """
    input(mensagem)
    logger.info("Login confirmado manualmente pelo usuário.")


# ---------------------------------------------------------------------------
# Navegação pelo menu (tela "menu01") — usada para chegar em qualquer opção
# do sistema pelo código numérico (ex.: '455' = gerar relatório de entregas,
# '023' = consulta/reimpressão de manifesto).
# ---------------------------------------------------------------------------

# IDs reais dos campos da tela de menu (form action="/bin/menu01")
ID_CAMPO_UNIDADE = "2"
ID_CAMPO_OPCAO = "3"


def focar_janela_por_url(driver, trecho_url: str, timeout: int = 40) -> str:
    """Troca o Selenium para a janela cuja URL contém ``trecho_url``.

    Percorre todas as janelas porque o SSW abre as opções em pop-ups e,
    em algumas execuções, reutiliza uma janela já existente.
    """
    import time

    from selenium.common.exceptions import NoSuchWindowException, WebDriverException

    limite = time.monotonic() + timeout
    ultima_lista: list[str] = []

    while time.monotonic() < limite:
        urls_encontradas: list[str] = []

        for identificador in list(driver.window_handles):
            try:
                driver.switch_to.window(identificador)
                url_atual = driver.current_url
                urls_encontradas.append(url_atual)

                if trecho_url.lower() in url_atual.lower():
                    driver.switch_to.default_content()
                    logger.info("Janela correta selecionada: %s", url_atual)
                    return url_atual
            except (NoSuchWindowException, WebDriverException):
                continue

        if urls_encontradas != ultima_lista:
            logger.info("Janelas disponíveis durante a espera: %s", urls_encontradas)
            ultima_lista = urls_encontradas

        time.sleep(0.4)

    salvar_diagnostico_falha(driver, "focar_janela_por_url")
    raise TimeoutError(
        f"Não encontrei uma janela cuja URL contenha '{trecho_url}' após {timeout}s. "
        f"Últimas URLs encontradas: {ultima_lista}"
    )


def navegar_para_opcao(
    driver,
    opcao: str,
    unidade: str | None = None,
    timeout: int | None = None,
) -> None:
    """Abre uma opção do menu do SSW disparando somente uma requisição.

    O SSW usa a função JavaScript ``doOption()``. Não se deve chamar essa
    função e, em seguida, disparar também eventos input/change/keyup/blur,
    pois cada evento pode iniciar outra requisição e gerar o alerta
    "Já existe uma requisição em andamento".
    """
    import time

    from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    timeout = timeout or SISTEMA.timeout_padrao_segundos
    espera = WebDriverWait(driver, timeout)

    espera.until(EC.presence_of_element_located((By.ID, ID_CAMPO_OPCAO)))

    # Altera somente o valor do campo, sem disparar eventos input/change/blur.
    # No menu do SSW, send_keys pode iniciar uma requisição assíncrona e fazer
    # a opção seguinte receber o alerta "Já existe uma requisição em andamento".
    if unidade:
        campo_unidade = driver.find_element(By.ID, ID_CAMPO_UNIDADE)
        valor_atual = (campo_unidade.get_attribute("value") or "").strip()
        if valor_atual != unidade:
            driver.execute_script(
                "arguments[0].value = arguments[1];",
                campo_unidade,
                unidade,
            )
            logger.info(
                "Unidade ajustada de '%s' para '%s' sem disparar eventos.",
                valor_atual,
                unidade,
            )

    campo_opcao = espera.until(EC.element_to_be_clickable((By.ID, ID_CAMPO_OPCAO)))
    campo_opcao.clear()
    campo_opcao.send_keys(opcao)

    valor_lido = campo_opcao.get_attribute("value")
    do_option_existe = driver.execute_script("return typeof doOption === 'function';")
    logger.info(
        "Diagnóstico navegação: campo Opção contém '%s' (esperado '%s') | função doOption existe: %s",
        valor_lido,
        opcao,
        do_option_existe,
    )

    if not do_option_existe:
        raise RuntimeError("A função JavaScript doOption() não foi encontrada na tela do menu.")

    # Guarda o estado antes da navegação. Ler current_url depois do doOption
    # pode falhar se um alerta do SSW estiver aberto.
    try:
        url_anterior = driver.current_url
    except UnexpectedAlertPresentException:
        try:
            driver.switch_to.alert.accept()
        except NoAlertPresentException:
            pass
        url_anterior = driver.current_url

    # UMA única chamada. Sem eventos adicionais e sem repetir a opção.
    try:
        driver.execute_script("doOption();")
    except UnexpectedAlertPresentException:
        # A primeira solicitação pode já ter sido aceita pelo sistema antes
        # de o alerta surgir. Aceitamos o alerta, mas NÃO reenviamos a opção.
        try:
            alerta = driver.switch_to.alert
            logger.warning("Alerta após abrir a opção %s: '%s'. Aceitando sem repetir.", opcao, alerta.text)
            alerta.accept()
        except NoAlertPresentException:
            pass

    logger.info("Navegação para a opção '%s' disparada uma única vez.", opcao)

    # Para opções conhecidas, procura diretamente a janela correta.
    numero_opcao = str(opcao).lstrip("0")
    telas_por_opcao = {
        "455": "/bin/ssw0230",
        "23": "/bin/ssw0125",
    }
    trecho_url = telas_por_opcao.get(numero_opcao)
    if trecho_url:
        focar_janela_por_url(driver, trecho_url, timeout=max(timeout, 40))
        return

    # Para outras opções, aguarda alguma mudança de URL ou de janela.
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.current_url != url_anterior or len(d.window_handles) > 1
        )
    except Exception:
        logger.warning("Não foi possível confirmar automaticamente a abertura da opção '%s'.", opcao)
