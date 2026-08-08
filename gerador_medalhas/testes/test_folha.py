from PIL import Image

from config_folhas import ALTURA_FOLHA_MM, LARGURA_FOLHA_MM, ConfigTamanho
from folha import (
    calcular_posicoes_px,
    gerar_folhas,
    mm_para_pixels,
    montar_imagem_folha,
    paginar_com_preenchimento,
)
from imagens import CacheMedalhas

CONFIG_TESTE = ConfigTamanho(
    chave="16",
    nome_exibicao="16mm",
    diametro_mm=16,
    linhas=16,
    colunas=10,  # capacidade 160, igual ao exemplo do usuário (350 -> 2 cheias + 1 com 30)
    margem_esquerda_mm=10,
    margem_superior_mm=10,
    passo_horizontal_mm=16,
    passo_vertical_mm=16,
    deslocamento_horizontal_mm=8,
)


def test_paginar_com_preenchimento_gera_paginas_conforme_exemplo_do_usuario():
    medalhas = [{"chave_santo": "x", "modelo": "1"} for _ in range(350)]

    paginas = paginar_com_preenchimento(medalhas, capacidade=160, chave_santo_preenchimento="sao_jose", modelo_preenchimento="1")

    assert len(paginas) == 3
    assert paginas[0]["quantidade_pedida"] == 160
    assert paginas[0]["quantidade_preenchimento"] == 0
    assert paginas[1]["quantidade_pedida"] == 160
    assert paginas[1]["quantidade_preenchimento"] == 0
    assert paginas[2]["quantidade_pedida"] == 30
    assert paginas[2]["quantidade_preenchimento"] == 130
    assert len(paginas[2]["medalhas"]) == 160
    # o preenchimento usa o santo/modelo padrão
    assert paginas[2]["medalhas"][-1] == {"chave_santo": "sao_jose", "modelo": "1"}


def test_paginar_com_preenchimento_pedido_exato_nao_gera_folha_extra():
    medalhas = [{"chave_santo": "x", "modelo": "1"} for _ in range(320)]
    paginas = paginar_com_preenchimento(medalhas, capacidade=160, chave_santo_preenchimento="sao_jose", modelo_preenchimento="1")
    assert len(paginas) == 2
    assert all(p["quantidade_preenchimento"] == 0 for p in paginas)


def test_calcular_posicoes_px_tem_uma_posicao_por_espaco_da_grade():
    posicoes = calcular_posicoes_px(CONFIG_TESTE, dpi=300)
    assert len(posicoes) == CONFIG_TESTE.capacidade_por_folha
    # linhas pares não têm deslocamento; ímpares têm
    x_linha0_col0 = posicoes[0][0]
    x_linha1_col0 = posicoes[CONFIG_TESTE.colunas][0]
    assert x_linha1_col0 > x_linha0_col0


def test_montar_imagem_folha_gera_tamanho_a4_correto(tmp_path):
    pasta_imagens = tmp_path / "imagens"
    pasta_imagens.mkdir()
    Image.new("RGBA", (30, 30), (200, 50, 50, 255)).save(pasta_imagens / "sao_jose_modelo_1.png")

    dpi = 150
    cache = CacheMedalhas(pasta_imagens, mm_para_pixels(CONFIG_TESTE.diametro_mm, dpi))
    medalhas = [{"chave_santo": "sao_jose", "modelo": "1"}] * 5

    folha = montar_imagem_folha(medalhas, CONFIG_TESTE, cache, dpi)

    assert folha.size == (mm_para_pixels(LARGURA_FOLHA_MM, dpi), mm_para_pixels(ALTURA_FOLHA_MM, dpi))


def test_gerar_folhas_end_to_end_com_preenchimento(tmp_path):
    pasta_imagens = tmp_path / "imagens"
    pasta_imagens.mkdir()
    Image.new("RGBA", (30, 30), (200, 50, 50, 255)).save(pasta_imagens / "pedido_modelo_1.png")
    Image.new("RGBA", (30, 30), (50, 200, 50, 255)).save(pasta_imagens / "sao_jose_modelo_1.png")

    medalhas = [{"chave_santo": "pedido", "modelo": "1"} for _ in range(170)]

    folhas = gerar_folhas(medalhas, CONFIG_TESTE, pasta_imagens, dpi=150, chave_santo_preenchimento="sao_jose", modelo_preenchimento="1")

    assert len(folhas) == 2
    assert folhas[0]["quantidade_pedida"] == 160
    assert folhas[1]["quantidade_pedida"] == 10
    assert folhas[1]["quantidade_preenchimento"] == 150
