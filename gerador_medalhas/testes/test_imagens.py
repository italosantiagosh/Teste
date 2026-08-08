from PIL import Image

from imagens import ImagemNaoEncontrada, localizar_imagem, preparar_medalha_circular


def test_localizar_imagem_encontra_arquivo(tmp_path):
    (tmp_path / "sao_jose_modelo_1.png").touch()
    caminho = localizar_imagem(tmp_path, "São José", "1")
    assert caminho.name == "sao_jose_modelo_1.png"


def test_localizar_imagem_arquivo_ausente(tmp_path):
    try:
        localizar_imagem(tmp_path, "Inexistente", "1")
        assert False, "deveria ter levantado ImagemNaoEncontrada"
    except ImagemNaoEncontrada:
        pass


def test_preparar_medalha_circular_recorta_em_circulo(tmp_path):
    # imagem retangular colorida (não quadrada), para testar o recorte central
    origem = Image.new("RGBA", (200, 100), (10, 20, 30, 255))
    caminho = tmp_path / "santo_modelo_1.png"
    origem.save(caminho)

    diametro_px = 40
    resultado = preparar_medalha_circular(caminho, diametro_px)

    assert resultado.size == (diametro_px, diametro_px)
    assert resultado.mode == "RGBA"

    # cantos devem ficar transparentes (fora do círculo)
    canto = resultado.getpixel((0, 0))
    assert canto[3] == 0
    # centro deve estar opaco (dentro do círculo)
    centro = resultado.getpixel((diametro_px // 2, diametro_px // 2))
    assert centro[3] > 200
