
import threading
import time

import mqtt
import opcua
import controle_esp


# Guarda o estado do gateway
protocolo_ativo = None
gateway_ativo = False

# Guarda a ultima medicao
ultima_distancia = None
instante_ultima_distancia = None

# Impede operacoes simultaneas
controle = threading.Lock()
controle_dados = threading.Lock()

# Tempo maximo sem receber dados
TEMPO_LIMITE = 2.5


# Recebe a distancia sem utilizar o CLP
def receber_distancia(distancia):
    global ultima_distancia, instante_ultima_distancia

    with controle_dados:
        ultima_distancia = float(distancia)
        instante_ultima_distancia = time.monotonic()

    print(f"Distancia recebida: {distancia:.2f} cm")


# Limpa a ultima medicao
def limpar_distancia():
    global ultima_distancia, instante_ultima_distancia

    with controle_dados:
        ultima_distancia = None
        instante_ultima_distancia = None


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

        limpar_distancia()

        # Inicia o receptor na TV Box
        try:
            if protocolo == "MQTT":
                mqtt.iniciar(receber_distancia)
            else:
                opcua.iniciar(receber_distancia)

        except Exception as erro:
            print("Erro ao iniciar receptor:", erro)

            try:
                if protocolo == "MQTT":
                    mqtt.parar()
                else:
                    opcua.parar()
            except Exception as erro_limpeza:
                print("Erro na limpeza:", erro_limpeza)

            limpar_distancia()
            return False

        # Solicita a transmissao pela ESP32
        try:
            controle_esp.enviar_comando(protocolo)

        except Exception as erro:
            print("Erro ao comandar ESP32:", erro)

            try:
                if protocolo == "MQTT":
                    mqtt.parar()
                else:
                    opcua.parar()
            except Exception as erro_limpeza:
                print("Erro na limpeza:", erro_limpeza)

            limpar_distancia()
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

        # Solicita a parada da ESP32
        try:
            controle_esp.enviar_comando("PARAR")

        except Exception as erro:
            print("Erro ao enviar PARAR:", erro)
            return False

        # Encerra o receptor
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
        limpar_distancia()

        print("Gateway parado.")
        return True


# Consulta o estado atual
def obter_estado():

    with controle:
        ativo = gateway_ativo
        protocolo = protocolo_ativo

        with controle_dados:
            distancia = ultima_distancia
            instante = instante_ultima_distancia

    # Verifica se a medicao e recente
    if instante is None:
        recente = False
    else:
        recente = (time.monotonic() - instante) <= TEMPO_LIMITE

    if not ativo:
        status_esp = "Parada"
        distancia = None

    elif recente:
        status_esp = "Recebendo dados"

    else:
        status_esp = "Aguardando dados"
        distancia = None

    return {
        "ativo": ativo,
        "protocolo": protocolo,
        "status_esp": status_esp,
        "distancia": distancia,
        "status_clp": "Nao monitorado",
        "estado_bomba": None
    }


if __name__ == "__main__":
    print("Modulo do gateway carregado.")
