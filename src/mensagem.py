"""Montagem de mensagens de texto com a posição de cargas, no formato de
tabela usado manualmente antes (Remetente/Pagador/Cidade/NF/Peso/Vol/Vr
Frete/Motorista/Situação), podendo juntar mais de um cliente na mesma
mensagem.
"""
from __future__ import annotations

from datetime import date, datetime
import logging
import re

import pandas as pd

from src.utils import converter_numero_br, normalizar_texto

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
    """Formata um número (peso, valor) no padrão brasileiro (1.234,56)."""
    numero = converter_numero_br(valor)
    if numero is None:
        return None
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
    """Situação sugerida a partir dos dados do sistema — ponto de partida
    para o operador confirmar ou reescrever. Não inclui a previsão: ela
    fica só na planilha (coluna previsao_entrega) para análise, não na
    mensagem ao cliente."""
    return _valor(pedido, "status", "situacao_mdfe")


def revisar_situacoes_interativo(pedidos: pd.DataFrame) -> dict[int, str]:
    """Mostra, carga por carga, a situação sugerida (com a previsão como
    referência) e deixa o operador aceitar (Enter) ou digitar o texto que
    achar melhor — é o mesmo texto livre que era escrito manualmente antes
    (ex.: "Em rota para entrega amanhã terça"), só que com uma sugestão
    pronta. A previsão mostrada aqui é só apoio para a decisão — não entra
    na mensagem final.
    """
    situacoes: dict[int, str] = {}
    print("\nRevisão da situação de cada carga (Enter mantém o texto sugerido):")
    for indice, pedido in pedidos.iterrows():
        sugestao = sugestao_situacao(pedido)
        previsao = _formatar_data(_previsao_bruta(pedido))
        identificacao = _valor(pedido, "nf", "pedido", padrao="?")
        resposta = input(
            f"NF/Pedido {identificacao} — previsão: {previsao} — [{sugestao}]: "
        ).strip()
        situacoes[indice] = resposta or sugestao
    return situacoes


# ---------------------------------------------------------------------------
# Filtro: cargas "saída para entrega" já resolvidas há alguns dias não
# precisam mais aparecer na mensagem (normalmente já foram entregues).
# ---------------------------------------------------------------------------

_PADRAO_DATA_NA_OCORRENCIA = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")
_TERMOS_SAIDA_PARA_ENTREGA = ("saida para entrega", "saiu para entrega")


def _data_da_ocorrencia(status: str) -> date | None:
    """Extrai a data embutida no texto da última ocorrência (ex.: '...em
    03/08/26, 10:08h.'). Devolve None se não achar uma data válida."""
    if not status:
        return None
    encontro = _PADRAO_DATA_NA_OCORRENCIA.search(status)
    if not encontro:
        return None
    dia, mes, ano = encontro.groups()
    ano_completo = int(ano) + 2000 if len(ano) == 2 else int(ano)
    try:
        return date(ano_completo, int(mes), int(dia))
    except ValueError:
        return None


def _saida_para_entrega_ja_resolvida(
    pedido: pd.Series, data_referencia: date, dias_limite: int
) -> bool:
    status = _valor(pedido, "status", "situacao_mdfe", padrao="")
    if status == "NÃO INFORMADO":
        return False

    status_normalizado = normalizar_texto(status)
    if not any(termo in status_normalizado for termo in _TERMOS_SAIDA_PARA_ENTREGA):
        return False

    data_ocorrencia = _data_da_ocorrencia(status)
    if data_ocorrencia is None:
        return False

    return (data_referencia - data_ocorrencia).days >= dias_limite


def filtrar_pedidos_para_mensagem(
    pedidos: pd.DataFrame,
    data_referencia: date | None = None,
    dias_limite_saida_entrega: int = 2,
) -> pd.DataFrame:
    """Remove da mensagem cargas cuja última ocorrência já é 'saída para
    entrega' há `dias_limite_saida_entrega` dias ou mais — normalmente já
    foram entregues, então não vale mais avisar o cliente sobre isso.

    A planilha tratada continua com todas as cargas; este filtro afeta
    apenas o texto da mensagem.
    """
    if pedidos.empty:
        return pedidos.copy()

    data_referencia = data_referencia or date.today()

    mascara_manter = ~pedidos.apply(
        lambda linha: _saida_para_entrega_ja_resolvida(
            linha, data_referencia, dias_limite_saida_entrega
        ),
        axis=1,
    )
    removidos = int((~mascara_manter).sum())
    if removidos:
        logger.info(
            "%d carga(s) com 'saída para entrega' há %d+ dias não entraram na mensagem.",
            removidos,
            dias_limite_saida_entrega,
        )
    return pedidos.loc[mascara_manter].copy()


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
