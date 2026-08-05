# Automação Transportadora

Automação para apoiar o trabalho semanal de um vendedor de transportadora:
baixar relatório de entregas, cruzar com a tabela de motoristas, calcular
previsão de entrega e preparar o envio de uma **mensagem de texto** (sem
imagem) pelo WhatsApp Web com a posição das entregas de cada cliente.

## Status do desenvolvimento

O projeto é construído em etapas, testando cada módulo isoladamente antes
de avançar. Nenhuma etapa depende de acesso ao sistema real da
transportadora até que o módulo correspondente seja explicitamente
validado pelo usuário.

| Etapa | Módulo | Status |
|---|---|---|
| 1 | Configuração | ✅ estrutura inicial criada, com nomes reais das colunas do SSW |
| 2 | Acesso ao sistema / download | ✅ implementado (login, navegação por opção, geração, fila e download), com o parsing da fila testado com dados reais |
| 3 | Tratamento da planilha principal | ✅ implementado e testado com o relatório real (681 pedidos) |
| 4 | Captura da tabela de motoristas | ✅ implementado e testado com HTML real (46 registros, tabela sem paginação) |
| 5 | Cruzamento dos dados | ✅ implementado e testado (com_motorista, sem_motorista, motoristas_sem_pedido, conflitos) |
| 6 | Previsão de entrega | ✅ implementado: 5 dias corridos se embarcado, 7 se não, a partir da data de emissão |
| 7 | Pesquisa de clientes | ⏳ ainda não iniciado — será só por nome (relatório não tem CNPJ) |
| 8 | Mensagem de texto (substitui a imagem) | ⏳ ainda não iniciado |
| 9 | Envio pelo WhatsApp Web | ⏳ ainda não iniciado |
| 10 | Fluxo principal (`main.py`) | ⏳ esqueleto de menu criado |

## Mudança em relação ao plano original

O plano original previa gerar uma **imagem** com a tabela de pedidos do
cliente. Isso foi substituído por uma **mensagem de texto** contendo os
dados da carga (pedido, cidade, status, motorista, previsão de entrega),
formatada a partir de um template configurável. Por isso:

- o módulo `gerar_imagem.py` foi removido do plano;
- as bibliotecas de imagem (Pillow/matplotlib/HTML→imagem) deixam de ser
  necessárias;
- o módulo `clientes.py` passa a ser responsável por montar o texto da
  mensagem (função a ser criada na Etapa 8), e `whatsapp.py` apenas abre
  a conversa e envia o texto — não há mais anexo de imagem.

## Como rodar pela primeira vez

1. Abra um terminal **na pasta do projeto** (não precisa ser pelo botão ▶/F5 do VS Code — de preferência use o terminal integrado: menu "Terminal" → "New Terminal").
2. Instale as bibliotecas necessárias:
   ```
   pip install -r requirements.txt
   ```
3. Copie o arquivo `.env.example` para `.env` (mesma pasta) e preencha com os dados reais (URL do sistema, usuário, unidade etc.). Sem isso, as opções que acessam o sistema (1, 2, 6) não funcionam — mas a opção 3 (tratar planilha) funciona sem `.env`.
4. Rode:
   ```
   python main.py
   ```

Se faltar alguma biblioteca, o programa agora avisa exatamente qual instalar em vez de travar com um erro técnico. Se acontecer outro erro, ele mostra o motivo direto no terminal (e também salva o detalhe completo em `logs/automacao.log`).

## Como rodar os testes do módulo já implementado

Veja `testes/test_tratamento_planilha.py`. Instruções detalhadas na seção
"Como testar" da resposta que acompanha este projeto.
