"""Paginação e montagem das folhas A4 com as medalhas circulares."""

from pathlib import Path

from PIL import Image

from config_folhas import ALTURA_FOLHA_MM, LARGURA_FOLHA_MM, ConfigTamanho
from imagens import CacheMedalhas


def mm_para_pixels(mm: float, dpi: int) -> int:
    return round(mm / 25.4 * dpi)


def calcular_posicoes_px(config: ConfigTamanho, dpi: int):
    """Posições (x_px, y_px) do canto de cada medalha, em ordem de leitura
    (linha a linha), reproduzindo a grade "hexagonal" (linhas alternadas
    deslocadas) usada no gabarito de corte."""
    posicoes = []
    for linha in range(config.linhas):
        deslocamento_x = config.deslocamento_horizontal_mm if linha % 2 else 0.0
        y_mm = config.margem_superior_mm + linha * config.passo_vertical_mm
        for coluna in range(config.colunas):
            x_mm = config.margem_esquerda_mm + deslocamento_x + coluna * config.passo_horizontal_mm
            posicoes.append((mm_para_pixels(x_mm, dpi), mm_para_pixels(y_mm, dpi)))
    return posicoes


def paginar_com_preenchimento(medalhas, capacidade, chave_santo_preenchimento, modelo_preenchimento):
    """Divide a lista de medalhas em folhas cheias; a última é completada
    com o santo de preenchimento até fechar a capacidade da folha.

    Devolve uma lista de dicts: {medalhas, quantidade_pedida, quantidade_preenchimento}
    """
    paginas = []
    pagina_atual = []
    for medalha in medalhas:
        pagina_atual.append(medalha)
        if len(pagina_atual) == capacidade:
            paginas.append({"medalhas": pagina_atual, "quantidade_pedida": capacidade, "quantidade_preenchimento": 0})
            pagina_atual = []

    if pagina_atual:
        quantidade_pedida = len(pagina_atual)
        quantidade_preenchimento = capacidade - quantidade_pedida
        for _ in range(quantidade_preenchimento):
            pagina_atual.append({"chave_santo": chave_santo_preenchimento, "modelo": modelo_preenchimento})
        paginas.append(
            {
                "medalhas": pagina_atual,
                "quantidade_pedida": quantidade_pedida,
                "quantidade_preenchimento": quantidade_preenchimento,
            }
        )

    return paginas


def montar_imagem_folha(pagina_medalhas, config: ConfigTamanho, cache: CacheMedalhas, dpi: int) -> Image.Image:
    largura_px = mm_para_pixels(LARGURA_FOLHA_MM, dpi)
    altura_px = mm_para_pixels(ALTURA_FOLHA_MM, dpi)
    folha = Image.new("RGBA", (largura_px, altura_px), (255, 255, 255, 255))

    posicoes = calcular_posicoes_px(config, dpi)
    for (x, y), medalha in zip(posicoes, pagina_medalhas):
        imagem_medalha = cache.obter(medalha["chave_santo"], medalha["modelo"])
        folha.paste(imagem_medalha, (x, y), imagem_medalha)
    return folha


def gerar_folhas(medalhas, config: ConfigTamanho, pasta_imagens: Path, dpi: int, chave_santo_preenchimento, modelo_preenchimento):
    """Gera todas as folhas necessárias para um tamanho de medalha.

    Devolve (folhas, cache):
      folhas: lista de dicts {imagem: PIL.Image, quantidade_pedida, quantidade_preenchimento}
      cache: o CacheMedalhas usado — permite checar depois quais santos
             foram ampliados além da resolução original (cache.imagens_ampliadas()).
    """
    capacidade = config.capacidade_por_folha
    paginas = paginar_com_preenchimento(medalhas, capacidade, chave_santo_preenchimento, modelo_preenchimento)

    cache = CacheMedalhas(pasta_imagens, mm_para_pixels(config.diametro_mm, dpi))
    resultado = []
    for pagina in paginas:
        imagem = montar_imagem_folha(pagina["medalhas"], config, cache, dpi)
        resultado.append(
            {
                "imagem": imagem,
                "quantidade_pedida": pagina["quantidade_pedida"],
                "quantidade_preenchimento": pagina["quantidade_preenchimento"],
            }
        )
    return resultado, cache


def _achatar_para_rgb_opaco(imagem_rgba: Image.Image) -> Image.Image:
    """Compõe a folha (RGBA) sobre um fundo branco opaco e descarta o canal
    alfa. A folha final nunca tem transparência de verdade (cada posição da
    grade é sempre preenchida, com pedido real ou com o santo de
    preenchimento) — então isso não perde nada visualmente, só evita
    carregar um 4º canal inteiro à toa no arquivo. Compor explicitamente
    sobre branco (em vez de só descartar o alfa) evita manchas escuras caso
    alguma arte de origem tenha transparência interna.
    """
    fundo = Image.new("RGB", imagem_rgba.size, (255, 255, 255))
    fundo.paste(imagem_rgba, (0, 0), imagem_rgba)
    return fundo


def salvar_folhas(folhas, pasta_saida: Path, config: ConfigTamanho, dpi: int, tambem_pdf: bool = False):
    """Salva cada folha como PNG (e opcionalmente PDF) e devolve os caminhos gerados."""
    pasta_saida = Path(pasta_saida) / config.nome_exibicao
    pasta_saida.mkdir(parents=True, exist_ok=True)

    caminhos = []
    total_paginas = len(folhas)
    for indice, folha in enumerate(folhas, start=1):
        nome_base = f"folha_{config.nome_exibicao}_pag{indice}_de_{total_paginas}"
        imagem_final = _achatar_para_rgb_opaco(folha["imagem"])

        caminho_png = pasta_saida / f"{nome_base}.png"
        imagem_final.save(caminho_png, dpi=(dpi, dpi), optimize=True, compress_level=9)
        caminhos.append(caminho_png)

        if tambem_pdf:
            caminho_pdf = pasta_saida / f"{nome_base}.pdf"
            imagem_final.save(caminho_pdf, resolution=dpi)
            caminhos.append(caminho_pdf)

    return caminhos
