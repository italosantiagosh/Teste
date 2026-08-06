"""Montagem de mensagens de texto com as cargas do cliente."""
from __future__ import annotations

from datetime import date, datetime
import logging

import pandas as pd

logger = logging.getLogger("automacao_transportadora")


def _valor(linha: pd.Series, *nomes: str, padrao: str = "NÃO INFORMADO") -> str:
    for nome in nomes:
        if nome in linha.index:
            valor = linha.get(nome)
            if pd.notna(valor) and str(valor).strip() and str(valor).lower() != "nan":
                return str(valor).strip()
    return padrao


def _formatar_data(valor: object) -> str:
    if valor is None or pd.isna(valor):
        return "NÃO DEFINIDA"
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto or texto.upper() == "PREVISÃO NÃO DEFINIDA":
            return "NÃO DEFINIDA"
        data = pd.to_datetime(texto, errors="coerce", dayfirst=True)
        return data.strftime("%d/%m/%Y") if pd.notna(data) else texto
    if isinstance(valor, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(valor).strftime("%d/%m/%Y")
    return str(valor)


def montar_mensagem_cliente(
    nome_cliente: str,
    pedidos_cliente: pd.DataFrame,
    data_referencia: str | None = None,
) -> str:
    if pedidos_cliente.empty:
        raise ValueError("Não há cargas para o cliente selecionado.")

    data_referencia = data_referencia or date.today().strftime("%d/%m/%Y")
    linhas: list[str] = []

    for _, pedido in pedidos_cliente.iterrows():
        numero = _valor(pedido, "pedido", "CTRC")
        cidade = _valor(pedido, "cidade", "destino")
        status = _valor(pedido, "status", "situacao_mdfe")
        motorista = _valor(pedido, "motorista", padrao="NÃO INFORMADO")
        previsao_bruta = None
        for coluna in ("previsao_entrega_calculada", "previsao_entrega", "prev_chegada"):
            if coluna in pedido.index and pd.notna(pedido.get(coluna)):
                previsao_bruta = pedido.get(coluna)
                break
        previsao = _formatar_data(previsao_bruta)

        linhas.append(
            f"• Carga {numero} | Destino: {cidade} | "
            f"Status: {status} | Motorista: {motorista} | Previsão: {previsao}"
        )

    return "\n".join(
        [
            f"Olá, {nome_cliente}!",
            "",
            f"Segue a posição atualizada das suas cargas em {data_referencia}:",
            "",
            *linhas,
            "",
            "As previsões são estimativas e podem sofrer alterações durante o transporte.",
            "",
            "Qualquer dúvida, estou à disposição.",
        ]
    )


def dividir_mensagem(texto: str, limite: int = 3500) -> list[str]:
    if len(texto) <= limite:
        return [texto]
    blocos: list[str] = []
    atual: list[str] = []
    tamanho = 0
    for linha in texto.splitlines():
        adicional = len(linha) + 1
        if atual and tamanho + adicional > limite:
            blocos.append("\n".join(atual))
            atual = []
            tamanho = 0
        atual.append(linha)
        tamanho += adicional
    if atual:
        blocos.append("\n".join(atual))
    total = len(blocos)
    return [f"Mensagem {i}/{total}\n\n{bloco}" for i, bloco in enumerate(blocos, 1)]
