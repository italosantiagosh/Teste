"""
Configuração central da automação.

Nenhum dado sensível (usuário, senha, token) deve ser escrito neste
arquivo. Esses dados vêm de variáveis de ambiente (arquivo `.env`, que
não deve ser versionado) ou são solicitados durante a execução.

As configurações de negócio (nomes de colunas, regras de previsão,
clientes/WhatsApp) ficam em arquivos JSON dentro de `config/`, para que
possam ser ajustadas sem mexer em código.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

_caminho_env = BASE_DIR / ".env"
if not load_dotenv(_caminho_env):
    # Não interrompe a execução (pode ser proposital não ter .env em
    # alguns cenários), mas avisa claramente, já que "URL não configurada"
    # sozinho não deixa óbvio que o problema é o .env não ter sido achado.
    import logging as _logging

    _logging.getLogger("automacao_transportadora").warning(
        "Arquivo .env não encontrado em: %s — as configurações vão usar "
        "valores padrão/vazios. Confira se o arquivo existe e NÃO se "
        "chama '.env.txt' (erro comum ao salvar pelo Bloco de Notas no "
        "Windows).",
        _caminho_env,
    )

# ---------------------------------------------------------------------------
# Caminhos base do projeto
# ---------------------------------------------------------------------------

CONFIG_DIR = BASE_DIR / "config"
ENTRADA_DIR = BASE_DIR / "entrada"
SAIDA_DIR = BASE_DIR / "saida"
LOGS_DIR = BASE_DIR / "logs"

for _dir in (ENTRADA_DIR, SAIDA_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def _carregar_json(nome_arquivo: str) -> dict:
    """Carrega um arquivo JSON de config/. Retorna {} se não existir."""
    caminho = CONFIG_DIR / nome_arquivo
    if not caminho.exists():
        return {}
    with caminho.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Configuração de colunas da planilha principal
# ---------------------------------------------------------------------------

_colunas_cfg = _carregar_json("colunas.json")


@dataclass
class ColunasConfig:
    """Nomes de colunas usados em todo o projeto (fonte única da verdade)."""

    # Nome das colunas como vêm no arquivo baixado -> nome final desejado
    mapa_renomeacao: dict[str, str] = field(
        default_factory=lambda: _colunas_cfg.get("mapa_renomeacao", {})
    )
    colunas_excluir: list[str] = field(
        default_factory=lambda: _colunas_cfg.get("colunas_excluir", [])
    )
    ordem_final: list[str] = field(
        default_factory=lambda: _colunas_cfg.get("ordem_final", [])
    )

    # Colunas-chave (já no nome FINAL, após renomeação)
    col_pedido: str = _colunas_cfg.get("col_pedido", "pedido")
    col_cnpj: str = _colunas_cfg.get("col_cnpj", "cnpj")
    col_cliente: str = _colunas_cfg.get("col_cliente", "cliente")
    col_cidade: str = _colunas_cfg.get("col_cidade", "cidade")
    col_data_emissao: str = _colunas_cfg.get("col_data_emissao", "data_emissao")
    col_motorista: str = _colunas_cfg.get("col_motorista", "motorista")
    col_previsao: str = _colunas_cfg.get("col_previsao", "previsao_entrega")
    # Coluna usada como chave principal no cruzamento pedidos <-> motoristas
    # (hoje: primeiro manifesto, com fallback para o último - ver
    # src/cruzamento.py). Também usada para decidir se um pedido já foi
    # embarcado (ver src/previsao_entrega.py).
    col_chave_cruzamento: str = _colunas_cfg.get("col_chave_cruzamento", "primeiro_manifesto")
    col_chave_cruzamento_fallback: str = _colunas_cfg.get("col_chave_cruzamento_fallback", "ultimo_manifesto")


COLUNAS = ColunasConfig()

# ---------------------------------------------------------------------------
# Configuração de sistema / navegador / downloads
# ---------------------------------------------------------------------------


@dataclass
class SistemaConfig:
    url_sistema: str = os.getenv("URL_SISTEMA", "")
    navegador: str = os.getenv("NAVEGADOR", "chrome")
    # Por padrão, os relatórios são baixados direto na pasta 'entrada/' do
    # projeto (não na pasta padrão de Downloads do Windows), para já ficarem
    # no lugar certo para o tratamento da planilha. Pode ser sobrescrito
    # via PASTA_DOWNLOADS no .env — uma linha vazia (ou ausente) usa o padrão.
    pasta_downloads: Path = Path(os.getenv("PASTA_DOWNLOADS") or str(ENTRADA_DIR))
    pasta_saida: Path = SAIDA_DIR
    timeout_padrao_segundos: int = int(os.getenv("TIMEOUT_PADRAO_SEGUNDOS", "20"))
    unidade_padrao: str = os.getenv("UNIDADE_PADRAO", "GRU")


SISTEMA = SistemaConfig()

# ---------------------------------------------------------------------------
# Credenciais (NUNCA fixas no código — sempre de variável de ambiente)
# ---------------------------------------------------------------------------


@dataclass
class CredenciaisConfig:
    dominio: str = os.getenv("SISTEMA_DOMINIO", "")  # ex.: 'CDI' — deixe em branco se o sistema não usar domínio
    cpf: str = os.getenv("SISTEMA_CPF", "")  # obrigatório em sessão nova (sem cookie de "Lembrar CPF")
    usuario: str = os.getenv("SISTEMA_USUARIO", "")
    senha: str = os.getenv("SISTEMA_SENHA", "")


CREDENCIAIS = CredenciaisConfig()

# ---------------------------------------------------------------------------
# Regras de previsão de entrega e clientes/WhatsApp
# ---------------------------------------------------------------------------

REGRAS_ENTREGA: dict = _carregar_json("regras_entrega.json")
CLIENTES: dict = _carregar_json("clientes.json")
