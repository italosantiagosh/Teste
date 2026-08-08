"""Leitura e validação da tabela única de pedido (santo, modelo, tamanho, quantidade)."""

from pathlib import Path

import pandas as pd

from catalogo import Catalogo
from config_folhas import CONFIGS_TAMANHO, normalizar_chave_tamanho
from normalizacao import normalizar_nome, sugerir_correspondencia, sugerir_por_prefixo

# Depois de tantas tentativas de digitar de novo sem achar nada, desiste e
# vira erro — evita loop infinito se alguém automatizar a resposta errado.
MAXIMO_TENTATIVAS_DIGITACAO = 5

COLUNAS_OBRIGATORIAS = ["santo", "modelo", "tamanho", "quantidade"]


class ErroPedido(Exception):
    pass


def ler_tabela_pedido(caminho) -> pd.DataFrame:
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroPedido(f"Arquivo de pedido não encontrado: {caminho}")

    if caminho.suffix.lower() in (".xlsx", ".xlsm"):
        tabela = pd.read_excel(caminho)
    else:
        tabela = _ler_csv_com_fallback_de_codificacao(caminho)

    tabela.columns = [str(coluna).strip().lower() for coluna in tabela.columns]
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in tabela.columns]
    if faltando:
        raise ErroPedido(
            "A tabela de pedido precisa ter as colunas "
            f"{COLUNAS_OBRIGATORIAS}. Faltando: {faltando}."
        )
    return tabela


def _ler_csv_com_fallback_de_codificacao(caminho: Path) -> pd.DataFrame:
    ultimo_erro = None
    for codificacao in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(caminho, encoding=codificacao)
        except UnicodeDecodeError as erro:
            ultimo_erro = erro
    raise ErroPedido(
        f"Não consegui ler '{caminho.name}' em nenhuma codificação conhecida "
        f"(utf-8, cp1252, latin1). Salve o CSV como 'CSV UTF-8' no Excel. "
        f"Erro original: {ultimo_erro}"
    )


def resolver_pedido(tabela: pd.DataFrame, catalogo: Catalogo, perguntar_confirmacao=None, pedir_texto=None):
    """Valida cada linha da tabela, tentando corrigir nomes de santo parecidos.

    perguntar_confirmacao(mensagem) -> bool: confirma uma sugestão automática.
    pedir_texto(mensagem) -> str: usado quando não há sugestão (ou ela foi
      recusada), para o usuário digitar o nome correto na hora. Uma resposta
      vazia desiste da linha.
    Se ambos forem None, nenhuma correção acontece — linhas ambíguas viram
    erro direto (útil para rodar sem interação: testes, automação).

    Devolve (itens_resolvidos, erros):
      itens_resolvidos: lista de dicts {chave_santo, modelo, chave_tamanho, quantidade}
      erros: lista de strings descrevendo linhas que não puderam ser resolvidas
    """
    itens_resolvidos = []
    erros = []
    cache_correcoes: dict[str, str | None] = {}

    for indice, linha in tabela.iterrows():
        numero_linha = indice + 2  # +2: cabeçalho + índice 0-based

        try:
            quantidade = int(linha["quantidade"])
        except (TypeError, ValueError):
            erros.append(f"Linha {numero_linha}: quantidade inválida ({linha['quantidade']!r}).")
            continue
        if quantidade <= 0:
            continue

        try:
            config_tamanho = normalizar_chave_tamanho(linha["tamanho"])
            if config_tamanho not in CONFIGS_TAMANHO:
                tamanhos_validos = ", ".join(sorted(CONFIGS_TAMANHO))
                erros.append(
                    f"Linha {numero_linha}: tamanho '{linha['tamanho']}' não reconhecido "
                    f"(válidos: {tamanhos_validos})."
                )
                continue
        except Exception as erro:  # noqa: BLE001 - queremos reportar qualquer problema de parsing
            erros.append(f"Linha {numero_linha}: {erro}")
            continue

        santo_digitado = str(linha["santo"]).strip()
        modelo = str(linha["modelo"]).strip()
        chave_santo_digitada = normalizar_nome(santo_digitado)

        chave_santo_resolvida = _resolver_nome_santo(
            santo_digitado,
            chave_santo_digitada,
            catalogo,
            perguntar_confirmacao,
            pedir_texto,
            cache_correcoes,
        )
        if chave_santo_resolvida is None:
            erros.append(f"Linha {numero_linha}: santo '{santo_digitado}' não encontrado em imagens/.")
            continue

        if not catalogo.existe_modelo(chave_santo_resolvida, modelo):
            disponiveis = catalogo.modelos_disponiveis(chave_santo_resolvida)
            nome_bonito = catalogo.nome_bonito(chave_santo_resolvida)
            erros.append(
                f"Linha {numero_linha}: modelo '{modelo}' não existe para '{nome_bonito}'. "
                f"Modelos disponíveis: {', '.join(disponiveis) if disponiveis else '(nenhum)'}."
            )
            continue

        itens_resolvidos.append(
            {
                "chave_santo": chave_santo_resolvida,
                "modelo": modelo,
                "chave_tamanho": config_tamanho,
                "quantidade": quantidade,
            }
        )

    return itens_resolvidos, erros


