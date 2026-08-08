"""Preparo das imagens circulares dos santos (recorte, máscara, qualidade)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from normalizacao import normalizar_nome

# Quantas vezes maior que o tamanho final a imagem é processada antes de
# reduzir. Suaviza a borda do círculo (evita serrilhado) — o mesmo truque
# testado em "montar_folha copy.py", só que como opção reaproveitável.
FATOR_SUPERAMOSTRAGEM = 4


class ImagemNaoEncontrada(FileNotFoundError):
    pass


def localizar_imagem(pasta_imagens: Path, chave_santo: str, modelo: str) -> Path:
    caminho = Path(pasta_imagens) / f"{normalizar_nome(chave_santo)}_modelo_{modelo}.png"
    if not caminho.exists():
        raise ImagemNaoEncontrada(f"Imagem não encontrada: {caminho}")
    return caminho


def preparar_medalha_circular(
    caminho_imagem: Path, diametro_px: int, aplicar_nitidez: bool = True
) -> Image.Image:
    """Abre a imagem, recorta um quadrado central (cover) e aplica máscara
    circular com antialiasing por supersampling, na melhor qualidade que o
    Pillow permite (Lanczos nas duas reamostragens)."""
    imagem = Image.open(caminho_imagem).convert("RGBA")

    largura, altura = imagem.size
    lado = min(largura, altura)
    esquerda = (largura - lado) // 2
    topo = (altura - lado) // 2
    imagem = imagem.crop((esquerda, topo, esquerda + lado, topo + lado))

    tamanho_grande = diametro_px * FATOR_SUPERAMOSTRAGEM
    imagem = imagem.resize((tamanho_grande, tamanho_grande), Image.Resampling.LANCZOS)

    mascara = Image.new("L", (tamanho_grande, tamanho_grande), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, tamanho_grande - 1, tamanho_grande - 1), fill=255)

    resultado = Image.new("RGBA", (tamanho_grande, tamanho_grande), (255, 255, 255, 0))
    resultado.paste(imagem, (0, 0), mascara)

    resultado = resultado.resize((diametro_px, diametro_px), Image.Resampling.LANCZOS)
    if aplicar_nitidez:
        resultado = resultado.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    return resultado


class CacheMedalhas:
    """Evita reprocessar a mesma combinação santo+modelo+tamanho várias vezes."""

    def __init__(self, pasta_imagens: Path, diametro_px: int):
        self.pasta_imagens = Path(pasta_imagens)
        self.diametro_px = diametro_px
        self._cache: dict[tuple[str, str], Image.Image] = {}

    def obter(self, chave_santo: str, modelo: str) -> Image.Image:
        chave = (chave_santo, modelo)
        if chave not in self._cache:
            caminho = localizar_imagem(self.pasta_imagens, chave_santo, modelo)
            self._cache[chave] = preparar_medalha_circular(caminho, self.diametro_px)
        return self._cache[chave]
