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


def _localizar_relatorio_baixado():
    """Mais recente .csv/.xlsx em entrada/ - baixado pela opção 1 ou
    colocado manualmente na pasta. Usado como sugestão padrão na opção 3."""
    from config import ENTRADA_DIR

    candidatos = [
        p for p in ENTRADA_DIR.glob("*")
        if p.is_file() and p.suffix.lower() in {".csv", ".xlsx"}
    ]
    if not candidatos:
        return None
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def opcao_3_tratar_e_cruzar() -> None:
    from pathlib import Path

    import pandas as pd

    from config import SAIDA_DIR
    from src import cruzamento, relatorio_visual
    from src import tratamento_planilha as tp

    sugestao = _localizar_relatorio_baixado()
    if sugestao:
        resposta = input(
            f"Usar o arquivo mais recente encontrado em entrada/ ({sugestao.name})? "
            "Pressione Enter para usá-lo, ou digite outro caminho: "
        ).strip()
        caminho_str = resposta or str(sugestao)
    else:
        caminho_str = input(
            "Nenhum arquivo encontrado em entrada/. Informe o caminho do "
            "arquivo baixado (ex.: entrada/relatorio050826.csv): "
        ).strip()

    if not caminho_str:
        print("Nenhum caminho informado.")
        return

    caminho_relatorio = Path(caminho_str)
    caminho_motoristas = SAIDA_DIR / "motoristas_capturados.xlsx"

    try:
        df_pedidos = tp.tratar_planilha(caminho_relatorio)
        print(f"Planilha tratada com sucesso. {len(df_pedidos)} linhas finais.")

        if not caminho_motoristas.exists():
            print(
                "Erro: a tabela de motoristas ainda não foi encontrada em "
                f"{caminho_motoristas}. Execute primeiro a opção 2."
            )
            return

        df_motoristas = pd.read_excel(caminho_motoristas, dtype=str)
        resultados = cruzamento.cruzar_pedidos_motoristas(
            df_pedidos,
            df_motoristas,
            coluna_primeiro_manifesto="primeiro_manifesto",
            coluna_ultimo_manifesto="ultimo_manifesto",
            coluna_chave_motoristas="manifesto",
        )

        nome_base = caminho_relatorio.stem
        caminho_final = SAIDA_DIR / f"{nome_base}_com_motoristas.xlsx"
        caminho_sem = SAIDA_DIR / "pedidos_sem_motorista.xlsx"
        caminho_sobras = SAIDA_DIR / "motoristas_sem_pedido.xlsx"
        caminho_conflitos = SAIDA_DIR / "conflitos_manifestos.xlsx"

        resultados["relatorio_completo"].to_excel(caminho_final, index=False)
        resultados["sem_motorista"].to_excel(caminho_sem, index=False)
        resultados["motoristas_sem_pedido"].to_excel(caminho_sobras, index=False)
        resultados["conflitos"].to_excel(caminho_conflitos, index=False)

        qtd_com = len(resultados["com_motorista"])
        qtd_sem = len(resultados["sem_motorista"])
        print(f"Cruzamento concluído: {qtd_com} pedidos com motorista e {qtd_sem} sem correspondência.")
        print(f"Relatório final salvo em: {caminho_final}")
        if qtd_sem:
            print(f"Pedidos para conferência salvos em: {caminho_sem}")

        caminho_visual = SAIDA_DIR / f"{nome_base}_analise_visual.xlsx"
        relatorio_visual.gerar_relatorio_visual(resultados["relatorio_completo"], caminho_visual)
        print(f"Planilha visual (KPIs e gráficos) salva em: {caminho_visual}")

    except (FileNotFoundError, ValueError, pd.errors.ParserError) as e:
        print(f"Erro: {e}")


