import paho.mqtt.client as mqtt

from config import broker_mqtt, porta_mqtt, topico_distancia

funcao_distancia = None

def quando_conectar(cliente, userdata, flags, reason_code, properties):

    print("Conectado ao broker!")
    cliente.subscribe(topico_distancia)      # Inscreve-se no tópico para receber mensagens da ESP sobre a distancia

def quando_receber(cliente, userdata, mensagem):

    dado = mensagem.payload.decode()    # Decodifica o payload da mensagem e deixa em formato string

    # Caso o topico seja o de distancia
    if mensagem.topic == topico_distancia:

        distancia = float(dado)  

        print("Distancia recebida da ESP:", dado, "cm")
        print()

        if funcao_distancia is not None:
            funcao_distancia(distancia)     # Aqui, funcao_distancia == escrever_distancia

# Cria o objeto cliente MQTT
cliente = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

cliente.on_connect = quando_conectar    # Chama a funcao quando_conectar quando o cliente se conectar ao broker
cliente.on_message = quando_receber     # Chama a funcao quando_receber quando o cliente receber uma mensagem

# Funcao chamada pelo main caso o protocolo ativo seja MQTT
# A funcao "callback_distancia" seria a "escrever_distancia"
def iniciar(callback_distancia):

    global funcao_distancia         # para modificar a variavel funcao_distancia

    funcao_distancia = callback_distancia   # funcao_distancia deixa de ser None e passa a ser escrever_distancia

    cliente.connect(broker_mqtt, porta_mqtt)  # Se conecta ao broker MQTT
    cliente.loop_start()            # Mantem o loop em segundo plano

# Para o loop MQTT
def parar():

    cliente.loop_stop()
    cliente.disconnect()