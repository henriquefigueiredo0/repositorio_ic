
import mqtt
import opcua

# Guarda o protocolo selecionado
protocolo_ativo = None

# Indica se o gateway esta ativo
gateway_ativo = False

# Define se o CLP sera utilizado
usar_clp = False


# Recebe a distancia sem precisar do CLP
def receber_distancia(distancia):
    print(f"Distancia recebida: {distancia:.2f} cm")


# Inicia o gateway com o protocolo escolhido
def iniciar_gateway(protocolo):
    global protocolo_ativo, gateway_ativo

    # Impede iniciar duas vezes
    if gateway_ativo:
        print("Gateway ja esta ativo.")
        return False

    # Verifica se o protocolo e valido
    if protocolo not in ("MQTT", "OPCUA"):
        print("Protocolo invalido.")
        return False

    # Inicia o protocolo selecionado
    try:
        if protocolo == "MQTT":
            mqtt.iniciar(receber_distancia)

        elif protocolo == "OPCUA":
            opcua.iniciar(receber_distancia)

    except Exception as erro:
        print("Erro ao iniciar gateway:", erro)
        return False

    protocolo_ativo = protocolo
    gateway_ativo = True

    print("Gateway iniciado:", protocolo_ativo)
    return True


# Encerra a comunicacao do gateway
def parar_gateway():
    global protocolo_ativo, gateway_ativo

    # Verifica se ja esta parado
    if not gateway_ativo:
        print("Gateway ja esta parado.")
        return False

    # Encerra o protocolo selecionado
    try:
        if protocolo_ativo == "MQTT":
            mqtt.parar()

        elif protocolo_ativo == "OPCUA":
            opcua.parar()

    except Exception as erro:
        print("Erro ao parar gateway:", erro)
        return False

    gateway_ativo = False
    protocolo_ativo = None

    print("Gateway parado.")
    return True


# Executa somente quando chamado diretamente
if __name__ == "__main__":
    print("Modulo de gerenciamento do gateway carregado.")
