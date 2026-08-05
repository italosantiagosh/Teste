"""
Etapa 9 — Preparação e envio da mensagem de texto pelo WhatsApp Web.

Sem anexo de imagem — apenas texto (ver `mensagem.py`).

AINDA NÃO IMPLEMENTADO. Preciso confirmar:
  - abrir a conversa via URL (https://wa.me/<numero>) e Selenium, ou via
    busca dentro do WhatsApp Web?
  - o envio deve aguardar a página carregar completamente antes de digitar?

Requisitos de segurança já definidos:
  - nunca enviar automaticamente sem confirmação explícita no terminal;
  - mostrar prévia da mensagem antes de perguntar;
  - se o número não estiver cadastrado em config/clientes.json, avisar e
    não tentar enviar;
  - logar cliente, horário e status do envio — nunca logar senha/token.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("automacao_transportadora")


def preparar_e_enviar_mensagem(numero_whatsapp: str, texto_mensagem: str) -> bool:
    """Abre a conversa do cliente, preenche a mensagem, mostra prévia no
    terminal e só envia mediante confirmação explícita do usuário.

    Returns:
        True se a mensagem foi enviada, False se o usuário cancelou.

    Placeholder — implementação real depende de decisão sobre abertura
    da conversa (wa.me vs. busca) e de testes no ambiente do usuário.
    """
    raise NotImplementedError("Etapa 9 será desenvolvida por último, após Etapa 8.")
