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
            # download de .xlsx/.csv (o nome do prefs é enganoso: diz
            # respeito a deixar a checagem de segurança silenciosa, não a
            # habilitá-la).
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
    data de uma tela) não aparece a tempo — em vez de o usuário precisar
    abrir o DevTools manualmente, os arquivos gerados aqui podem ser
    enviados diretamente para análise.

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


def navegar_para_opcao(driver, opcao: str, unidade: str | None = None, timeout: int | None = None) -> None:
    """Navega para uma tela do sistema pelo código numérico da opção.

    Reproduz o fluxo manual: preenche 'Unidade' (ex.: 'GRU') e 'Opção'
    (ex.: '455'), e dispara a navegação chamando diretamente a função
    JavaScript `doOption()` do próprio sistema (em vez de simular Tab),
    o que evita falhas de temporização entre preencher o campo e o
    sistema reagir ao evento de mudança.

    Args:
        driver: instância do WebDriver, já logada e na tela de menu.
        opcao: código numérico da tela de destino (ex.: '455', '023').
        unidade: código da unidade/filial (ex.: 'GRU'). Se None, usa
            `SISTEMA.unidade_padrao` (configurável) e, na ausência dela,
            não mexe no campo (mantém o valor que já estiver lá).
        timeout: segundos de espera explícita.
    """
    timeout = timeout or SISTEMA.timeout_padrao_segundos

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    espera = WebDriverWait(driver, timeout)

    espera.until(EC.presence_of_element_located((By.ID, ID_CAMPO_OPCAO)))

    janelas_antes = driver.window_handles

    if unidade:
        campo_unidade = driver.find_element(By.ID, ID_CAMPO_UNIDADE)
        campo_unidade.clear()
        campo_unidade.send_keys(unidade)

    # Busca o campo de novo (não reaproveita a referência de cima) — se
    # preencher 'Unidade' disparar uma atualização parcial da página
    # (o sistema faz isso via 'atualizaQuadroIndicadores'), a referência
    # antiga pode ficar desatualizada.
    campo_opcao = driver.find_element(By.ID, ID_CAMPO_OPCAO)
    campo_opcao.clear()
    campo_opcao.send_keys(opcao)

    valor_lido = campo_opcao.get_attribute("value")
    doOption_existe = driver.execute_script("return typeof doOption === 'function';")
    logger.info(
        "Diagnóstico navegação: campo Opção contém '%s' (esperado '%s') | "
        "função doOption existe: %s",
        valor_lido,
        opcao,
        doOption_existe,
    )

    # Tenta disparar a navegação, tratando o alerta "Já existe uma
    # requisição em andamento" onde quer que ele apareça (usa o helper
    # `executar_ignorando_alertas`, que aceita e tenta de novo).
    script_navegacao = """
        var el = arguments[0];
        if (typeof doOption === 'function') { doOption(); }
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        el.dispatchEvent(new Event('keyup', {bubbles: true}));
        el.blur();
    """

    def _disparar_navegacao():
        nonlocal campo_opcao
        driver.execute_script(script_navegacao, campo_opcao)

        # Mesmo sem exceção do execute_script, o alerta pode aparecer
        # de forma assíncrona logo em seguida.
        from selenium.common.exceptions import (
            NoAlertPresentException,
            TimeoutException as _TimeoutException,
            UnexpectedAlertPresentException,
        )

        try:
            WebDriverWait(driver, 2).until(EC.alert_is_present())
            texto = driver.switch_to.alert.text
            raise UnexpectedAlertPresentException(alert_text=texto)
        except (_TimeoutException, NoAlertPresentException):
            pass  # nenhum alerta — deu certo

    def _tentar_de_novo_apos_alerta():
        nonlocal campo_opcao
        campo_opcao = driver.find_element(By.ID, ID_CAMPO_OPCAO)
        campo_opcao.clear()
        campo_opcao.send_keys(opcao)
        _disparar_navegacao()

    try:
        _disparar_navegacao()
    except Exception as e:
        from selenium.common.exceptions import UnexpectedAlertPresentException

        if not isinstance(e, UnexpectedAlertPresentException):
            raise
        executar_ignorando_alertas(
            driver, _tentar_de_novo_apos_alerta, contexto=f"navegação para '{opcao}'"
        )

    logger.info("Navegação solicitada para a opção '%s' (unidade: %s).", opcao, unidade or "(mantida)")

    # Verifica se uma NOVA aba/janela abriu (o SSW costuma abrir cada
    # opção em uma janela própria) e, se sim, troca o controle do
    # Selenium para ela — senão o código continuaria "olhando" para a
    # janela antiga do menu, mesmo com a nova já na tela.
    trocou_de_janela = False
    try:
        WebDriverWait(driver, min(timeout, 10)).until(
            lambda d: len(d.window_handles) > len(janelas_antes)
        )
        nova_janela = [j for j in driver.window_handles if j not in janelas_antes][0]
        driver.switch_to.window(nova_janela)
        trocou_de_janela = True
        logger.info("Nova aba/janela detectada e selecionada: %s", driver.current_url)
    except Exception:
        logger.info(
            "Nenhuma aba/janela nova detectada — a navegação deve ter "
            "acontecido na mesma janela."
        )

    # Se trocamos de janela, a referência antiga de `campo_opcao` pertence
    # a outro contexto de navegação — não faz sentido checar staleness
    # dela. Só roda essa checagem quando ficamos na mesma janela.
    if not trocou_de_janela:
        try:
            WebDriverWait(driver, min(timeout, 5)).until(EC.staleness_of(campo_opcao))
        except Exception:
            logger.warning(
                "Não confirmei a troca de tela para a opção '%s' pelo método "
                "usual, mas a navegação foi enviada — seguindo em frente.",
                opcao,
            )

    logger.info("URL após navegação para '%s': %s", opcao, driver.current_url)

    import time

    time.sleep(1.0)  # pequena margem para a tela terminar de carregar
