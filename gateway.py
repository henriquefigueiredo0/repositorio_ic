import paho.mqtt.client as mqtt
import snap7
from snap7.type import Areas
import time

# Define os parametros de conexão com o broker MQTT
broker = "192.168.0.10"
porta = 1883
topico_bits = "ic/esp/dados"
topico_distancia = "ic/esp/distancia"

# Conexao com o CLP
clp = snap7.client.Client()         # Cria o objeto CLP
clp.connect("192.168.0.1", 0, 1)    # Conecta o CLP

if not clp.get_connected():         # Se o CLP nao conectar, encerra o programa
    print("Deu ruim")
    exit()

# Le Q0 e divide cada valor no vetor "saida"
def ler_saidas (): 
    
    dados = clp.read_area(Areas.PA, 0, 0, 1)    # Area de saidas, DB number, byte inicial, quantidade de bytes
    byte_q0 = dados[0]                  # Pega o byte Q0 inteiro
    saida = []                          # Cria o vetor que guarda as saidas

    for i in range(8):                  # Separa cada bit do byte e coloca cada variavel de saida
        bit = (byte_q0 >> i) & 1        # A saida de Q0.0 fica salva em saida[0] e por ai vai
        saida.append(bit)

    return saida   

# Escreve o valor que quiser na memoria do CLP
def escrever_memoria_clp(numero_memoria, valor_memoria):

    dados_m = clp.read_area(Areas.MK, 0, 0, 1)  # Area de memoria, DB number, byte inicial, quantidade de bytes
    byte_m0 = dados_m[0]                        #Pega o byte M0 inteiro

    if valor_memoria == 1: byte_m0 = byte_m0 | (1 << numero_memoria) # Escreve 1 na memor se passar o valor 1
    else: byte_m0 = byte_m0 & ~(1 << numero_memoria)                 # Escreve 0 na memoria se passar o valor 0

    dados_m[0] = byte_m0                            # Coloca o byte alterado de volta
    clp.write_area(Areas.MK, 0, 0, dados_m)         # Escreve no CLP

    
def quando_conectar(cliente, userdata, flags, reason_code, properties):

    print("Conectado ao broker!")
    cliente.subscribe(topico_bits)           # Inscreve-se no tópico para receber mensagens da ESP sobre os bits
    cliente.subscribe(topico_distancia)      # Inscreve-se no tópico para receber mensagens da ESP sobre a distancia

def quando_receber(cliente, userdata, mensagem):

    dado = mensagem.payload.decode()    # Decodifica o payload da mensagem e deixa em formato string

    # Caso o topico seja o de bits
    if mensagem.topic == topico_bits:

        print("Recebido da ESP:", dado)

        # Verifica se recebeu exatamente 3 bits
        if (len(dado) == 3):

            # Separa os 3 caracteres
            bit1 = int(dado[0])
            bit2 = int(dado[1])
            bit3 = int(dado[2])

            print(dado, "sendo escrito no CLP.")

            # Escreve nos bits de memoria do CLP
            escrever_memoria_clp(1, bit1)
            escrever_memoria_clp(2, bit2)
            escrever_memoria_clp(3, bit3)

            print(dado, "escrito no CLP.")
            print()
            
        else: print("Mensagem invalida. Use algo como 010.")

    # Caso o topico seja o de distancia
    elif mensagem.topic == topico_distancia:

        print("Distancia recebida da ESP:", dado, "cm")
        print()

        distancia = float(dado)  

        # Liga a saida Q0.4 se a distancia for menor que 10cm, caso contrario desliga
        if (distancia < 10): escrever_memoria_clp(4, 1)  
        else: escrever_memoria_clp(4, 0)  

# Cria o objeto cliente MQTT
cliente = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

cliente.on_connect = quando_conectar    # Chama a funcao quando_conectar quando o cliente se conectar ao broker
cliente.on_message = quando_receber     # Chama a funcao quando_receber quando o cliente receber uma mensagem

cliente.connect(broker, porta)          # Conecta ao broker MQTT

try:

    while True:
        cliente.loop_forever()          # Mantem tudo rodando ate apertar Ctrl + C
              
except KeyboardInterrupt:               # Para apertando Ctrl + C
    print("deu")

finally:                                # Termina desconectando o clp
    clp.disconnect()
