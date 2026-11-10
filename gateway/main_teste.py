
import threading

import mqtt
import opcua
import controle_esp


# Guarda o estado do gateway
protocolo_ativo = None
gateway_ativo = False

# Impede operacoes simultaneas
controle = threading.Lock()


# Recebe a distancia sem utilizar o CLP
def receber_distancia(distancia):
    print(f"Distancia recebida: {distancia:.2f} cm")


# Inicia o protocolo selecionado
def iniciar_gateway(protocolo):
    global protocolo_ativo, gateway_ativo

    with controle:

        if gateway_ativo:
            print("Gateway ja esta ativo.")
            return False

        if protocolo not in ("MQTT", "OPCUA"):
            print("Protocolo invalido.")
            return False

        # Prepara o receptor na TV Box
        try:
            if protocolo == "MQTT":
                mqtt.iniciar(receber_distancia)
            else:
                opcua.iniciar(receber_distancia)

        except Exception as erro:
            print("Erro ao iniciar receptor:", erro)

            # Tenta limpar uma inicializacao parcial
            try:
                if protocolo == "MQTT":
                    mqtt.parar()
                else:
                    opcua.parar()
            except Exception as erro_limpeza:
                print("Erro na limpeza:", erro_limpeza)

            return False

        # Envia o comando para a ESP32
        try:
            controle_esp.enviar_comando(protocolo)

        except Exception as erro:
            print("Erro ao comandar ESP32:", erro)

            # Desfaz a inicializacao do receptor
            try:
                if protocolo == "MQTT":
                    mqtt.parar()
                else:
                    opcua.parar()
            except Exception as erro_limpeza:
                print("Erro na limpeza:", erro_limpeza)

            return False

        protocolo_ativo = protocolo
        gateway_ativo = True

        print("Gateway iniciado:", protocolo)
        return True


# Encerra o protocolo ativo
def parar_gateway():
    global protocolo_ativo, gateway_ativo

    with controle:

        if not gateway_ativo:
            print("Gateway ja esta parado.")
            return False

        # Solicita que a ESP32 pare de transmitir
        try:
            controle_esp.enviar_comando("PARAR")

        except Exception as erro:
            print("Erro ao enviar PARAR:", erro)
            return False

        # Encerra o receptor na TV Box
        try:
            if protocolo_ativo == "MQTT":
                mqtt.parar()

            elif protocolo_ativo == "OPCUA":
                opcua.parar()

        except Exception as erro:
            print("Erro ao parar receptor:", erro)
            return False

        gateway_ativo = False
        protocolo_ativo = None

        print("Gateway parado.")
        return True


# Consulta o estado atual
def obter_estado():

    with controle:
        return {
            "ativo": gateway_ativo,
            "protocolo": protocolo_ativo
        }


if __name__ == "__main__":
    print("Modulo do gateway carregado.")
