"""Montagem de mensagens de texto com a posição de cargas, no formato de
tabela usado manualmente antes (Remetente/Destinatário/Cidade/NF/Peso/Vol/
Vr Frete/Motorista/Situação), podendo juntar mais de um cliente na mesma
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


# Quando a carga ainda não foi embarcada (sem número de manifesto), o
# sistema registra só a emissão do CT-e como última ocorrência (ex.:
# "CT-e autorizado com 1 volume e 12 Kg. Destino: RN/NATAL. Previsao de
# entrega: 07/08/26") — texto técnico demais pro cliente, e a "previsão"
# ali é só a data padrão do sistema, não uma previsão real de embarque.
_TERMOS_CTE_AUTORIZADO = ("cte autorizado", "ct-e autorizado")
_SITUACAO_AGUARDANDO_EMBARQUE = "No depósito em São Paulo aguardando embarque"


def _embarcado(pedido: pd.Series) -> bool:
    for coluna in ("primeiro_manifesto", "ultimo_manifesto"):
        if coluna in pedido.index:
            valor = pedido.get(coluna)
            if pd.notna(valor) and str(valor).strip():
                return True
    return False


def _aguardando_embarque(pedido: pd.Series) -> bool:
    if _embarcado(pedido):
        return False
    status_normalizado = normalizar_texto(_valor(pedido, "status", "situacao_mdfe", padrao=""))
    return any(termo in status_normalizado for termo in _TERMOS_CTE_AUTORIZADO)


def sugestao_situacao(pedido: pd.Series) -> str:
    """Situação sugerida a partir dos dados do sistema — ponto de partida
    para o operador confirmar ou reescrever. Não inclui a previsão: ela
    fica só na planilha (coluna previsao_entrega) para análise, não na
    mensagem ao cliente.

    Para cargas ainda não embarcadas com o texto padrão de emissão do
    CT-e, troca a sugestão por uma frase fixa mais amigável ao cliente.
    """
    if _aguardando_embarque(pedido):
        return _SITUACAO_AGUARDANDO_EMBARQUE
    return _valor(pedido, "status", "situacao_mdfe")


def revisar_situacoes_interativo(pedidos: pd.DataFrame) -> dict[int, str]:
    """Mostra, carga por carga, a situação sugerida (com a previsão como
    referência) e deixa o operador aceitar (Enter) ou digitar o texto que
    achar melhor — é o mesmo texto livre que era escrito manualmente antes
    (ex.: "Em rota para entrega amanhã terça"), só que com uma sugestão
    pronta. A previsão mostrada aqui é só apoio para a decisão — não entra
    na mensagem final. Para cargas aguardando embarque (ver
    `_aguardando_embarque`), nem a previsão é mostrada — a data que o
    sistema traz nesse caso não é confiável.
    """
    situacoes: dict[int, str] = {}
    print("\nRevisão da situação de cada carga (Enter mantém o texto sugerido):")
    for indice, pedido in pedidos.iterrows():
        sugestao = sugestao_situacao(pedido)
        previsao = "NÃO DEFINIDA" if _aguardando_embarque(pedido) else _formatar_data(_previsao_bruta(pedido))
        identificacao = _valor(pedido, "nf", "pedido", padrao="?")
        resposta = input(
            f"NF/Pedido {identificacao} — previsão: {previsao} — [{sugestao}]: "
        ).strip()
        situacoes[indice] = resposta or sugestao
    return situacoes


# ---------------------------------------------------------------------------
# Filtro: cargas "saída para entrega" já resolvidas há alguns dias, ou já
# entregues/em conferência no cliente, não precisam mais aparecer na
# mensagem.
# ---------------------------------------------------------------------------

_PADRAO_DATA_NA_OCORRENCIA = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")
_TERMOS_SAIDA_PARA_ENTREGA = ("saida para entrega", "saiu para entrega")

# Situações que já significam "resolvido" (mercadoria já chegou ao
# destino) — independente de data, não faz sentido mais avisar o cliente.
_TERMOS_JA_RESOLVIDO = (
    "em conferencia",
    "entrega realizada",
    "mercadoria entregue",
    "entregue ao destinatario",
    "canhoto",
)


def _situacao_ja_resolvida(pedido: pd.Series) -> bool:
    status = _valor(pedido, "status", "situacao_mdfe", padrao="")
    if status == "NÃO INFORMADO":
        return False
    status_normalizado = normalizar_texto(status)
    return any(termo in status_normalizado for termo in _TERMOS_JA_RESOLVIDO)


def _data_da_ocorrencia(status: str) -> date | None:
    """Extrai a data embutida no texto da última ocorrência (ex.: '...em
    03/08/26, 10:08h.'). Devolve None se não achar uma data válida.

    Usado apenas como reforço: nem todo status traz data no texto (ex.:
    "Saida para entrega na cidade de X." não tem nenhuma data escrita) —
    a fonte principal é a coluna `data_ultima_ocorrencia`, vinda direto do
    sistema (ver `_data_ultima_ocorrencia`).
    """
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


def _data_ultima_ocorrencia(pedido: pd.Series) -> date | None:
    """Data em que a última ocorrência foi registrada no sistema.

    Usa a coluna dedicada `data_ultima_ocorrencia` (vem de 'Data da Ultima
    Ocorrencia' no relatório) — necessária porque o TEXTO da ocorrência
    (coluna `status`) nem sempre traz a data escrita (ex.: "Saida para
    entrega na cidade de X." não tem data nenhuma no texto). Se a coluna
    não existir ou estiver vazia, tenta como último recurso achar uma data
    escrita dentro do próprio texto do status.
    """
    if "data_ultima_ocorrencia" in pedido.index:
        valor = pedido.get("data_ultima_ocorrencia")
        if pd.notna(valor):
            if isinstance(valor, (datetime, date, pd.Timestamp)):
                return pd.Timestamp(valor).date()
            data = pd.to_datetime(str(valor), errors="coerce", dayfirst=True)
            if pd.notna(data):
                return data.date()

    status = _valor(pedido, "status", "situacao_mdfe", padrao="")
    return _data_da_ocorrencia(status)


def _saida_para_entrega_ja_resolvida(
    pedido: pd.Series, data_referencia: date, dias_limite: int
) -> bool:
    status = _valor(pedido, "status", "situacao_mdfe", padrao="")
    if status == "NÃO INFORMADO":
        return False

    status_normalizado = normalizar_texto(status)
    if not any(termo in status_normalizado for termo in _TERMOS_SAIDA_PARA_ENTREGA):
        return False

    data_ocorrencia = _data_ultima_ocorrencia(pedido)
    if data_ocorrencia is None:
        return False

    return (data_referencia - data_ocorrencia).days >= dias_limite


def filtrar_pedidos_para_mensagem(
    pedidos: pd.DataFrame,
    data_referencia: date | None = None,
    dias_limite_saida_entrega: int = 2,
) -> pd.DataFrame:
    """Remove da mensagem cargas que já não precisam mais de aviso:

      - 'saída para entrega' há `dias_limite_saida_entrega` dias ou mais
        (normalmente já foram entregues);
      - situação já indica que chegou ao destino (em conferência, entrega
        realizada etc.), não importa a data.

    A planilha tratada continua com todas as cargas; este filtro afeta
    apenas o texto da mensagem.
    """
    if pedidos.empty:
        return pedidos.copy()

    data_referencia = data_referencia or date.today()

    ja_resolvido = pedidos.apply(_situacao_ja_resolvida, axis=1)
    saida_antiga = pedidos.apply(
        lambda linha: _saida_para_entrega_ja_resolvida(
            linha, data_referencia, dias_limite_saida_entrega
        ),
        axis=1,
    )
    mascara_manter = ~(ja_resolvido | saida_antiga)

    removidos_resolvidos = int(ja_resolvido.sum())
    removidos_saida_antiga = int((saida_antiga & ~ja_resolvido).sum())
    if removidos_resolvidos:
        logger.info(
            "%d carga(s) com situação já resolvida (entregue/em conferência) não entraram na mensagem.",
            removidos_resolvidos,
        )
    if removidos_saida_antiga:
        logger.info(
            "%d carga(s) com 'saída para entrega' há %d+ dias não entraram na mensagem.",
            removidos_saida_antiga,
            dias_limite_saida_entrega,
        )
    return pedidos.loc[mascara_manter].copy()


def montar_mensagem_clientes(
    pedidos: pd.DataFrame,
    situacoes: dict[int, str] | None = None,
    data_referencia: str | None = None,
) -> str:
    """Monta a mensagem de posição de cargas no formato de tabela
    (Remetente/Destinatário/Cidade/NF/Peso/Vol/Vr Frete/Motorista/Situação).

    Os títulos de cada campo saem em *negrito* usando a formatação nativa
    do WhatsApp (texto entre asteriscos) — o WhatsApp não tem sublinhado,
    só negrito/itálico/tachado.

    `pedidos` pode conter cargas de mais de um cliente juntas (ver
    `src.clientes.selecionar_varios_clientes_interativo`) — cada carga
    aparece com seu próprio remetente/destinatário na linha.
    """
    if pedidos.empty:
        raise ValueError("Não há cargas para montar a mensagem.")

    data_referencia = data_referencia or date.today().strftime("%d/%m/%Y")
    situacoes = situacoes or {}

    linhas: list[str] = []
    for indice, pedido in pedidos.iterrows():
        remetente = _valor(pedido, "remetente")
        destinatario = _valor(pedido, "cliente")
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
                    f"• *Remetente:* {remetente} | *Destinatário:* {destinatario}",
                    f"  *Cidade:* {cidade} | *NF:* {nf} | *Peso:* {peso} | *Vol:* {volumes} | *Vr Frete:* {frete}",
                    f"  *Motorista:* {motorista}",
                    f"  *Situação:* {situacao}",
                ]
            )
        )

    return "\n\n".join(
        [
            f"*POSIÇÃO DE CARGAS — {data_referencia}*",
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
