from flask import Flask, render_template

# Cria o servidor web
app = Flask(__name__)

# Define a pagina inicial
@app.route("/")
def pagina_inicial():
    return render_template("index.html")

# Inicia o servidor na rede local
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
