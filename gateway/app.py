
import atexit

from flask import Flask, jsonify, render_template, request

import config
import main


# Cria a aplicacao web
app = Flask(__name__)

# Limita o tamanho das requisicoes JSON recebidas
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024


# Padroniza as respostas da API
def responder(sucesso, mensagem, codigo=200, **dados):
    resposta = {"sucesso": sucesso, "mensagem": mensagem}
    resposta.update(dados)

    return jsonify(resposta), codigo


# Confere se a requisicao possui um objeto JSON
def obter_dados():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        raise ValueError("Envie um objeto JSON valido.")

    return dados


# Trata erros de cadastro ou configuracao das regras
def tratar_erro(erro):
    if isinstance(erro, KeyError):
        return responder(False, str(erro.args[0]), 404)

    if isinstance(erro, ValueError):
        return responder(False, str(erro), 400)

    if isinstance(erro, RuntimeError):
        return responder(False, str(erro), 503)

    # Nao envia detalhes internos de erros inesperados ao navegador
    print(f"Erro interno na API: {erro}")
    return responder(False, "Erro interno no gateway.", 500)


# Exibe a pagina principal da interface
@app.route("/", methods=["GET"])
def pagina_inicial():
    return render_template("index.html")


# Retorna todas as regras e os seus estados atuais
@app.route("/api/regras", methods=["GET"])
def listar_regras():
    try:
        regras = main.listar_regras()

        # O JavaScript espera uma lista JSON diretamente
        return jsonify(regras)

    except Exception as erro:
        return tratar_erro(erro)


# Cadastra uma nova regra no SQLite
@app.route("/api/regras", methods=["POST"])
def criar_regra():
    try:
        dados = obter_dados()

        # O motor valida os campos e verifica conflitos
        id_regra = main.criar_regra(dados)

        return responder(
            True,
            "Regra cadastrada com sucesso.",
            201,
            id=id_regra
        )

    except Exception as erro:
        return tratar_erro(erro)


# Atualiza uma regra existente
@app.route("/api/regras/<int:id_regra>", methods=["PUT"])
def atualizar_regra(id_regra):
    try:
        dados = obter_dados()

        # A atualizacao preserva o identificador da regra
        main.atualizar_regra(id_regra, dados)

        return responder(True, "Regra atualizada com sucesso.")

    except Exception as erro:
        return tratar_erro(erro)


# Exclui uma regra cadastrada
@app.route("/api/regras/<int:id_regra>", methods=["DELETE"])
def remover_regra(id_regra):
    try:
        main.remover_regra(id_regra)

        return responder(True, "Regra excluida com sucesso.")

    except Exception as erro:
        return tratar_erro(erro)


# Ativa ou desativa uma regra individualmente
@app.route("/api/regras/<int:id_regra>/ativar", methods=["POST"])
def ativar_regra(id_regra):
    try:
        dados = obter_dados()
        ativo = dados.get("ativo")

        # Exige um booleano verdadeiro ou falso
        if not isinstance(ativo, bool):
            raise ValueError("O campo ativo deve ser booleano.")

        main.ativar_regra(id_regra, ativo)

        mensagem = "Regra ativada." if ativo else "Regra desativada."
        return responder(True, mensagem)

    except Exception as erro:
        return tratar_erro(erro)


# Consulta a disponibilidade do MQTT, OPC UA e acesso ao CLP
@app.route("/api/servicos", methods=["GET"])
def consultar_servicos():
    try:
        return jsonify(main.obter_servicos())

    except Exception as erro:
        return tratar_erro(erro)


# Inicializa os servicos e inicia a interface web
if __name__ == "__main__":
    try:
        # Inicia os dois protocolos antes de abrir o Flask
        main.iniciar_gateway()

        # Registra o encerramento dos servicos ao sair do Python
        atexit.register(main.encerrar_gateway)

        print(f"Interface web disponivel na porta {config.PORTA_WEB}")

        # Sem reloader, evitando iniciar duas instancias do motor
        app.run(
            host=config.HOST_WEB,
            port=config.PORTA_WEB,
            debug=False,
            threaded=True,
            use_reloader=False
        )

    finally:
        # Garante a tentativa de encerramento ao sair do Flask
        main.encerrar_gateway()
