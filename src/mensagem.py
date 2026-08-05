"""
Etapa 8 — Montagem da MENSAGEM DE TEXTO com a posição das entregas do cliente.

Este módulo substitui o antigo plano de gerar uma imagem da tabela: em vez
disso, monta um texto formatado (usando o template de `config/clientes.json`
ou um template dedicado) com os dados de cada pedido do cliente — pedido,
cidade, status, motorista e previsão de entrega.

AINDA NÃO IMPLEMENTADO. Depende dos dados já cruzados e com previsão
calculada (Etapas 5 e 6) e da busca de cliente (Etapa 7).

Formato-alvo (a ajustar com você):

    Olá, [NOME DO CLIENTE]!

    Segue a posição atualizada das suas entregas em [DATA]:

    Pedido 1001 | Natal-RN | Em trânsito | Motorista: João | Previsão: 05/08/2026
    Pedido 1004 | Natal-RN | Coletado | Motorista: João | Previsão: 05/08/2026

    As previsões apresentadas são estimativas e podem sofrer alterações
    durante o transporte.

    Qualquer dúvida, estou à disposição.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("automacao_transportadora")


def montar_mensagem_cliente(
    nome_cliente: str,
    pedidos_cliente: pd.DataFrame,
    data_referencia: str,
) -> str:
    """Monta o texto da mensagem com os pedidos do cliente informado.

    Args:
        nome_cliente: nome do cliente (como cadastrado/encontrado).
        pedidos_cliente: DataFrame já filtrado apenas com os pedidos deste
            cliente (saída da Etapa 7), contendo pedido, cidade, status,
            motorista e previsão de entrega.
        data_referencia: data a exibir na mensagem (ex.: data de geração).

    Returns:
        Texto completo pronto para ser enviado pelo WhatsApp.

    Placeholder — aguardando confirmação do template exato e de quais
    campos devem (ou não) aparecer para o cliente.
    """
    raise NotImplementedError("Etapa 8 será desenvolvida após Etapas 5, 6 e 7.")
