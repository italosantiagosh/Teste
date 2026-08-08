# Gerador de folhas de medalhas

Programa para gerar as folhas A4 com os santos, prontas para colar no
Silhouette Studio por cima do gabarito de corte já calibrado. Substitui os
antigos `folha de 12mm.py` e `folha de 16mm.py` por um único programa que
lê **uma tabela só** com todos os tamanhos e gera as folhas de cada um
automaticamente.

## Como usar

1. Instale as bibliotecas:
   ```
   pip install -r requirements.txt
   ```
2. Coloque as imagens dos santos em `imagens/`, no padrão
   `{santo}_modelo_{numero}.png` (ex.: `sao_jose_modelo_1.png`,
   `carlo_acutis_modelo_2.png` — sem acento, espaço vira `_`).
3. Edite `pedidos/pedido.csv` (ou crie outro arquivo, `.csv` ou `.xlsx`)
   com as colunas:

   | santo | modelo | tamanho | quantidade |
   |---|---|---|---|
   | São José | 1 | 16 | 155 |
   | Carlo Acutis | 2 | 12 | 30 |

   Um único arquivo pode misturar 12mm e 16mm à vontade — o programa separa
   automaticamente e gera as folhas de cada tamanho.
4. Rode:
   ```
   python gerar_medalhas.py
   ```
   Isso lê `pedidos/pedido.csv`, gera as folhas em `saida/12mm/` e
   `saida/16mm/` e abre os PNGs gerados.

Outras opções (`python gerar_medalhas.py --help`):

- `python gerar_medalhas.py caminho/outro_pedido.xlsx` — usa outro arquivo de pedido.
- `--dpi 2400` — resolução de saída (padrão: 1200, priorizando a melhor qualidade possível — o programa não se preocupa em manter o arquivo pequeno; folhas de 20-30MB são esperadas e não são um problema).
- `--pdf` — também salva cada folha em PDF, além do PNG (veja a pergunta 1 abaixo).
- `--sem-confirmar` — não pergunta nada; nomes que não baterem exatamente viram erro na lista, em vez de sugestão interativa. Útil pra rodar sem alguém acompanhando o terminal.
- `--nao-abrir` — não abre os arquivos automaticamente ao final.

## Respostas às melhorias pedidas

**1) PNG é mesmo o melhor formato para o fluxo com o Silhouette Studio?**
Sim, mantendo PNG faz sentido porque o gabarito de corte já é calibrado em
cima da posição exata dos círculos dessa grade — trocar para outro formato
não traria nenhuma vantagem e ainda arriscaria descalibrar o encaixe. O
único risco do PNG é o Silhouette Studio, às vezes, não respeitar o DPI
gravado no arquivo e importar a imagem em outra escala física, obrigando a
redimensionar manualmente para conferir com o gabarito. Por isso foi
adicionada a opção `--pdf`: o PDF grava o tamanho físico da página de forma
inequívoca (independente da resolução), então se em algum teste a
importação do PNG vier com o tamanho errado, o PDF é uma alternativa mais
confiável para o mesmo posicionamento.

**2) Melhor qualidade possível nas imagens**
Tamanho do arquivo não é um critério aqui — o programa prioriza qualidade
mesmo que isso signifique folhas de 20-30MB (ou mais) e um processamento
mais demorado:
- DPI padrão de 1200 (configurável, pode subir com `--dpi 2400` etc.).
- Antialiasing por *supersampling*: cada medalha é processada em 8x o
  tamanho final antes de aplicar a máscara circular e reduzir com Lanczos —
  a borda do círculo fica lisa, sem serrilhado (o mesmo truque que estava
  sendo testado em `montar_folha copy.py`, ampliado e ativo por padrão).
- Nitidez leve (`UnsharpMask`) depois da redução, pra compensar a suavização natural do redimensionamento.
- O único corte que o programa faz é "de graça": salvar a folha sem canal de transparência (a folha final é sempre 100% opaca, então isso não muda um pixel visível) e com compressão PNG sem perda — não é uma troca de qualidade por espaço, é só não desperdiçar espaço à toa. Veja a seção de avisos de resolução abaixo pra saber quando vale a pena subir o DPI de verdade.

**3) Gerar automaticamente mais de uma folha**
O programa soma a quantidade pedida de cada tamanho e divide pela
capacidade da folha (198 no 16mm, 360 no 12mm): quantas folhas cheias
couberem são geradas cheias com o pedido, e a última folha recebe o
restante do pedido + São José modelo 1 preenchendo o resto — exatamente o
exemplo dos 350 santos de 16mm (2 folhas cheias + uma terceira com o
restante e o preenchimento). O terminal mostra quantas folhas saíram e
quanto de cada uma é pedido real vs. preenchimento.

**4) O programa tenta reconhecer nomes parecidos**
Se o santo digitado não bater exatamente com nenhuma imagem em `imagens/`
(sem diferenciar acento/maiúscula), o programa procura o nome mais parecido
e pergunta, por exemplo:

```
'Sãu Jusé' não encontrado. Você quis dizer 'São José'? [S/n]
```

Aceitando (Enter ou "s"), a linha é corrigida automaticamente. Recusando,
ou se nada parecido for encontrado, a linha entra na lista de erros mostrada
ao final — sem travar o processamento das outras linhas. O mesmo vale pro
**modelo**: se o santo existe mas o modelo pedido não, o erro já lista quais
modelos existem pra aquele santo.

