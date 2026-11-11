# IP da TV Box
ip_tvbox = "192.168.0.123"

# Parametros MQTT
broker_mqtt = ip_tvbox
porta_mqtt = 1883
topico_distancia = "ic/esp/distancia"

# Parametros OPC UA
porta_opcua = 4840
endpoint_opcua = f"opc.tcp://{ip_tvbox}:{porta_opcua}/ic/"
namespace_opcua = "urn:gateway"

# Parametros CLP
ip_clp = "192.168.0.1"

# False: testes em casa sem CLP
# True: comunica com o CLP pela rede
habilitar_clp = True

# Saida que representa a bomba
bit_bomba = 3 # Q0.3
