"""Montagem de mensagens de texto com a posição de cargas, no formato de
tabela usado manualmente antes (Remetente/Pagador/Cidade/NF/Peso/Vol/Vr
Frete/Motorista/Situação), podendo juntar mais de um cliente na mesma
mensagem.
"""
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


def _formatar_numero_br(valor: object) -> str | None:
    """Formata um número (peso, valor) no padrão brasileiro (1.234,56).

    Aceita tanto texto com vírgula decimal (como vem do relatório) quanto
    ponto decimal (como o Excel/pandas às vezes grava). Se não for
    possível interpretar como número, devolve o texto original sem
    alteração — nunca inventa um valor.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return None

    texto_normalizado = texto.replace(".", "").replace(",", ".") if "," in texto else texto
    try:
        numero = float(texto_normalizado)
    except ValueError:
        return texto

    inteiro, _, decimal = f"{numero:,.2f}".partition(".")
    inteiro = inteiro.replace(",", ".")
    return f"{inteiro},{decimal}"


def _formatar_peso(valor: object) -> str:
    formatado = _formatar_numero_br(valor)
    return f"{formatado} kg" if formatado else "NÃO INFORMADO"


def _formatar_moeda(valor: object) -> str:
    formatado = _formatar_numero_br(valor)
    return f"R$ {formatado}" if formatado else "NÃO INFORMADO"


def _previsao_bruta(pedido: pd.Series) -> object:
    for coluna in ("previsao_entrega_calculada", "previsao_entrega", "prev_chegada"):
        if coluna in pedido.index and pd.notna(pedido.get(coluna)):
            return pedido.get(coluna)
    return None


def sugestao_situacao(pedido: pd.Series) -> str:
    """Situação + previsão sugeridas a partir dos dados do sistema —
    ponto de partida para o operador confirmar ou reescrever."""
    status = _valor(pedido, "status", "situacao_mdfe")
    previsao = _formatar_data(_previsao_bruta(pedido))
    return f"{status} | Previsão: {previsao}"


def revisar_situacoes_interativo(pedidos: pd.DataFrame) -> dict[int, str]:
    """Mostra, carga por carga, a situação/previsão sugerida e deixa o
    operador aceitar (Enter) ou digitar o texto que achar melhor — é o
    mesmo texto livre que era escrito manualmente antes (ex.: "Em rota
    para entrega amanhã terça"), só que com uma sugestão pronta.
    """
    situacoes: dict[int, str] = {}
    print("\nRevisão da situação de cada carga (Enter mantém o texto sugerido):")
    for indice, pedido in pedidos.iterrows():
        sugestao = sugestao_situacao(pedido)
        identificacao = _valor(pedido, "nf", "pedido", padrao="?")
        resposta = input(f"NF/Pedido {identificacao} — [{sugestao}]: ").strip()
        situacoes[indice] = resposta or sugestao
    return situacoes


def montar_mensagem_clientes(
    pedidos: pd.DataFrame,
    situacoes: dict[int, str] | None = None,
    data_referencia: str | None = None,
) -> str:
    """Monta a mensagem de posição de cargas no formato de tabela
    (Remetente/Pagador/Cidade/NF/Peso/Vol/Vr Frete/Motorista/Situação).

    `pedidos` pode conter cargas de mais de um cliente juntas (ver
    `src.clientes.selecionar_varios_clientes_interativo`) — cada carga
    aparece com seu próprio remetente/pagador na linha.
    """
    if pedidos.empty:
        raise ValueError("Não há cargas para montar a mensagem.")

    data_referencia = data_referencia or date.today().strftime("%d/%m/%Y")
    situacoes = situacoes or {}

    linhas: list[str] = []
    for indice, pedido in pedidos.iterrows():
        remetente = _valor(pedido, "remetente")
        pagador = _valor(pedido, "pagador")
        cidade = _valor(pedido, "cidade")
        nf = _valor(pedido, "nf")
        peso = _formatar_peso(pedido.get("peso_real"))
        volumes = _valor(pedido, "volumes")
        frete = _formatar_moeda(pedido.get("valor_frete"))
        motorista = _valor(pedido, "motorista")
        situacao = situacoes.get(indice) or sugestao_situacao(pedido)

        linhas.append(
            "\n".join(
                [
                    f"• Remetente: {remetente} | Pagador: {pagador}",
                    f"  Cidade: {cidade} | NF: {nf} | Peso: {peso} | Vol: {volumes} | Vr Frete: {frete}",
                    f"  Motorista: {motorista}",
                    f"  Situação: {situacao}",
                ]
            )
        )

    return "\n\n".join(
        [
            f"POSIÇÃO DE CARGAS — {data_referencia}",
            *linhas,
            "As previsões são estimativas e podem sofrer alterações durante o transporte.",
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
