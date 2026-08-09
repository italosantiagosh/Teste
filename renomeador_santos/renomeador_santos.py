"""
Renomeador de imagens de santos.

Abre uma janela que mostra, uma por uma, todas as imagens de uma pasta.
Você digita o nome do santo e ele:

  - normaliza o texto digitado (sem acento, minúsculo, espaços viram "_");
  - garante o padrão "<nome>_modelo_<numero>" (ex.: digitar "São José 1"
    salva como "sao_jose_modelo_1.png"; sem número, usa modelo 1);
  - converte a imagem para PNG, não importa o formato original;
  - salva numa pasta nova "renomeadas" dentro da pasta escolhida, sem
    mexer nos arquivos originais.

Uso: rode este arquivo (python renomeador_santos.py) e escolha a pasta
com as imagens quando a janela pedir.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    print("Falta instalar a biblioteca Pillow antes de rodar o programa.")
    print("Abra um terminal nesta pasta e rode: pip install -r requirements.txt")
    sys.exit(1)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
TAMANHO_PREVIEW = (480, 480)


def normalizar_nome(texto: str) -> str | None:
    """Normaliza o texto digitado para o padrão `nome_modelo_numero`.

    - Remove acentos e deixa tudo minúsculo.
    - Troca qualquer sequência de caracteres que não seja letra/número por "_".
    - Se o texto terminar em número (ex.: "São José 1"), esse número vira o
      modelo: "sao_jose_modelo_1". Sem número no final, usa modelo 1
      automaticamente.
    - Se "modelo" já tiver sido digitado (ex.: "São José modelo 2"), não
      duplica a palavra.

    Retorna None se não sobrar nada aproveitável (texto vazio ou só símbolos).
    """
    texto = (texto or "").strip()
    if not texto:
        return None

    match_numero = re.search(r"(\d+)\s*$", texto)
    if match_numero:
        numero = match_numero.group(1)
        base = texto[: match_numero.start()]
    else:
        numero = "1"
        base = texto

    base_sem_acento = unicodedata.normalize("NFKD", base)
    base_sem_acento = "".join(c for c in base_sem_acento if not unicodedata.combining(c))

    base_normalizada = re.sub(r"[^a-zA-Z0-9]+", "_", base_sem_acento).strip("_").lower()
    base_normalizada = re.sub(r"(_modelo)+$", "", base_normalizada)

    if not base_normalizada:
        return None

    return f"{base_normalizada}_modelo_{numero}"


def _converter_para_modo_salvavel(imagem: Image.Image) -> Image.Image:
    """Garante um modo de cor que o PNG aceita, preservando transparência
    quando ela existir no arquivo original."""
    if imagem.mode in ("RGB", "RGBA"):
        return imagem
    if imagem.mode in ("P", "LA", "PA") and (
        "transparency" in imagem.info or imagem.mode in ("LA", "PA")
    ):
        return imagem.convert("RGBA")
    return imagem.convert("RGB")


class JanelaRenomeador:
    def __init__(self, pasta_saida: Path, arquivos: list[Path]) -> None:
        self.pasta_saida = pasta_saida
        self.arquivos = arquivos
        self.indice = 0
        # Nomes já usados na pasta de saída (inclui execuções anteriores,
        # caso o programa tenha sido fechado e reaberto no meio do processo).
        self.nomes_usados: set[str] = {p.stem.lower() for p in pasta_saida.glob("*.png")}

        self.root = tk.Tk()
        self.root.title("Renomeador de Imagens de Santos")
        self.root.geometry("620x680")

        self.rotulo_progresso = ttk.Label(self.root, padding=10, font=("", 11, "bold"))
        self.rotulo_progresso.pack(side=tk.TOP)

        self.rotulo_imagem = ttk.Label(self.root)
        self.rotulo_imagem.pack(side=tk.TOP, padx=10, pady=10)

        self.rotulo_arquivo = ttk.Label(self.root, foreground="gray")
        self.rotulo_arquivo.pack(side=tk.TOP)

        quadro_entrada = ttk.Frame(self.root, padding=10)
        quadro_entrada.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(quadro_entrada, text="Nome:").pack(side=tk.LEFT)
        self.campo_nome = ttk.Entry(quadro_entrada)
        self.campo_nome.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.campo_nome.bind("<Return>", lambda evento: self._salvar_e_avancar())
        self.campo_nome.bind("<KeyRelease>", self._atualizar_preview_nome)

        self.rotulo_preview_nome = ttk.Label(self.root, foreground="blue")
        self.rotulo_preview_nome.pack(side=tk.TOP)

        self.rotulo_aviso = ttk.Label(self.root, foreground="red", wraplength=580)
        self.rotulo_aviso.pack(side=tk.TOP, pady=(5, 0))

        quadro_botoes = ttk.Frame(self.root, padding=10)
        quadro_botoes.pack(side=tk.BOTTOM, pady=10)
        ttk.Button(quadro_botoes, text="Pular >", command=self._pular).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            quadro_botoes, text="Salvar e próxima (Enter)", command=self._salvar_e_avancar
        ).pack(side=tk.LEFT, padx=5)

        self._imagem_tk: ImageTk.PhotoImage | None = None  # evita coleta de lixo prematura
        self._mostrar_imagem_atual()
        self.campo_nome.focus_set()

    def _mostrar_imagem_atual(self) -> None:
        if self.indice >= len(self.arquivos):
            self._finalizar()
            return

        caminho = self.arquivos[self.indice]
        self.rotulo_progresso.configure(text=f"Imagem {self.indice + 1} de {len(self.arquivos)}")
        self.rotulo_arquivo.configure(text=caminho.name)
        self.rotulo_aviso.configure(text="")
        self.rotulo_preview_nome.configure(text="")
        self.campo_nome.delete(0, tk.END)

        try:
            with Image.open(caminho) as imagem_original:
                imagem_preview = imagem_original.copy()
            imagem_preview.thumbnail(TAMANHO_PREVIEW)
            self._imagem_tk = ImageTk.PhotoImage(imagem_preview)
            self.rotulo_imagem.configure(image=self._imagem_tk, text="")
        except Exception as e:
            self._imagem_tk = None
            self.rotulo_imagem.configure(image="", text="(não foi possível abrir esta imagem)")
            self.rotulo_aviso.configure(text=f"Erro ao abrir '{caminho.name}': {e}")

        self.campo_nome.focus_set()

    def _atualizar_preview_nome(self, evento=None) -> None:
        nome = normalizar_nome(self.campo_nome.get())
        self.rotulo_preview_nome.configure(text=f"Vai salvar como: {nome}.png" if nome else "")

    def _salvar_e_avancar(self) -> None:
        if self.indice >= len(self.arquivos):
            return

        nome_normalizado = normalizar_nome(self.campo_nome.get())
        if not nome_normalizado:
            # Enter sem digitar nada = mesma coisa que "Pular": ignora esta
            # imagem e não copia nada, sem avisar (é o caminho rápido para
            # descartar imagens que não interessam).
            self._pular()
            return

        if nome_normalizado.lower() in self.nomes_usados:
            self.rotulo_aviso.configure(
                text=f"Já existe uma imagem salva como '{nome_normalizado}'. "
                "Digite outro nome ou ajuste o número."
            )
            return

        caminho_origem = self.arquivos[self.indice]
        caminho_destino = self.pasta_saida / f"{nome_normalizado}.png"

        try:
            with Image.open(caminho_origem) as imagem:
                imagem_convertida = _converter_para_modo_salvavel(imagem)
                imagem_convertida.save(caminho_destino, "PNG")
        except Exception as e:
            messagebox.showerror(
                "Erro ao salvar", f"Não foi possível salvar '{caminho_origem.name}':\n{e}"
            )
            return

        self.nomes_usados.add(nome_normalizado.lower())
        self.indice += 1
        self._mostrar_imagem_atual()

    def _pular(self) -> None:
        self.indice += 1
        self._mostrar_imagem_atual()

    def _finalizar(self) -> None:
        messagebox.showinfo(
            "Concluído",
            f"Todas as {len(self.arquivos)} imagens foram processadas.\n\n"
            f"Salvas em: {self.pasta_saida}",
        )
        self.root.destroy()

    def rodar(self) -> None:
        self.root.mainloop()


def main() -> None:
    raiz = tk.Tk()
    raiz.withdraw()

    pasta_str = filedialog.askdirectory(title="Escolha a pasta com as imagens dos santos")
    if not pasta_str:
        raiz.destroy()
        return

    pasta_entrada = Path(pasta_str)
    arquivos = sorted(
        p for p in pasta_entrada.iterdir() if p.is_file() and p.suffix.lower() in EXTENSOES_IMAGEM
    )

    if not arquivos:
        messagebox.showwarning(
            "Nenhuma imagem encontrada",
            "Não encontrei nenhuma imagem (.png, .jpg, .jpeg, .bmp, .gif, .tif, .webp) em:\n"
            f"{pasta_entrada}",
        )
        raiz.destroy()
        return

    pasta_saida = pasta_entrada / "renomeadas"
    pasta_saida.mkdir(exist_ok=True)

    raiz.destroy()

    JanelaRenomeador(pasta_saida, arquivos).rodar()


if __name__ == "__main__":
    main()
