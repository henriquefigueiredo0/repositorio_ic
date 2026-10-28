# Define o protocolo ativo, pode ser "MQTT" ou "OPC-UA"
# protocolo_ativo = "MQTT"  
# Por agora , vou fazer com 1 ou 2

# Parametros MQTT
broker_mqtt = "192.168.0.123"
porta_mqtt = 1883
topico_distancia = "ic/esp/distancia"

# Parametros OPC-UA
porta_opcua = 4840
endpoint_opcua = "opc.tcp://0.0.0.0:4840/ic/"
namespace_opcua = "urn:gateway"

# Parametros CLP
ip_clp = "192.168.0.1"      # IP do CLP