def _resolver_nome_santo(
    santo_digitado, chave_digitada, catalogo: Catalogo, perguntar_confirmacao, pedir_texto, cache_correcoes
):
    if catalogo.existe_santo(chave_digitada):
        catalogo.registrar_nome_novo_se_ausente(chave_digitada, santo_digitado)
        return chave_digitada

    if chave_digitada in cache_correcoes:
        return cache_correcoes[chave_digitada]

    resultado = _tentar_resolver_interativamente(
        santo_digitado, chave_digitada, catalogo, perguntar_confirmacao, pedir_texto
    )
    cache_correcoes[chave_digitada] = resultado
    return resultado


def _sugerir(chave_digitada, catalogo: Catalogo):
    """Tenta primeiro achar um santo cadastrado que seja um "prefixo" do que
    foi digitado (ex.: 'guido_schaffer' -> 'guido': mesmo santo, sobrenome a
    mais que não está no catálogo). Só se isso falhar, cai pra semelhança
    geral de texto (cobre erro de digitação tipo 'sao_juse' -> 'sao_jose')."""
    chaves = catalogo.chaves_santos()
    return sugerir_por_prefixo(chave_digitada, chaves) or sugerir_correspondencia(chave_digitada, chaves)


def _tentar_resolver_interativamente(santo_digitado, chave_digitada, catalogo: Catalogo, perguntar_confirmacao, pedir_texto):
    texto_atual = santo_digitado
    chave_atual = chave_digitada

    for _ in range(MAXIMO_TENTATIVAS_DIGITACAO):
        if catalogo.existe_santo(chave_atual):
            return chave_atual

        sugestao = _sugerir(chave_atual, catalogo)
        if sugestao is not None and perguntar_confirmacao is not None:
            nome_sugerido = catalogo.nome_bonito(sugestao)
            if perguntar_confirmacao(f"'{texto_atual}' não encontrado. Você quis dizer '{nome_sugerido}'?"):
                return sugestao

        if pedir_texto is None:
            return None

        novo_texto = pedir_texto(
            f"Não encontrei '{texto_atual}' em imagens/. Digite o nome correto "
            "(ou deixe em branco para pular esta linha):"
        )
        if not novo_texto or not novo_texto.strip():
            return None
        texto_atual = novo_texto.strip()
        chave_atual = normalizar_nome(texto_atual)

    return None


def expandir_por_tamanho(itens_resolvidos):
    """Agrupa por tamanho e expande quantidade em uma medalha por unidade,
    preservando a ordem da tabela (igual aos scripts originais)."""
    medalhas_por_tamanho: dict[str, list[dict]] = {}
    for item in itens_resolvidos:
        lista = medalhas_por_tamanho.setdefault(item["chave_tamanho"], [])
        for _ in range(item["quantidade"]):
            lista.append({"chave_santo": item["chave_santo"], "modelo": item["modelo"]})
    return medalhas_por_tamanho
