# Renomeador de Imagens de Santos

Programa simples para renomear rapidamente uma pasta cheia de imagens de
santos: ele mostra cada imagem numa janela, você digita o nome, e ele já
salva normalizado e convertido em PNG.

## O que ele faz

- Percorre uma pasta escolhida por você e mostra as imagens **uma por uma**.
- Você digita o nome (ex.: `São José 1`) e aperta **Enter** (ou o botão
  "Salvar e próxima").
- O nome é normalizado automaticamente:
  - sem acento e em minúsculo;
  - espaços e símbolos viram `_`;
  - o número no final vira o "modelo": `São José 1` → `sao_jose_modelo_1`;
  - se você não digitar número nenhum, ele usa `modelo_1` automaticamente
    (ex.: `São José` → `sao_jose_modelo_1`).
- Converte a imagem para **PNG**, não importa o formato original
  (jpg, jpeg, bmp, gif, tif, webp).
- Salva tudo numa pasta nova chamada `renomeadas`, criada dentro da pasta
  que você escolheu — **as imagens originais não são apagadas nem
  alteradas**.
- Se você digitar um nome que já foi usado (mesmo santo, mesmo número), ele
  avisa e não deixa salvar até você digitar outro nome ou outro número.
- Tem um botão "Pular" para deixar uma imagem sem renomear e ir para a
  próxima (útil pra imagens que você não quer aproveitar).

## Como rodar pela primeira vez

1. Abra um terminal **nesta pasta** (`renomeador_santos`).
2. Instale a biblioteca necessária:
   ```
   pip install -r requirements.txt
   ```
3. Rode:
   ```
   python renomeador_santos.py
   ```
4. Escolha a pasta com as imagens dos santos quando a janela pedir.

## Como gerar um executável (.exe), para não precisar abrir terminal

1. Nesta pasta, dê duplo clique em `build_exe.bat` (ou rode
   `build_exe.bat` num terminal). Isso instala as bibliotecas necessárias
   e gera `RenomeadorDeSantos.exe` **nesta mesma pasta**.
2. Depois de gerado, use direto o `.exe` — pode criar um atalho dele na
   Área de Trabalho. Ele funciona sozinho, não depende do resto desta
   pasta.

Gerar o `.exe` só funciona rodando `build_exe.bat` no Windows (o
PyInstaller empacota para o sistema operacional onde é executado).