**5) Uma tabela só, com os dois tamanhos juntos**
`pedidos/pedido.csv` agora tem a coluna `tamanho` (12 ou 16). O programa lê
a tabela inteira uma vez, separa por tamanho e gera as folhas dos dois
tamanhos na mesma execução — sem precisar rodar dois scripts nem manter
duas tabelas.

## Correções depois do primeiro teste

**"Guido Schaffer" não foi reconhecido como "Guido"**
O algoritmo de semelhança de texto (usado para pegar erro de digitação tipo
"Sãu Jusé") mede o quão parecidas duas strings são de ponta a ponta — e
"guido_schaffer" x "guido" fica abaixo do limiar de confiança só por causa
da diferença de tamanho, mesmo sendo claramente o mesmo santo com um
sobrenome que não está cadastrado. Duas mudanças:

1. Antes de cair pro algoritmo de semelhança geral, o programa agora testa
   se algum santo cadastrado é um "prefixo" do que foi digitado (tira a
   última palavra, testa; tira mais uma, testa de novo...) — é isso que
   pega o caso do Guido.
2. Se mesmo assim nada for encontrado (ou a sugestão for recusada), em vez
   de simplesmente pular a linha, o programa agora **pede pra digitar o
   nome de novo** ali mesmo, na hora, em vez de só listar como erro no
   final. Só vira erro se você deixar em branco (desistir da linha) ou digitar 5 vezes sem achar.

**Prioridade é qualidade, não tamanho do arquivo**
Ajustado: tamanho de arquivo não é levado em conta em nenhuma decisão do
programa — DPI padrão voltou a 1200 e o antialiasing ficou mais pesado (8x
supersampling, em vez de 4x), então é esperado (e não é problema) folhas de
20-30MB pra cima, e o processamento de cada folha ficar mais lento
(dezenas de segundos, dependendo de quantos santos diferentes tem no
pedido — cada imagem única só é processada uma vez e fica em cache, então
o tempo cresce com a quantidade de **santos diferentes**, não com a
quantidade total de medalhas). O único corte que continua sendo feito é
descartar o canal de transparência ao salvar — isso não muda um único
pixel visível (a folha final é sempre 100% opaca), então não é uma troca
de qualidade por espaço, é só não gravar dado que não serve pra nada.

Uma ressalva que continua valendo mesmo priorizando qualidade: **o DPI só
ajuda até o ponto em que a imagem de origem tem resolução de verdade** —
depois disso o programa está esticando pixels por interpolação, sem
nenhum detalhe novo (só arquivo maior e mais demora à toa). Por isso, ao
final de cada tamanho, o programa avisa quando alguma arte de origem é
pequena demais para o DPI pedido:

```
Aviso: 2 imagem(ns) de origem estão em resolução baixa demais para 1200 DPI
neste tamanho — estão sendo esticadas, aumentar o DPI não vai deixá-las
mais nítidas:
    - Padre Cícero modelo 1: precisaria de ~2.3x mais resolução na imagem de origem
```

Se aparecer esse aviso pra algum santo, o ganho real de qualidade vem de
substituir a imagem de origem por uma versão maior — não de aumentar o
`--dpi`. Se não aparecer nenhum aviso, já está na melhor qualidade que a
arte permite; subir o DPI além disso só troca espaço em disco por nada.

## Outras melhorias incluídas

- **CSV ou Excel**: além de `.csv`, o pedido pode ser uma planilha `.xlsx` — útil se quiser usar validação de dados do Excel (lista suspensa de tamanho, por exemplo) pra reduzir erro de digitação na origem.
- **Leitura de CSV mais robusta**: tenta `utf-8`, `cp1252` e `latin1` nessa ordem, em vez de travar com erro de acentuação se o arquivo foi salvo em outra codificação.
- **Erros agrupados, não um por um**: o programa processa a tabela inteira e mostra todos os problemas encontrados de uma vez (linha, motivo), em vez de parar no primeiro santo com problema.
- **Catálogo de nomes bonitos** (`config/nomes_exibicao.json`): a pasta `imagens/` é a fonte da verdade sobre o que existe, mas os nomes de arquivo não têm acento. Esse arquivo guarda a grafia correta de cada santo pra aparecer certo nas mensagens ("São José", não "Sao Jose") — um santo novo funciona mesmo sem estar cadastrado aqui (aparece sem acento até alguém completar).
- **Relatório por folha**: cada execução mostra quantas folhas saíram por tamanho e quanto de cada folha é pedido real vs. preenchimento — fácil de conferir antes de imprimir.
- **Cross-platform**: abrir o arquivo gerado automaticamente agora funciona também fora do Windows (o script original usava `os.startfile`, que só existe no Windows).

## Estrutura

```
gerador_medalhas/
  gerar_medalhas.py    # ponto de entrada (CLI)
  config_folhas.py     # grade/margens de cada tamanho de medalha
  catalogo.py           # o que existe em imagens/ + nomes de exibição
  normalizacao.py       # normalizar nome e sugerir correspondência parecida
  pedido.py             # ler e validar a tabela de pedido
  imagens.py             # recorte circular + antialiasing + cache
  folha.py               # paginação e montagem das folhas A4
  imagens/                # arte dos santos (não versionado)
  pedidos/pedido.csv       # exemplo (o pedido real de 12mm + 16mm já migrado pra cá)
  saida/                    # folhas geradas (não versionado)
  testes/                    # testes automatizados (pytest)
```

## Rodando os testes

```
pip install pytest
python -m pytest testes/
```
