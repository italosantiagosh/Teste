"""
Ponto de entrada da automação. Apresenta o menu de opções descrito no
planejamento. Etapas ainda não implementadas informam isso claramente ao
usuário em vez de falhar silenciosamente ou simular um resultado.
"""

from __future__ import annotations

import logging
import sys


def _checar_dependencias() -> None:
    """Confere se as bibliotecas do requirements.txt estão instaladas
    ANTES de importar qualquer coisa do projeto, e mostra uma mensagem
    clara (em vez de um erro técnico) se faltar alguma.
    """
    pacotes_necessarios = {
        "pandas": "pandas",
        "openpyxl": "openpyxl",
        "bs4": "beautifulsoup4",
        "selenium": "selenium",
        "dotenv": "python-dotenv",
    }
    faltando = []
    for modulo, nome_pacote in pacotes_necessarios.items():
        try:
            __import__(modulo)
        except ImportError:
            faltando.append(nome_pacote)

    if faltando:
        print("Faltam instalar as seguintes bibliotecas antes de rodar o programa:")
        for pacote in faltando:
            print(f"  - {pacote}")
        print()
        print("Abra um terminal na pasta do projeto e rode:")
        print("  pip install -r requirements.txt")
        sys.exit(1)


_checar_dependencias()

from config import LOGS_DIR
from src.utils import configurar_logging

logger = configurar_logging(LOGS_DIR)


MENU = """
1 - Baixar novo relatório
2 - Capturar tabela de motoristas
3 - Tratar e cruzar os dados
4 - Consultar cliente
5 - Gerar mensagem de um cliente
6 - Preparar envio pelo WhatsApp
7 - Executar processo completo
8 - Sair
"""


def opcao_1_baixar_relatorio() -> None:
    from datetime import date, datetime, timedelta

    from config import CREDENCIAIS, SISTEMA
    from src import download_relatorio, sistema

    data_final = date.today()
    data_inicial = data_final - timedelta(days=15)

    print(f"Período padrão: {data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y} (últimos 15 dias).")
    resposta = input(
        "Pressione Enter para confirmar, ou digite outro período no "
        "formato dd/mm/aaaa-dd/mm/aaaa: "
    ).strip()

    if resposta:
        try:
            ini_str, fim_str = resposta.split("-")
            data_inicial = datetime.strptime(ini_str.strip(), "%d/%m/%Y").date()
            data_final = datetime.strptime(fim_str.strip(), "%d/%m/%Y").date()
        except ValueError:
            print("Formato inválido — mantendo o período padrão dos últimos 15 dias.")

    if not CREDENCIAIS.usuario:
        print(
            "Não é possível continuar: SISTEMA_USUARIO não está definido no "
            ".env (é usado para filtrar o relatório certo na fila)."
        )
        return

    driver = sistema.criar_driver()
    try:
        sistema.fazer_login(driver, SISTEMA.url_sistema)
        arquivo = download_relatorio.baixar_relatorio(
            driver,
            data_inicial,
            data_final,
            usuario=CREDENCIAIS.usuario,
        )
        print(f"Relatório baixado em: {arquivo}")
    finally:
        driver.quit()


def opcao_2_capturar_motoristas() -> None:
    from datetime import date, datetime, timedelta

    from config import SISTEMA
    from src import captura_motoristas, sistema

    data_final = date.today()
    data_inicial = data_final - timedelta(days=15)

    print(f"Período padrão (saída): {data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y}.")
    resposta = input("Pressione Enter para confirmar, ou dd/mm/aaaa-dd/mm/aaaa: ").strip()
    if resposta:
        try:
            ini_str, fim_str = resposta.split("-")
            data_inicial = datetime.strptime(ini_str.strip(), "%d/%m/%Y").date()
            data_final = datetime.strptime(fim_str.strip(), "%d/%m/%Y").date()
        except ValueError:
            print("Formato inválido — mantendo o período padrão.")

    driver = sistema.criar_driver()
    try:
        sistema.fazer_login(driver, SISTEMA.url_sistema)
        df = captura_motoristas.buscar_motoristas_por_periodo(driver, data_inicial, data_final)
        caminho = SISTEMA.pasta_saida / "motoristas_capturados.xlsx"
        df.to_excel(caminho, index=False)
        print(f"{len(df)} motoristas capturados. Salvo em: {caminho}")
    finally:
        driver.quit()


def opcao_3_tratar_e_cruzar() -> None:
    from pathlib import Path
    from src import tratamento_planilha as tp

    caminho_str = input(
        "Caminho do arquivo baixado (ex.: entrada/relatorio_entregas.xlsx): "
    ).strip()
    if not caminho_str:
        print("Nenhum caminho informado.")
        return

    try:
        df = tp.tratar_planilha(Path(caminho_str))
        print(f"Planilha tratada com sucesso. {len(df)} linhas finais.")
        print("Cruzamento com motoristas (Etapa 5) ainda não implementado.")
    except FileNotFoundError as e:
        print(f"Erro: {e}")


def opcao_4_consultar_cliente() -> None:
    from src import clientes  # noqa: F401
    print("Etapa 7 (consulta de cliente) ainda não implementada.")


def opcao_5_gerar_mensagem() -> None:
    from src import mensagem  # noqa: F401
    print("Etapa 8 (montagem da mensagem de texto) ainda não implementada.")


def opcao_6_preparar_whatsapp() -> None:
    from src import whatsapp  # noqa: F401
    print("Etapa 9 (envio pelo WhatsApp) ainda não implementada.")


def opcao_7_processo_completo() -> None:
    print("Processo completo depende de todas as etapas estarem prontas.")
    print("Ainda faltam as Etapas 2, 4, 5, 6, 7, 8 e 9.")


def main() -> None:
    acoes = {
        "1": opcao_1_baixar_relatorio,
        "2": opcao_2_capturar_motoristas,
        "3": opcao_3_tratar_e_cruzar,
        "4": opcao_4_consultar_cliente,
        "5": opcao_5_gerar_mensagem,
        "6": opcao_6_preparar_whatsapp,
        "7": opcao_7_processo_completo,
    }

    while True:
        print(MENU)
        escolha = input("Escolha uma opção: ").strip()

        if escolha == "8":
            print("Encerrando.")
            break

        acao = acoes.get(escolha)
        if acao is None:
            print("Opção inválida.")
            continue

        try:
            acao()
        except NotImplementedError as e:
            print(f"Ainda não disponível: {e}")
        except Exception as e:
            logger.exception("Erro inesperado ao executar a opção %s", escolha)
            print(f"Deu erro: [{type(e).__name__}] {e}")
            print("(Detalhes completos também foram salvos em logs/automacao.log)")


if __name__ == "__main__":
    main()
