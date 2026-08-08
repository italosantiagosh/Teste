from PIL import Image

from catalogo import Catalogo


def _criar_imagem_fake(caminho):
    Image.new("RGBA", (50, 50), (255, 0, 0, 255)).save(caminho)


def test_catalogo_escaneia_imagens_e_agrupa_modelos(tmp_path):
    pasta_imagens = tmp_path / "imagens"
    pasta_imagens.mkdir()
    _criar_imagem_fake(pasta_imagens / "sao_jose_modelo_1.png")
    _criar_imagem_fake(pasta_imagens / "sao_jose_modelo_7.png")
    _criar_imagem_fake(pasta_imagens / "carlo_acutis_modelo_1.png")
    (pasta_imagens / "desktop.ini").write_text("nao deve ser lido")

    catalogo = Catalogo(pasta_imagens, tmp_path / "config" / "nomes_exibicao.json")

    assert catalogo.existe_santo("sao_jose")
    assert catalogo.modelos_disponiveis("sao_jose") == ["1", "7"]
    assert catalogo.existe_modelo("sao_jose", "7")
    assert not catalogo.existe_modelo("sao_jose", "2")
    assert catalogo.existe_santo("carlo_acutis")
    assert not catalogo.existe_santo("desktop")


def test_nome_bonito_usa_apelido_salvo_ou_cai_para_titulo(tmp_path):
    pasta_imagens = tmp_path / "imagens"
    pasta_imagens.mkdir()
    _criar_imagem_fake(pasta_imagens / "sao_jose_modelo_1.png")

    caminho_nomes = tmp_path / "config" / "nomes_exibicao.json"
    caminho_nomes.parent.mkdir(parents=True)
    caminho_nomes.write_text('{"sao_jose": "São José"}', encoding="utf-8")

    catalogo = Catalogo(pasta_imagens, caminho_nomes)
    assert catalogo.nome_bonito("sao_jose") == "São José"
    assert catalogo.nome_bonito("santo_sem_apelido") == "Santo Sem Apelido"


def test_registrar_nome_novo_nao_sobrescreve_existente(tmp_path):
    catalogo = Catalogo(tmp_path / "imagens_inexistente", tmp_path / "nomes.json")
    catalogo.registrar_nome_novo_se_ausente("sao_jose", "São José")
    catalogo.registrar_nome_novo_se_ausente("sao_jose", "sao jose (digitado errado depois)")
    assert catalogo.nomes_exibicao["sao_jose"] == "São José"
