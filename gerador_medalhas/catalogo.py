"""Catálogo de santos disponíveis, construído a partir dos arquivos em imagens/.

A pasta imagens/ é sempre a fonte da verdade sobre o que existe (é o que o
programa consegue realmente desenhar). Arquivos precisam seguir o padrão:

    {nome_do_santo}_modelo_{modelo}.png

com nome_do_santo já no formato normalizado (sem acento, minúsculo,
espaços viram "_"). Ex.: sao_jose_modelo_1.png, carlo_acutis_modelo_2.png

Como o nome normalizado perde acentuação (só serve pra comparar), um
arquivo à parte (config/nomes_exibicao.json) guarda a grafia bonita de
cada santo para mostrar nas mensagens e relatórios. Um santo novo que
ainda não está nesse arquivo continua funcionando normalmente — só
aparece com o nome "cru" (sem acento) até alguém completar o apelido.
"""

import json
import re
from pathlib import Path

from normalizacao import normalizar_nome

PADRAO_ARQUIVO = re.compile(r"^(.*)_modelo_([^.]+)\.png$", re.IGNORECASE)


class Catalogo:
    def __init__(self, pasta_imagens: Path, caminho_nomes_exibicao: Path):
        self.pasta_imagens = Path(pasta_imagens)
        self.caminho_nomes_exibicao = Path(caminho_nomes_exibicao)
        # chave_normalizada -> {modelo1, modelo2, ...}
        self.modelos_por_santo: dict[str, set[str]] = {}
        self.nomes_exibicao: dict[str, str] = {}
        self._escanear_imagens()
        self._carregar_nomes_exibicao()

    def _escanear_imagens(self):
        if not self.pasta_imagens.exists():
            return
        for arquivo in self.pasta_imagens.glob("*.png"):
            correspondencia = PADRAO_ARQUIVO.match(arquivo.name)
            if not correspondencia:
                continue
            chave_santo, modelo = correspondencia.groups()
            chave_santo = normalizar_nome(chave_santo)
            self.modelos_por_santo.setdefault(chave_santo, set()).add(modelo.strip())

    def _carregar_nomes_exibicao(self):
        if self.caminho_nomes_exibicao.exists():
            with open(self.caminho_nomes_exibicao, encoding="utf-8") as arquivo:
                self.nomes_exibicao = json.load(arquivo)

    def salvar_nomes_exibicao(self):
        self.caminho_nomes_exibicao.parent.mkdir(parents=True, exist_ok=True)
        with open(self.caminho_nomes_exibicao, "w", encoding="utf-8") as arquivo:
            json.dump(self.nomes_exibicao, arquivo, ensure_ascii=False, indent=2, sort_keys=True)

    def nome_bonito(self, chave_santo: str) -> str:
        if chave_santo in self.nomes_exibicao:
            return self.nomes_exibicao[chave_santo]
        # fallback: reconstrói algo legível a partir da chave normalizada
        return chave_santo.replace("_", " ").title()

    def existe_santo(self, chave_santo: str) -> bool:
        return chave_santo in self.modelos_por_santo

    def existe_modelo(self, chave_santo: str, modelo: str) -> bool:
        return modelo in self.modelos_por_santo.get(chave_santo, set())

    def modelos_disponiveis(self, chave_santo: str):
        return sorted(self.modelos_por_santo.get(chave_santo, set()))

    def chaves_santos(self):
        return list(self.modelos_por_santo.keys())

    def registrar_nome_novo_se_ausente(self, chave_santo: str, nome_como_digitado: str):
        """Se o santo ainda não tem apelido bonito salvo, usa a primeira grafia
        vista para ele (preserva acentos do jeito que o usuário digitou)."""
        if chave_santo not in self.nomes_exibicao:
            self.nomes_exibicao[chave_santo] = str(nome_como_digitado).strip()
