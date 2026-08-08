"""Normalização de nomes de santos e busca por nomes parecidos (fuzzy match)."""

import difflib
import unicodedata

# Abaixo do quê a sugestão automática não é confiável o suficiente para
# perguntar ao usuário; erros mais graves de digitação caem como "não
# encontrado" em vez de uma sugestão estranha.
LIMIAR_SUGESTAO = 0.6


def normalizar_nome(texto: str) -> str:
    """'São José' -> 'sao_jose'. Usado como chave de comparação e no nome do arquivo."""
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace(" ", "_").replace("-", "_")
    while "__" in texto:
        texto = texto.replace("__", "_")
    return texto.strip("_")


def sugerir_correspondencia(chave_digitada: str, chaves_conhecidas):
    """Devolve a chave conhecida mais parecida com chave_digitada, ou None.

    chaves_conhecidas: iterável de chaves já normalizadas (normalizar_nome).
    """
    chaves_conhecidas = list(chaves_conhecidas)
    if not chaves_conhecidas:
        return None
    correspondencias = difflib.get_close_matches(
        chave_digitada, chaves_conhecidas, n=1, cutoff=LIMIAR_SUGESTAO
    )
    return correspondencias[0] if correspondencias else None


def sugerir_por_prefixo(chave_digitada: str, chaves_conhecidas):
    """Cobre o caso de um nome digitado "maior" que o cadastrado, tipo
    'guido_schaffer' quando só existe 'guido' — a diferença de tamanho faz
    o índice de semelhança do difflib ficar baixo demais mesmo quando é
    claramente o mesmo santo com um sobrenome/apelido a mais no fim.

    Vai tirando a última palavra e testando se o que sobra bate exatamente
    com alguma chave conhecida; devolve a primeira (mais longa) que bater.
    """
    chaves_conhecidas = set(chaves_conhecidas)
    tokens = chave_digitada.split("_")
    for quantidade_tokens in range(len(tokens) - 1, 0, -1):
        candidata = "_".join(tokens[:quantidade_tokens])
        if candidata in chaves_conhecidas:
            return candidata
    return None
