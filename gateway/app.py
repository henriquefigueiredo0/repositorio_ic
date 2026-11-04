
from flask import Flask, render_template, request, jsonify

# Cria o servidor web
app = Flask(__name__)

# Guarda o estado simulado do gateway
gateway_ativo = False

# Define a pagina inicial
@app.route("/")
def pagina_inicial():
    return render_template("index.html")

# Recebe o comando de inicio
@app.route("/iniciar", methods=["POST"])
def iniciar():
    global gateway_ativo

    if gateway_ativo:
        return jsonify({
            "sucesso": False,
            "mensagem": "Gateway ja esta ativo!"
        })

    dados = request.get_json()

    print("Configuracao recebida:", dados)

    gateway_ativo = True

    return jsonify({
        "sucesso": True,
        "mensagem": "Gateway iniciado (simulacao)."
    })

# Recebe o comando de parada
@app.route("/parar", methods=["POST"])
def parar():
    global gateway_ativo

    if not gateway_ativo:
        return jsonify({
            "sucesso": False,
            "mensagem": "Gateway ja esta parado!"
        })

    gateway_ativo = False

    return jsonify({
        "sucesso": True,
        "mensagem": "Gateway parado (simulacao)."
    })

# Inicia o servidor na rede local
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
