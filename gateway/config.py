from pathlib import Path


# Pasta onde estao os arquivos do gateway
PASTA_GATEWAY = Path(__file__).resolve().parent

# Banco que armazena as regras cadastradas na interface
BANCO_DADOS = PASTA_GATEWAY / "regras.db"


# MQTT: o Mosquitto sera executado na propria TV Box
BROKER_MQTT = "127.0.0.1"
PORTA_MQTT = 1883


# OPC UA: 0.0.0.0 permite conexoes pelas interfaces de rede
HOST_OPCUA = "0.0.0.0"
PORTA_OPCUA = 4840
ENDPOINT_OPCUA = f"opc.tcp://{HOST_OPCUA}:{PORTA_OPCUA}/ic/"
NAMESPACE_OPCUA = "urn:gateway"


# Servidor web acessivel pela rede
HOST_WEB = "0.0.0.0"
PORTA_WEB = 5001


# Comunicacao com os CLPs Siemens
# Deixe False enquanto estiver sem o equipamento
HABILITAR_CLP = True

# Parametros de conexao padrao do S7-1200
CLP_RACK = 0
CLP_SLOT = 1


# Configuracoes gerais das regras
INTERVALO_PADRAO_MS = 200

# Tamanho maximo do tipo STRING Siemens
MAX_STRING = 254
