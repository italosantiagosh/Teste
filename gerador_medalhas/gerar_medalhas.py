"""Ponto de entrada: lê o pedido, valida os nomes, gera as folhas de todos os
tamanhos presentes na tabela e abre os arquivos gerados.

Uso:
    python gerar_medalhas.py [caminho_do_pedido] [--dpi 600] [--pdf] [--sem-confirmar]

Se caminho_do_pedido não for informado, usa pedidos/pedido.csv.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from catalogo import Catalogo
from config_folhas import (
    MODELO_PREENCHIMENTO_PADRAO,
    SANTO_PREENCHIMENTO_PADRAO,
    obter_config_tamanho,
)
from folha import gerar_folhas, salvar_folhas
from normalizacao import normalizar_nome
from pedido import ErroPedido, expandir_por_tamanho, ler_tabela_pedido, resolver_pedido

PASTA_BASE = Path(__file__).resolve().parent
PASTA_IMAGENS_PADRAO = PASTA_BASE / "imagens"
PASTA_SAIDA_PADRAO = PASTA_BASE / "saida"
PASTA_PEDIDOS_PADRAO = PASTA_BASE / "pedidos"
CAMINHO_NOMES_EXIBICAO_PADRAO = PASTA_BASE / "config" / "nomes_exibicao.json"

DPI_PADRAO = 600


def perguntar_confirmacao_terminal(mensagem: str) -> bool:
    resposta = input(f"{mensagem} [S/n] ").strip().lower()
    return resposta in ("", "s", "sim", "y", "yes")


def abrir_arquivo(caminho: Path):
    try:
        if sys.platform.startswith("win"):
            import os

            os.startfile(caminho)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(caminho)], check=False)
        else:
            subprocess.run(["xdg-open", str(caminho)], check=False)
    except OSError:
        pass  # abrir automaticamente é conveniência, não deve derrubar o programa


def montar_argumentos():
    parser = argparse.ArgumentParser(description="Gera folhas de medalhas de santos para corte no Silhouette Studio.")
    parser.add_argument("pedido", nargs="?", default=None, help="Caminho do CSV/XLSX com o pedido (padrão: pedidos/pedido.csv)")
    parser.add_argument("--imagens", default=None, help="Pasta com as imagens dos santos (padrão: imagens/)")
    parser.add_argument("--saida", default=None, help="Pasta onde salvar as folhas geradas (padrão: saida/)")
    parser.add_argument("--dpi", type=int, default=DPI_PADRAO, help=f"Resolução de saída em DPI (padrão: {DPI_PADRAO})")
    parser.add_argument("--pdf", action="store_true", help="Também salva cada folha como PDF (tamanho físico sem ambiguidade de DPI ao importar)")
    parser.add_argument("--sem-confirmar", action="store_true", help="Não pergunta nada; nomes não encontrados exatamente viram erro")
    parser.add_argument("--nao-abrir", action="store_true", help="Não abre as folhas geradas automaticamente ao final")
    return parser.parse_args()


def main():
    argumentos = montar_argumentos()

    caminho_pedido = Path(argumentos.pedido) if argumentos.pedido else PASTA_PEDIDOS_PADRAO / "pedido.csv"
    pasta_imagens = Path(argumentos.imagens) if argumentos.imagens else PASTA_IMAGENS_PADRAO
    pasta_saida = Path(argumentos.saida) if argumentos.saida else PASTA_SAIDA_PADRAO

    try:
        tabela = ler_tabela_pedido(caminho_pedido)
    except ErroPedido as erro:
        print(f"Erro: {erro}")
        sys.exit(1)

    catalogo = Catalogo(pasta_imagens, CAMINHO_NOMES_EXIBICAO_PADRAO)
    if not catalogo.chaves_santos():
        print(f"Nenhuma imagem encontrada em {pasta_imagens}. Confira o padrão de nome: santo_modelo_1.png")
        sys.exit(1)

    perguntar = None if argumentos.sem_confirmar else perguntar_confirmacao_terminal
    itens_resolvidos, erros = resolver_pedido(tabela, catalogo, perguntar)
    catalogo.salvar_nomes_exibicao()

    if erros:
        print("\nNão foi possível processar as seguintes linhas:")
        for erro in erros:
            print(f"  - {erro}")
        if not itens_resolvidos:
            sys.exit(1)
        print()

    medalhas_por_tamanho = expandir_por_tamanho(itens_resolvidos)
    if not medalhas_por_tamanho:
        print("Nenhuma medalha válida no pedido.")
        sys.exit(1)

    chave_preenchimento = normalizar_nome(SANTO_PREENCHIMENTO_PADRAO)
    if not catalogo.existe_santo(chave_preenchimento) or not catalogo.existe_modelo(
        chave_preenchimento, MODELO_PREENCHIMENTO_PADRAO
    ):
        print(
            f"Aviso: santo de preenchimento padrão "
            f"'{SANTO_PREENCHIMENTO_PADRAO}' modelo {MODELO_PREENCHIMENTO_PADRAO} "
            "não está disponível em imagens/. Folhas parcialmente cheias vão falhar."
        )

    todos_arquivos_gerados = []
    for chave_tamanho, medalhas in medalhas_por_tamanho.items():
        config_tamanho = obter_config_tamanho(chave_tamanho)
        folhas = gerar_folhas(
            medalhas,
            config_tamanho,
            pasta_imagens,
            argumentos.dpi,
            chave_preenchimento,
            MODELO_PREENCHIMENTO_PADRAO,
        )
        caminhos = salvar_folhas(folhas, pasta_saida, config_tamanho, argumentos.dpi, tambem_pdf=argumentos.pdf)
        todos_arquivos_gerados.extend(caminhos)

        print(f"\n{config_tamanho.nome_exibicao}: {len(medalhas)} medalha(s) pedida(s), {len(folhas)} folha(s) gerada(s)")
        for indice, folha in enumerate(folhas, start=1):
            print(
                f"  Folha {indice}/{len(folhas)}: {folha['quantidade_pedida']} do pedido"
                + (f" + {folha['quantidade_preenchimento']} de preenchimento" if folha["quantidade_preenchimento"] else "")
            )

    print(f"\n{len(todos_arquivos_gerados)} arquivo(s) salvos em {pasta_saida}")
    if not argumentos.nao_abrir:
        for caminho in todos_arquivos_gerados:
            abrir_arquivo(caminho)


if __name__ == "__main__":
    main()
