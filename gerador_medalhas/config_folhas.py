"""Configuração das folhas de medalha por tamanho.

Cada tamanho de medalha tem sua própria grade (linhas x colunas) e margens,
calibradas para bater com o gabarito de corte já usado no Silhouette Studio.
Se um dia o gabarito físico mudar, é só ajustar os números aqui — nada mais
no programa depende de valores fixos de posição.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigTamanho:
    chave: str  # como aparece na coluna "tamanho" da tabela de pedido (ex.: "16")
    nome_exibicao: str  # ex.: "16mm"
    diametro_mm: float
    linhas: int
    colunas: int
    margem_esquerda_mm: float
    margem_superior_mm: float
    passo_horizontal_mm: float
    passo_vertical_mm: float
    # em grades "hexagonais" (linhas alternadas deslocadas), como as duas
    # folhas originais. Se a folha não tiver esse padrão, deixar 0.
    deslocamento_horizontal_mm: float = 0.0

    @property
    def capacidade_por_folha(self) -> int:
        return self.linhas * self.colunas


LARGURA_FOLHA_MM = 210.0  # A4
ALTURA_FOLHA_MM = 297.0

# Filler padrão: quando sobra espaço numa folha, ela é completada com este santo.
SANTO_PREENCHIMENTO_PADRAO = "São José"
MODELO_PREENCHIMENTO_PADRAO = "1"

CONFIGS_TAMANHO = {
    "12": ConfigTamanho(
        chave="12",
        nome_exibicao="12mm",
        diametro_mm=12,
        linhas=24,
        colunas=15,
        margem_esquerda_mm=10.19,
        margem_superior_mm=12.09,
        passo_horizontal_mm=12.25,
        passo_vertical_mm=10.63,
        deslocamento_horizontal_mm=12.25 / 2,
    ),
    "16": ConfigTamanho(
        chave="16",
        nome_exibicao="16mm",
        diametro_mm=16,
        linhas=18,
        colunas=11,
        margem_esquerda_mm=11.69,
        margem_superior_mm=15.76,
        passo_horizontal_mm=16.25,
        passo_vertical_mm=14.112,
        deslocamento_horizontal_mm=16.25 / 2,
    ),
}


def normalizar_chave_tamanho(texto: str) -> str:
    """Aceita '16', '16mm', '16 mm' etc. e devolve a chave usada em CONFIGS_TAMANHO."""
    chave = str(texto).strip().lower().replace("mm", "").replace(" ", "")
    return chave


def obter_config_tamanho(texto: str) -> ConfigTamanho:
    chave = normalizar_chave_tamanho(texto)
    if chave not in CONFIGS_TAMANHO:
        tamanhos_validos = ", ".join(sorted(CONFIGS_TAMANHO))
        raise ValueError(
            f"Tamanho '{texto}' não reconhecido. Tamanhos configurados: {tamanhos_validos}."
        )
    return CONFIGS_TAMANHO[chave]
