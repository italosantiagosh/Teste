from argparse import Namespace

from gerar_medalhas import PASTA_BASE, resolver_caminhos


def _argumentos(**overrides):
    base = dict(pedido=None, imagens=None, saida=None, nomes_exibicao=None)
    base.update(overrides)
    return Namespace(**base)


def test_resolver_caminhos_usa_padroes_do_projeto_quando_nada_e_informado():
    _, pasta_imagens, pasta_saida, caminho_nomes = resolver_caminhos(_argumentos())
    assert pasta_imagens == PASTA_BASE / "imagens"
    assert pasta_saida == PASTA_BASE / "saida"
    assert caminho_nomes == PASTA_BASE / "config" / "nomes_exibicao.json"


def test_resolver_caminhos_catalogo_de_nomes_segue_pasta_de_imagens_customizada():
    # regressão: um --imagens apontando pra fora do projeto não pode nunca
    # cair no config/nomes_exibicao.json real (já aconteceu durante os testes
    # manuais desta melhoria e poluiu o catálogo de verdade com lixo).
    _, pasta_imagens, _, caminho_nomes = resolver_caminhos(_argumentos(imagens="/tmp/outro_pedido/imagens"))
    assert pasta_imagens.name == "imagens"
    assert caminho_nomes != PASTA_BASE / "config" / "nomes_exibicao.json"
    assert str(caminho_nomes) == "/tmp/outro_pedido/config/nomes_exibicao.json"


def test_resolver_caminhos_nomes_exibicao_explicito_tem_prioridade():
    _, _, _, caminho_nomes = resolver_caminhos(
        _argumentos(imagens="/tmp/outro/imagens", nomes_exibicao="/tmp/nomes_customizado.json")
    )
    assert str(caminho_nomes) == "/tmp/nomes_customizado.json"
