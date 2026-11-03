# Define o protocolo ativo, pode ser "MQTT" ou "OPC-UA"
# protocolo_ativo = "MQTT"  
# Por agora , vou fazer com 1 ou 2

# IP da TV Box
ip_tvbox = "192.168.15.147"

# Parametros MQTT
broker_mqtt = ip_tvbox
porta_mqtt = 1883
topico_distancia = "ic/esp/distancia"

# Parametros OPC-UA
porta_opcua = 4840
endpoint_opcua = f"opc.tcp://{ip_tvbox}:{porta_opcua}/ic/"
namespace_opcua = "urn:gateway"

# Parametros CLP
ip_clp = "192.168.0.1"      # IP do CLP