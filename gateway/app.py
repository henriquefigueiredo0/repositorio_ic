
from flask import Flask, render_template, request, jsonify

import main_teste
from config import porta_mqtt, porta_opcua
from config import topico_distancia, namespace_opcua


# Cria o servidor web
app = Flask(__name__)


# Exibe a interface principal
@app.route("/")
def pagina_inicial():
    return render_template("index.html")


# Consulta o estado do gateway
@app.route("/estado", methods=["GET"])
def consultar_estado():
    return jsonify(main_teste.obter_estado())


# Inicia a comunicacao
@app.route("/iniciar", methods=["POST"])
def iniciar():

    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "sucesso": False,
            "mensagem": "Configuracao invalida."
        }), 400

    protocolo = dados.get("protocolo")
    porta = dados.get("porta")
    parametro = dados.get("parametro")

    # Confere os parametros atualmente suportados
    if protocolo == "MQTT":
        configuracao_valida = (
            porta == porta_mqtt and
            parametro == topico_distancia
        )

    elif protocolo == "OPCUA":
        configuracao_valida = (
            porta == porta_opcua and
            parametro == namespace_opcua
        )

    else:
        return jsonify({
            "sucesso": False,
            "mensagem": "Protocolo invalido."
        }), 400

    if not configuracao_valida:
        return jsonify({
            "sucesso": False,
            "mensagem": "Use os parametros padrao nesta etapa."
        }), 400

    # Solicita o inicio do gateway
    sucesso = main_teste.iniciar_gateway(protocolo)

    if not sucesso:
        return jsonify({
            "sucesso": False,
            "mensagem": "Nao foi possivel iniciar o gateway."
        }), 409

    return jsonify({
        "sucesso": True,
        "mensagem": "Gateway iniciado com " + protocolo
    })


# Para a comunicacao
@app.route("/parar", methods=["POST"])
def parar():

    sucesso = main_teste.parar_gateway()

    if not sucesso:
        return jsonify({
            "sucesso": False,
            "mensagem": "Nao foi possivel parar o gateway."
        }), 409

    return jsonify({
        "sucesso": True,
        "mensagem": "Gateway parado com sucesso."
    })


# Inicia o servidor Flask
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )
