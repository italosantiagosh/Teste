"""Preparação semiautomática de mensagens no WhatsApp Web."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote
import webbrowser

logger = logging.getLogger("automacao_transportadora")


def normalizar_telefone(numero: str, ddi_padrao: str = "55") -> str:
    digitos = re.sub(r"\D", "", str(numero))
    if not digitos:
        raise ValueError("Telefone vazio.")
    if len(digitos) in {10, 11}:
        digitos = ddi_padrao + digitos
    if not (12 <= len(digitos) <= 13):
        raise ValueError("Telefone inválido. Informe DDI, DDD e número.")
    return digitos


def montar_link(numero_whatsapp: str, texto_mensagem: str) -> str:
    """Monta o link do WhatsApp Web com o número e o texto já preenchidos.

    Levanta ValueError (via `normalizar_telefone`) se o telefone for
    vazio/inválido — nunca gera um link com número quebrado.
    """
    numero = normalizar_telefone(numero_whatsapp)
    return f"https://web.whatsapp.com/send?phone={numero}&text={quote(texto_mensagem)}"


def abrir_conversa(numero_whatsapp: str, texto_mensagem: str) -> bool:
    numero = normalizar_telefone(numero_whatsapp)
    url = montar_link(numero, texto_mensagem)
    aberto = webbrowser.open(url, new=2)
    logger.info("Conversa preparada no WhatsApp Web para telefone final %s.", numero[-4:])
    return bool(aberto)


def preparar_e_enviar_mensagem(numero_whatsapp: str, texto_mensagem: str) -> bool:
    print("\nPRÉVIA DA MENSAGEM\n" + "=" * 60)
    print(texto_mensagem)
    print("=" * 60)
    confirmar = input("Abrir esta mensagem no WhatsApp Web? (s/n): ").strip().lower()
    if confirmar != "s":
        print("Operação cancelada.")
        return False
    abrir_conversa(numero_whatsapp, texto_mensagem)
    print("Conversa aberta com o texto preenchido. Confira e envie manualmente.")
    return True
