
from flask import Flask, render_template, request, jsonify

# Cria o servidor web
app = Flask(__name__)

# Define a pagina inicial
@app.route("/")
def pagina_inicial():
    return render_template("index.html")

# Recebe a configuracao enviada pelo navegador
@app.route("/iniciar", methods=["POST"])
def iniciar():

    dados = request.get_json()

    print("Dados recebidos:", dados)

    return jsonify({
        "sucesso": True,
        "mensagem": "Configuracao recebida!"
    })

# Inicia o servidor na rede local
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
