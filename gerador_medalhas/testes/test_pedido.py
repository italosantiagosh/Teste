import pandas as pd
from PIL import Image

from catalogo import Catalogo
from pedido import expandir_por_tamanho, resolver_pedido


def _catalogo_com_santos(tmp_path, santos_modelos):
    pasta_imagens = tmp_path / "imagens"
    pasta_imagens.mkdir()
    for chave_santo, modelo in santos_modelos:
        Image.new("RGBA", (10, 10)).save(pasta_imagens / f"{chave_santo}_modelo_{modelo}.png")
    return Catalogo(pasta_imagens, tmp_path / "nomes.json")


def test_resolver_pedido_aceita_nome_exato(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "São José", "modelo": "1", "tamanho": "16mm", "quantidade": 3}])

    itens, erros = resolver_pedido(tabela, catalogo, perguntar_confirmacao=None)

    assert erros == []
    assert itens == [{"chave_santo": "sao_jose", "modelo": "1", "chave_tamanho": "16", "quantidade": 3}]


def test_resolver_pedido_corrige_typo_quando_confirmado(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "Sãu Jusé", "modelo": "1", "tamanho": "16", "quantidade": 1}])

    itens, erros = resolver_pedido(tabela, catalogo, perguntar_confirmacao=lambda msg: True)

    assert erros == []
    assert itens[0]["chave_santo"] == "sao_jose"


def test_resolver_pedido_recusa_correcao_vira_erro(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "Sãu Jusé", "modelo": "1", "tamanho": "16", "quantidade": 1}])

    itens, erros = resolver_pedido(tabela, catalogo, perguntar_confirmacao=lambda msg: False)

    assert itens == []
    assert len(erros) == 1
    assert "não encontrado" in erros[0]


def test_resolver_pedido_sem_confirmacao_nao_corrige_sozinho(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "Sãu Jusé", "modelo": "1", "tamanho": "16", "quantidade": 1}])

    itens, erros = resolver_pedido(tabela, catalogo, perguntar_confirmacao=None)

    assert itens == []
    assert len(erros) == 1


def test_resolver_pedido_modelo_inexistente_vira_erro_com_sugestoes(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1"), ("sao_jose", "2")])
    tabela = pd.DataFrame([{"santo": "São José", "modelo": "9", "tamanho": "16", "quantidade": 1}])

    itens, erros = resolver_pedido(tabela, catalogo, perguntar_confirmacao=None)

    assert itens == []
    assert "modelo '9' não existe" in erros[0]
    assert "1, 2" in erros[0]


def test_resolver_pedido_tamanho_invalido_vira_erro(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "São José", "modelo": "1", "tamanho": "20", "quantidade": 1}])

    itens, erros = resolver_pedido(tabela, catalogo, perguntar_confirmacao=None)

    assert itens == []
    assert "não reconhecido" in erros[0]


def test_resolver_pedido_ignora_linha_com_quantidade_zero(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "São José", "modelo": "1", "tamanho": "16", "quantidade": 0}])

    itens, erros = resolver_pedido(tabela, catalogo, perguntar_confirmacao=None)

    assert itens == []
    assert erros == []


def test_resolver_pedido_sugere_por_prefixo_quando_ha_sobrenome_extra(tmp_path):
    # reproduz o bug relatado: 'guido schaffer' não é achado por semelhança
    # de texto pura, mas 'guido' é um prefixo válido do catálogo.
    catalogo = _catalogo_com_santos(tmp_path, [("guido", "1")])
    tabela = pd.DataFrame([{"santo": "guido schaffer", "modelo": "1", "tamanho": "16", "quantidade": 2}])

    perguntas = []

    def perguntar(mensagem):
        perguntas.append(mensagem)
        return True

    itens, erros = resolver_pedido(tabela, catalogo, perguntar_confirmacao=perguntar)

    assert erros == []
    assert itens[0]["chave_santo"] == "guido"
    assert len(perguntas) == 1
    assert "Você quis dizer 'guido'" in perguntas[0] or "guido" in perguntas[0]


def test_resolver_pedido_pede_para_digitar_de_novo_quando_nao_encontra_nada(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "santo totalmente desconhecido", "modelo": "1", "tamanho": "16", "quantidade": 1}])

    textos_pedidos = iter(["São José"])

    itens, erros = resolver_pedido(
        tabela,
        catalogo,
        perguntar_confirmacao=lambda msg: False,
        pedir_texto=lambda msg: next(textos_pedidos),
    )

    assert erros == []
    assert itens[0]["chave_santo"] == "sao_jose"


def test_resolver_pedido_digitar_em_branco_desiste_da_linha(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "santo totalmente desconhecido", "modelo": "1", "tamanho": "16", "quantidade": 1}])

    itens, erros = resolver_pedido(
        tabela,
        catalogo,
        perguntar_confirmacao=lambda msg: False,
        pedir_texto=lambda msg: "",
    )

    assert itens == []
    assert len(erros) == 1
    assert "não encontrado" in erros[0]


def test_resolver_pedido_desiste_apos_muitas_tentativas_de_digitacao(tmp_path):
    catalogo = _catalogo_com_santos(tmp_path, [("sao_jose", "1")])
    tabela = pd.DataFrame([{"santo": "x", "modelo": "1", "tamanho": "16", "quantidade": 1}])

    chamadas = {"n": 0}

    def pedir_texto_sempre_errado(mensagem):
        chamadas["n"] += 1
        return "ainda errado"

    itens, erros = resolver_pedido(
        tabela,
        catalogo,
        perguntar_confirmacao=lambda msg: False,
        pedir_texto=pedir_texto_sempre_errado,
    )

    assert itens == []
    assert len(erros) == 1
    assert chamadas["n"] <= 5  # não entra em loop infinito


def test_expandir_por_tamanho_repete_quantidade_e_agrupa():
    itens = [
        {"chave_santo": "sao_jose", "modelo": "1", "chave_tamanho": "16", "quantidade": 2},
        {"chave_santo": "carlo_acutis", "modelo": "1", "chave_tamanho": "16", "quantidade": 1},
        {"chave_santo": "sao_jose", "modelo": "1", "chave_tamanho": "12", "quantidade": 3},
    ]
    resultado = expandir_por_tamanho(itens)

    assert len(resultado["16"]) == 3
    assert resultado["16"][0] == {"chave_santo": "sao_jose", "modelo": "1"}
    assert resultado["16"][2] == {"chave_santo": "carlo_acutis", "modelo": "1"}
    assert len(resultado["12"]) == 3
