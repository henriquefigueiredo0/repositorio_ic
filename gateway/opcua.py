import asyncio
import threading

from asyncua import Server

funcao_distancia = None
servidor = None
thread_servidor = None
rodando = False

# Classe que recebe a notificacao de que a distancia mudou
class HandlerDistancia:

    def datachange_notification(self, node, valor, data):

        print("Distancia recebida: ", valor, "cm")

        if funcao_distancia is not None:
            funcao_distancia(float(valor))

# Ativa o servidor OPC-UA de forma assincrona
async def servidor_opcua():

    global servidor
    global rodando

    servidor = Server()     # Cria o objeto servidor 
    await servidor.init()   # Inicializa o servidor

    servidor.set_endpoint("opc.tcp://0.0.0.0:4840/ic/")             # Define o endereco do servidor
    indice = await servidor.register_namespace("urn:gateway")       # Registra o namespace do servidor

    objetos = servidor.nodes.objects # Pasta padrao de OPC-UA chamada "Objects"

    esp32 = await objetos.add_object(indice, "ESP32") # Cria um objeto chamado "ESP32" dentro da pasta "Objects"

    distancia = await esp32.add_variable(indice, "Distancia", 0.0) # Cria uma variavel chamada "Distancia" dentro do objeto "ESP32"
    await distancia.set_writable() # Permite que a esp32 escreva nessa variavel
    
    monitor_distancia = HandlerDistancia() # Cria um objeto da classe HandlerDistancia, que recebe a notificacao de que a distancia mudou
    subscription = await servidor.create_subscription(100, monitor_distancia) # Cria uma subscription com periodo de 100ms 
    await subscription.subscribe_data_change(distancia) # Monitora mudancas na variavel "Distancia"


    # Mantem o servidor rodando
    async with servidor:
        rodando = True
        while rodando:
            await asyncio.sleep(1) 

# Funcao que executa o servidor OPC-UA de forma sincrona, para ser chamada em uma thread
def executar_servidor():
    asyncio.run(servidor_opcua()) # Executa a funcao assincrona servidor_opcua() de forma sincrona

# Funcao chamada pelo main caso o protocolo ativo seja OPC-UA
# A funcao "callback_distancia" seria a "escrever_distancia"
def iniciar(callback_distancia):

    global funcao_distancia                 # para modificar a variavel funcao_distancia
    global thread_servidor                  # para modificar a variavel thread_servidor  

    funcao_distancia = callback_distancia   # funcao_distancia deixa de ser None e passa a ser escrever_distancia

    thread_servidor = threading.Thread(target=executar_servidor,daemon=True) # Cria uma thread para rodar o servidor

    thread_servidor.start() # Inicia a thread do servidor

# Para o loop do servidor OPC-UA
def parar():
    global rodando
    rodando = False

      