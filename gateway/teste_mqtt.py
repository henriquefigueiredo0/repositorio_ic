
import time
import threading
import paho.mqtt.publish as publish

import mqtt
from config import broker_mqtt, porta_mqtt, topico_distancia


# Sinaliza quando uma mensagem chega
mensagem_recebida = threading.Event()


# Recebe a distancia pelo MQTT
def receber_distancia(distancia):
    print(f"Callback recebeu: {distancia:.2f} cm")
    mensagem_recebida.set()


# Testa um ciclo MQTT
def testar_mqtt(numero_teste, distancia):

    print(f"\n=== TESTE {numero_teste} ===")

    mensagem_recebida.clear()

    # Inicia o cliente MQTT da TV Box
    mqtt.iniciar(receber_distancia)

    try:
        # Aguarda a inscricao no topico
        time.sleep(2)

        print(f"Enviando distancia: {distancia:.2f} cm")

        # Publica uma mensagem de teste no broker
        publish.single(
            topico_distancia,
            payload=str(distancia),
            hostname=broker_mqtt,
            port=porta_mqtt
        )

        # Aguarda a mensagem chegar ao callback
        if mensagem_recebida.wait(timeout=5):
            print("Mensagem recebida com sucesso!")
        else:
            raise RuntimeError("Mensagem nao recebida.")

    finally:
        # Encerra o cliente MQTT
        mqtt.parar()
        print("Cliente MQTT encerrado.")


# Executa dois ciclos de comunicacao
def main():

    try:
        testar_mqtt(1, 12.34)
        testar_mqtt(2, 56.78)

        print("\nTESTES CONCLUIDOS!")

    except Exception as erro:
        print("\nERRO NO TESTE:", erro)


if __name__ == "__main__":
    main()
