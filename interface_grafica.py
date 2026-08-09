"""
Interface gráfica simples (Tkinter, já incluso no Python — nenhuma
dependência nova) para rodar a automação sem precisar abrir um terminal
ou o VS Code.

Não reimplementa nenhuma regra de negócio: só chama as mesmas funções
`opcao_*` de `main.py`, com adaptações para funcionar numa janela:

  - a saída de `print(...)` é redirecionada para a caixa de texto da janela;
  - respostas de `input(...)` são pedidas numa caixinha de diálogo;
  - perguntas de confirmação (prompts terminados em "(s/n)") viram uma
    caixinha com botões Sim/Não, em vez de precisar digitar "s" ou "n";
  - a senha pedida via `getpass.getpass(...)` usa uma caixinha com o texto
    mascarado, em vez do terminal.

Cada ação roda em uma thread separada para a janela não travar durante as
esperas do Selenium — por isso só uma ação pode rodar por vez (os botões
ficam desabilitados enquanto uma está em andamento).

Nota de implementação: Tkinter não é thread-safe, então a thread da ação
NUNCA mexe direto em nenhum widget - tudo (texto de saída, pedido de
entrada, fim da execução) passa por uma única fila, processada só pela
thread principal (a mesma que roda o `mainloop`).
"""

from __future__ import annotations

import builtins
import getpass as _getpass_module
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

import main as automacao

# Prompts terminados em "(s/n)" (o padrão usado em todo o projeto para
# perguntas de sim/não) viram uma caixinha com botões Sim/Não em vez de
# uma caixa de texto onde seria preciso digitar "s" ou "n".
_PADRAO_SIM_NAO = re.compile(r"\(s/n\)\s*:?\s*$", re.IGNORECASE)

MENU_BOTOES = [
    ("1 - Baixar novo relatório", automacao.opcao_1_baixar_relatorio),
    ("2 - Capturar tabela de motoristas", automacao.opcao_2_capturar_motoristas),
    ("3 - Tratar e cruzar os dados", automacao.opcao_3_tratar_e_cruzar),
    ("4 - Consultar cliente", automacao.opcao_4_consultar_cliente),
    ("5 - Gerar mensagem de um cliente", automacao.opcao_5_gerar_mensagem),
    ("6 - Preparar envio pelo WhatsApp", automacao.opcao_6_preparar_whatsapp),
    ("7 - Executar processo completo", automacao.opcao_7_processo_completo),
    ("8 - Gerar links do WhatsApp para vários destinatários", automacao.opcao_8_gerar_links_whatsapp),
]