def _localizar_relatorio_final():
    from config import SAIDA_DIR
    candidatos = sorted(
        SAIDA_DIR.glob("*_com_motoristas.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidatos:
        raise FileNotFoundError(
            "Nenhum relatório com motoristas foi encontrado. Execute primeiro a opção 3."
        )
    return candidatos[0]


# Colunas que a mensagem de posição de cargas depende para não sair com
# "NÃO INFORMADO" à toa — usadas para detectar uma seleção salva ANTES
# dessas colunas existirem (cache antigo, de uma versão anterior do
# programa) e descartá-la em vez de reaproveitar dado incompleto.
_COLUNAS_MENSAGEM_OBRIGATORIAS = ["remetente", "pagador", "nf", "peso_real", "volumes", "valor_frete"]


def _carregar_ou_selecionar_clientes():
    import json
    import pandas as pd
    from config import SAIDA_DIR
    from src import clientes

    planilha_selecionada = SAIDA_DIR / "cliente_selecionado.xlsx"
    info_selecionada = SAIDA_DIR / "cliente_selecionado.json"
    usar_anterior = False
    if planilha_selecionada.exists() and info_selecionada.exists():
        resposta = input("Usar a última seleção de clientes? (s/n): ").strip().lower()
        usar_anterior = resposta == "s"

    if usar_anterior:
        dados = pd.read_excel(planilha_selecionada)
        colunas_faltando = [c for c in _COLUNAS_MENSAGEM_OBRIGATORIAS if c not in dados.columns]
        if colunas_faltando:
            print(
                "A última seleção salva é de uma versão anterior do programa e não tem "
                f"as colunas {colunas_faltando} — descartando o cache e selecionando de novo "
                "a partir do relatório mais recente."
            )
        else:
            info = json.loads(info_selecionada.read_text(encoding="utf-8"))
            return dados, info

    caminho = _localizar_relatorio_final()
    df = pd.read_excel(caminho)
    dados, info = clientes.selecionar_varios_clientes_interativo(df)
    clientes.salvar_selecao(dados, info, SAIDA_DIR)
    return dados, info


def opcao_4_consultar_cliente() -> None:
    dados, info = _carregar_ou_selecionar_clientes()
    print(f"\nClientes selecionados: {info['nome']}")
    print(f"Quantidade de cargas: {len(dados)}")

    colunas_exibir = [
        c for c in [
            "pedido", "remetente", "pagador", "cidade", "nf", "peso_real",
            "volumes", "valor_frete", "motorista", "status", "previsao_entrega",
        ]
        if c in dados.columns
    ]
    if colunas_exibir:
        print(dados[colunas_exibir].to_string(index=False))


def opcao_5_gerar_mensagem() -> None:
    from config import SAIDA_DIR
    from src import mensagem

    dados, info = _carregar_ou_selecionar_clientes()
    dados_mensagem = mensagem.filtrar_pedidos_para_mensagem(dados)
    if len(dados_mensagem) < len(dados):
        print(
            f"{len(dados) - len(dados_mensagem)} carga(s) com 'saída para entrega' "
            "há 2+ dias não entraram na mensagem (provavelmente já entregues)."
        )
    situacoes = mensagem.revisar_situacoes_interativo(dados_mensagem)
    texto = mensagem.montar_mensagem_clientes(dados_mensagem, situacoes)
    blocos = mensagem.dividir_mensagem(texto)

    caminho = SAIDA_DIR / "mensagem_cliente.txt"
    caminho.write_text("\n\n---\n\n".join(blocos), encoding="utf-8")
    print("\n" + "=" * 60)
    print("\n\n---\n\n".join(blocos))
    print("=" * 60)
    print(f"Mensagem salva em: {caminho}")


def _buscar_telefones_clientes(nomes: list[str]) -> dict[str, str]:
    from config import CLIENTES
    from src.utils import normalizar_texto

    telefones: dict[str, str] = {}
    for nome in nomes:
        alvo = normalizar_texto(nome)
        for cadastro in CLIENTES.get("clientes", []):
            if alvo and normalizar_texto(cadastro.get("nome", "")) == alvo:
                telefones[nome] = str(cadastro.get("whatsapp", ""))
                break
    return telefones


def _escolher_telefone_envio(info: dict) -> str:
    nomes = info.get("nomes") or [info.get("nome", "")]
    telefones = _buscar_telefones_clientes(nomes)
    valores_unicos = set(telefones.values())

    if len(valores_unicos) == 1:
        return next(iter(valores_unicos))

    if telefones:
        print("\nTelefones cadastrados encontrados para os clientes selecionados:")
        for nome, telefone in telefones.items():
            print(f"  {nome}: {telefone}")
        if len(telefones) < len(nomes):
            faltando = [n for n in nomes if n not in telefones]
            print(f"Sem cadastro de WhatsApp: {', '.join(faltando)}")
        return input("Qual telefone usar para o envio (DDI+DDD+número)? ").strip()

    return input("Telefone com DDI e DDD (ex.: 5584999999999): ").strip()


def opcao_6_preparar_whatsapp() -> None:
    from src import mensagem, whatsapp

    dados, info = _carregar_ou_selecionar_clientes()
    dados_mensagem = mensagem.filtrar_pedidos_para_mensagem(dados)
    if len(dados_mensagem) < len(dados):
        print(
            f"{len(dados) - len(dados_mensagem)} carga(s) com 'saída para entrega' "
            "há 2+ dias não entraram na mensagem (provavelmente já entregues)."
        )
    situacoes = mensagem.revisar_situacoes_interativo(dados_mensagem)
    texto = mensagem.montar_mensagem_clientes(dados_mensagem, situacoes)
    blocos = mensagem.dividir_mensagem(texto)
    telefone = _escolher_telefone_envio(info)

    for indice, bloco in enumerate(blocos, 1):
        if len(blocos) > 1:
            print(f"Preparando mensagem {indice} de {len(blocos)}.")
        if not whatsapp.preparar_e_enviar_mensagem(telefone, bloco):
            break
        if indice < len(blocos):
            input("Depois de enviar no WhatsApp, pressione Enter para abrir a próxima parte...")


def opcao_7_processo_completo() -> None:
    print("\nFluxo completo usando os arquivos já disponíveis.")
    print("A etapa de download permanece manual por enquanto.")

    executar_captura = input("Capturar agora a tabela de motoristas? (s/n): ").strip().lower()
    if executar_captura == "s":
        opcao_2_capturar_motoristas()

    opcao_3_tratar_e_cruzar()
    resposta = input("Consultar um cliente e preparar a mensagem agora? (s/n): ").strip().lower()
    if resposta == "s":
        opcao_4_consultar_cliente()
        opcao_5_gerar_mensagem()
        enviar = input("Preparar também no WhatsApp Web? (s/n): ").strip().lower()
        if enviar == "s":
            opcao_6_preparar_whatsapp()

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
