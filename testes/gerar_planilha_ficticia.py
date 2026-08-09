"""
Gera uma planilha fictícia em `entrada/` para testar o módulo
`tratamento_planilha.py` sem depender do sistema real.

Usa os MESMOS nomes de coluna de origem configurados em
`config/colunas.json` (nomes reais do relatório SSW) — se o teste usasse
nomes genéricos diferentes, a renomeação não aconteceria e o teste não
estaria validando o pipeline de verdade.

Casos incluídos de propósito:
  - coluna a excluir (`Vendedor`);
  - colunas usadas na mensagem ao cliente (`Cliente Remetente`,
    `Cliente Pagador`, `Numero da Nota Fiscal`, `Peso Real em Kg`,
    `Quantidade de Volumes`, `Valor do Frete`);
  - coluna extra não mapeada (mantida ao final, sem perda de dado);
  - pedido e manifesto (primeiro e último) vindos como NÚMERO do Excel
    (viram '.0' na leitura bruta — deve ser removido pelo tratamento);
  - pedido duplicado, incluindo um duplicado só igual DEPOIS da
    normalização (um vem com '.0', o outro como texto puro);
  - pedido com zeros à esquerda (não pode virar número);
  - cliente com acentuação e espaços extras nas pontas;
  - pedido sem primeiro manifesto, mas com último manifesto preenchido
    (caso de fallback no cruzamento);
  - pedido sem manifesto nenhum (ainda não embarcado);
  - data de emissão em formatos diferentes (BR e ISO) e uma data inválida;
  - linha completamente vazia (deve ser removida sem avisar errado).

Não há coluna de CNPJ: o relatório real (`relatorio*.csv`, opção 455) não
traz essa informação — por isso não faz parte deste arquivo fictício (ver
comentário em `config/colunas.json`).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
ENTRADA_DIR = BASE_DIR / "entrada"


def gerar() -> Path:
    dados = [
        {
            "CTRC": "1001",
            "Cliente Remetente": "JTC Distribuidora Ltda",
            "Cliente Pagador": "JTC Distribuidora Ltda",
            "Cliente Destinatario": "  Comercial Nordeste Ltda ",
            "Cidade de Entrega": "Natal",
            "Data de Emissao": "01/08/2026",
            "Primeiro Manifesto": "GRU 002415-5",
            "Ultimo Manifesto": "",
            "Placa do Cavalo": "NVU5D88",
            "Descricao da Ultima Ocorrencia": "Em transito",
            "Numero da Nota Fiscal": "55501",
            "Peso Real em Kg": 120.5,
            "Quantidade de Volumes": 3,
            "Valor do Frete": 350.9,
            "Vendedor": "Fulano",
            "Observacao Extra": "cliente preferencial",
        },
        {
            "CTRC": 1002,  # número puro no Excel -> vira '1002.0' na leitura
            "Cliente Remetente": "Paiol Comercio Ltda",
            "Cliente Pagador": "Paiol Comercio Ltda",
            "Cliente Destinatario": "Comércio São José Ltda",  # com acento
            "Cidade de Entrega": "Mossoro",
            "Data de Emissao": "2026-08-01",
            "Primeiro Manifesto": "",  # vazio - usa o último manifesto (fallback)
            "Ultimo Manifesto": "GRU 002500-1",
            "Placa do Cavalo": "",
            "Descricao da Ultima Ocorrencia": "Pendente",
            "Numero da Nota Fiscal": "55502",
            "Peso Real em Kg": 80,
            "Quantidade de Volumes": 1,
            "Valor do Frete": 210,
            "Vendedor": "Fulano",
            "Observacao Extra": "",
        },
        {
            "CTRC": "1002",  # mesmo pedido do anterior, agora como texto puro
            "Cliente Remetente": "Paiol Comercio Ltda",
            "Cliente Pagador": "Paiol Comercio Ltda",
            "Cliente Destinatario": "Comércio São José Ltda",
            "Cidade de Entrega": "Mossoro",
            "Data de Emissao": "2026-08-01",
            "Primeiro Manifesto": 45143,  # número puro -> '45143.0' na leitura
            "Ultimo Manifesto": "",
            "Placa do Cavalo": "QGR9F84",
            "Descricao da Ultima Ocorrencia": "Coletado",
            "Numero da Nota Fiscal": "55502",
            "Peso Real em Kg": 80,
            "Quantidade de Volumes": 1,
            "Valor do Frete": 210,
            "Vendedor": "Fulano",
            "Observacao Extra": "",
        },
        {
            "CTRC": "1003",
            "Cliente Remetente": "Vimacedo Distribuidora",
            "Cliente Pagador": "Comercial Paty Ltda",
            "Cliente Destinatario": "Fortaleza Comercio Ltda",
            "Cidade de Entrega": "Fortaleza",
            "Data de Emissao": "31/13/2026",  # data inválida (mês 13)
            "Primeiro Manifesto": "GRU 002393-1",
            "Ultimo Manifesto": "",
            "Placa do Cavalo": "OWB1D50",
            "Descricao da Ultima Ocorrencia": "Pendente",
            "Numero da Nota Fiscal": "55503",
            "Peso Real em Kg": 45.0,
            "Quantidade de Volumes": 2,
            "Valor do Frete": 99.5,
            "Vendedor": "Fulano",
            "Observacao Extra": "",
        },
        {
            "CTRC": "00123",  # zeros à esquerda — não pode virar 123
            "Cliente Remetente": "Comercial Paty Ltda",
            "Cliente Pagador": "Comercial Paty Ltda",
            "Cliente Destinatario": "Cliente Zero Padded Ltda",
            "Cidade de Entrega": "Recife",
            "Data de Emissao": "05/08/2026",
            "Primeiro Manifesto": "GRU 009999-9",
            "Ultimo Manifesto": "",
            "Placa do Cavalo": "AQL2D03",
            "Descricao da Ultima Ocorrencia": "Em transito",
            "Numero da Nota Fiscal": "55504",
            "Peso Real em Kg": 12.3,
            "Quantidade de Volumes": 1,
            "Valor do Frete": 40,
            "Vendedor": "Fulano",
            "Observacao Extra": "",
        },
        # Linha completamente vazia (deve ser removida)
        {k: None for k in [
            "CTRC", "Cliente Remetente", "Cliente Pagador", "Cliente Destinatario",
            "Cidade de Entrega", "Data de Emissao", "Primeiro Manifesto",
            "Ultimo Manifesto", "Placa do Cavalo", "Descricao da Ultima Ocorrencia",
            "Numero da Nota Fiscal", "Peso Real em Kg", "Quantidade de Volumes",
            "Valor do Frete", "Vendedor", "Observacao Extra",
        ]},
    ]

    df = pd.DataFrame(dados)

    ENTRADA_DIR.mkdir(parents=True, exist_ok=True)
    caminho = ENTRADA_DIR / "relatorio_entregas_ficticio.xlsx"
    df.to_excel(caminho, index=False)
    print(f"Planilha fictícia gerada em: {caminho}")
    return caminho


if __name__ == "__main__":
    gerar()
