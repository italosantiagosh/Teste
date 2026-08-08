from normalizacao import normalizar_nome, sugerir_correspondencia, sugerir_por_prefixo


def test_normalizar_nome_remove_acentos_e_espacos():
    assert normalizar_nome("São José") == "sao_jose"
    assert normalizar_nome("Nossa Senhora do Carmo") == "nossa_senhora_do_carmo"
    assert normalizar_nome("Santa Teresinha - Criança") == "santa_teresinha_crianca"


def test_normalizar_nome_colapsa_underscores_duplicados():
    assert normalizar_nome("São   José") == "sao_jose"
    assert normalizar_nome("--Ressuscitado--") == "ressuscitado"


def test_sugerir_correspondencia_encontra_erro_de_digitacao():
    conhecidas = ["sao_jose", "santa_teresinha", "carlo_acutis"]
    assert sugerir_correspondencia("sao_juse", conhecidas) == "sao_jose"


def test_sugerir_correspondencia_sem_nada_parecido():
    conhecidas = ["sao_jose", "santa_teresinha"]
    assert sugerir_correspondencia("carlo_acutis", conhecidas) is None


def test_sugerir_correspondencia_lista_vazia():
    assert sugerir_correspondencia("qualquer_coisa", []) is None


def test_difflib_sozinho_nao_pega_nome_com_sobrenome_extra():
    # confirma o motivo do bug: 'guido_schaffer' x 'guido' fica abaixo do
    # limiar de semelhança do difflib por causa da diferença de tamanho.
    assert sugerir_correspondencia("guido_schaffer", ["guido"]) is None


def test_sugerir_por_prefixo_encontra_santo_com_sobrenome_extra():
    conhecidas = ["guido", "sao_jose"]
    assert sugerir_por_prefixo("guido_schaffer", conhecidas) == "guido"


def test_sugerir_por_prefixo_remove_mais_de_uma_palavra_se_precisar():
    conhecidas = ["guido"]
    assert sugerir_por_prefixo("guido_cesar_schaffer", conhecidas) == "guido"


def test_sugerir_por_prefixo_sem_correspondencia():
    assert sugerir_por_prefixo("carlo_acutis", ["guido", "sao_jose"]) is None


def test_sugerir_por_prefixo_palavra_unica_nao_tem_prefixo_para_remover():
    assert sugerir_por_prefixo("guido", ["outro"]) is None