class JanelaAutomacao:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Automação Transportadora")
        self.root.geometry("720x520")
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        # Única fila de comunicação entre a thread da ação e a thread
        # principal (Tkinter). Itens possíveis:
        #   ("saida", texto)
        #   ("pedido", prompt, mascarar, evento, resultado_dict)
        #   ("confirmar", prompt, evento, resultado_dict)
        #   ("fim",)
        self._fila_eventos: "queue.Queue[tuple]" = queue.Queue()
        self._em_execucao = False
        self._botoes: list[tk.Widget] = []

        self._montar_layout()
        self.root.after(100, self._processar_fila)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _montar_layout(self) -> None:
        quadro_botoes = ttk.Frame(self.root, padding=10)
        quadro_botoes.pack(side=tk.TOP, fill=tk.X)

        for texto, funcao in MENU_BOTOES:
            botao = ttk.Button(
                quadro_botoes,
                text=texto,
                command=lambda f=funcao, t=texto: self._executar_acao(t, f),
            )
            botao.pack(fill=tk.X, pady=2)
            self._botoes.append(botao)

        self.rotulo_status = ttk.Label(self.root, text="Pronto.", padding=(10, 0))
        self.rotulo_status.pack(side=tk.TOP, fill=tk.X)

        self.caixa_saida = scrolledtext.ScrolledText(
            self.root, state="normal", wrap=tk.WORD, height=18
        )
        self.caixa_saida.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.caixa_saida.configure(state="disabled")

        botao_sair = ttk.Button(self.root, text="Sair", command=self._ao_fechar)
        botao_sair.pack(side=tk.BOTTOM, pady=(0, 10))

    # ------------------------------------------------------------------
    # Fila única: processada a cada 100ms, sempre na thread principal.
    # ------------------------------------------------------------------

    def _processar_fila(self) -> None:
        try:
            while True:
                item = self._fila_eventos.get_nowait()
                tipo = item[0]

                if tipo == "saida":
                    _, texto = item
                    self.caixa_saida.configure(state="normal")
                    self.caixa_saida.insert(tk.END, texto)
                    self.caixa_saida.see(tk.END)
                    self.caixa_saida.configure(state="disabled")

                elif tipo == "pedido":
                    _, prompt, mascarar, evento, resultado = item
                    from tkinter import simpledialog

                    resposta = simpledialog.askstring(
                        "Automação Transportadora",
                        prompt or "Informe o valor:",
                        show="*" if mascarar else None,
                        parent=self.root,
                    )
                    resultado["valor"] = resposta if resposta is not None else ""
                    evento.set()

                elif tipo == "confirmar":
                    _, prompt, evento, resultado = item
                    from tkinter import messagebox

                    pergunta = _PADRAO_SIM_NAO.sub("", prompt).strip() or prompt
                    resposta = messagebox.askyesno(
                        "Automação Transportadora", pergunta, parent=self.root
                    )
                    resultado["valor"] = "s" if resposta else "n"
                    evento.set()

                elif tipo == "fim":
                    self._em_execucao = False
                    self._atualizar_botoes(True)
                    self.rotulo_status.configure(text="Pronto.")
        except queue.Empty:
            pass

        self.root.after(100, self._processar_fila)

    def _escrever_saida(self, texto: str) -> None:
        self._fila_eventos.put(("saida", texto))

    def _pedir_texto(self, prompt: str, mascarar: bool = False) -> str:
        resultado: dict[str, str] = {}
        evento = threading.Event()
        self._fila_eventos.put(("pedido", prompt, mascarar, evento, resultado))
        evento.wait()
        return resultado["valor"]

    def _pedir_confirmacao(self, prompt: str) -> str:
        resultado: dict[str, str] = {}
        evento = threading.Event()
        self._fila_eventos.put(("confirmar", prompt, evento, resultado))
        evento.wait()
        return resultado["valor"]

    def _entrada(self, prompt: str = "") -> str:
        texto_prompt = str(prompt)
        if _PADRAO_SIM_NAO.search(texto_prompt):
            return self._pedir_confirmacao(texto_prompt)
        return self._pedir_texto(texto_prompt)

    # ------------------------------------------------------------------
    # Execução das ações (thread separada, com input/print substituídos)
    # ------------------------------------------------------------------

    def _atualizar_botoes(self, habilitados: bool) -> None:
        estado = "normal" if habilitados else "disabled"
        for botao in self._botoes:
            botao.configure(state=estado)

    def _executar_acao(self, nome: str, funcao) -> None:
        if self._em_execucao:
            return

        self._em_execucao = True
        self._atualizar_botoes(False)
        self.rotulo_status.configure(text=f"Executando: {nome}...")

        def _rodar() -> None:
            stdout_original = sys.stdout
            input_original = builtins.input
            getpass_original = _getpass_module.getpass

            sys.stdout = _EscritorParaFila(self)
            builtins.input = self._entrada
            _getpass_module.getpass = lambda prompt="Senha: ": self._pedir_texto(
                str(prompt), mascarar=True
            )

            try:
                self._escrever_saida(f"\n=== {nome} ===\n")
                funcao()
            except NotImplementedError as e:
                self._escrever_saida(f"Ainda não disponível: {e}\n")
            except Exception as e:  # mesmo tratamento do menu de terminal
                automacao.logger.exception("Erro inesperado ao executar '%s'", nome)
                self._escrever_saida(f"Deu erro: [{type(e).__name__}] {e}\n")
                self._escrever_saida(
                    "(Detalhes completos também foram salvos em logs/automacao.log)\n"
                )
            finally:
                sys.stdout = stdout_original
                builtins.input = input_original
                _getpass_module.getpass = getpass_original
                self._fila_eventos.put(("fim",))

        threading.Thread(target=_rodar, daemon=True).start()

    def _ao_fechar(self) -> None:
        if self._em_execucao:
            from tkinter import messagebox

            if not messagebox.askyesno(
                "Ação em andamento",
                "Uma ação ainda está em execução (ex.: navegador aberto). "
                "Fechar mesmo assim?",
            ):
                return
        self.root.destroy()

    def rodar(self) -> None:
        self.root.mainloop()


class _EscritorParaFila:
    """Objeto compatível com `sys.stdout` que empilha o texto escrito na
    fila da janela, em vez de mandar para o terminal."""

    def __init__(self, janela: JanelaAutomacao) -> None:
        self._janela = janela

    def write(self, texto: str) -> int:
        if texto:
            self._janela._escrever_saida(texto)
        return len(texto)

    def flush(self) -> None:
        pass


def main() -> None:
    JanelaAutomacao().rodar()


if __name__ == "__main__":
    try:
        main()
    except BaseException as erro:  # noqa: BLE001 - último recurso antes de sumir sem aviso
        # Em um .exe gerado com --windowed não existe console: se algo
        # falhar ANTES da janela abrir (ex.: biblioteca faltando, .env
        # malformado), o programa fecharia sem nenhum aviso visível. Mostra
        # o erro numa caixa de diálogo simples em vez de sumir em silêncio.
        import traceback
        from pathlib import Path

        detalhe = traceback.format_exc()

        # Registra o erro mesmo que o logging de main.py não tenha chegado
        # a ser configurado (ex.: falha durante o próprio import).
        try:
            pasta_logs = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent / "logs"
            pasta_logs.mkdir(parents=True, exist_ok=True)
            (pasta_logs / "erro_inicializacao.log").write_text(detalhe, encoding="utf-8")
        except Exception:
            pass

        try:
            import tkinter as _tk
            from tkinter import messagebox as _messagebox

            _raiz_erro = _tk.Tk()
            _raiz_erro.withdraw()
            _messagebox.showerror(
                "Automação Transportadora — erro ao iniciar",
                f"O programa não conseguiu iniciar:\n\n{erro}\n\n"
                "Detalhes completos foram salvos em logs/erro_inicializacao.log, "
                "na mesma pasta do programa.",
            )
        except Exception:
            pass
        raise
