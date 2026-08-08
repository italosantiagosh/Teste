from normalizacao import normalizar_nome, sugerir_correspondencia


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
