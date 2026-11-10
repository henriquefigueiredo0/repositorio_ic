
import asyncio
import threading

from asyncua import Server
from config import endpoint_opcua, namespace_opcua


# Guarda a funcao que recebe a distancia
funcao_distancia = None

# Guarda o servidor e sua thread
servidor = None
thread_servidor = None

# Controla o funcionamento do servidor
rodando = False
evento_parada = threading.Event()
evento_inicio = threading.Event()

# Guarda possiveis erros de inicializacao
erro_inicio = None


# Recebe notificacoes de mudanca da distancia
class HandlerDistancia:

    def datachange_notification(self, node, valor, data):

        print(f"Distancia recebida: {valor} cm")

        if funcao_distancia is not None:
            funcao_distancia(float(valor))


# Executa o servidor OPC UA
async def servidor_opcua():

    global servidor, rodando, erro_inicio

    try:
        servidor = Server()
        await servidor.init()

        # Configura o endpoint e o namespace
        servidor.set_endpoint(endpoint_opcua)
        indice = await servidor.register_namespace(namespace_opcua)

        # Cria a estrutura de nos da ESP32
        objetos = servidor.nodes.objects
        esp32 = await objetos.add_object(indice, "ESP32")

        distancia = await esp32.add_variable(
            indice, "Distancia", 0.0
        )

        await distancia.set_writable()

        # Inicia o servidor
        async with servidor:

            # Monitora alteracoes da distancia
            monitor = HandlerDistancia()
            subscription = await servidor.create_subscription(
                100, monitor
            )

            await subscription.subscribe_data_change(distancia)

            rodando = True
            evento_inicio.set()

            print("Servidor OPC UA iniciado!")
            print("Endpoint:", endpoint_opcua)
            print("Node ID da distancia:", distancia.nodeid)

            # Mantem o servidor em funcionamento
            while not evento_parada.is_set():
                await asyncio.sleep(0.1)

    except Exception as erro:
        erro_inicio = erro
        print("Erro no servidor OPC UA:", erro)

    finally:
        rodando = False
        servidor = None
        evento_inicio.set()

        print("Servidor OPC UA encerrado.")


# Executa o servidor em uma thread
def executar_servidor():
    asyncio.run(servidor_opcua())


# Inicia o servidor OPC UA
def iniciar(callback_distancia):

    global funcao_distancia
    global thread_servidor, erro_inicio

    # Impede iniciar duas vezes
    if thread_servidor is not None and thread_servidor.is_alive():
        raise RuntimeError("Servidor OPC UA ja esta executando.")

    funcao_distancia = callback_distancia
    erro_inicio = None

    # Reinicia os sinais de controle
    evento_parada.clear()
    evento_inicio.clear()

    thread_servidor = threading.Thread(
        target=executar_servidor,
        daemon=True
    )

    thread_servidor.start()

    # Aguarda a inicializacao do servidor
    if not evento_inicio.wait(timeout=10):
        evento_parada.set()
        thread_servidor.join(timeout=5)
        raise RuntimeError("Tempo limite ao iniciar OPC UA.")

    # Verifica se ocorreu algum erro
    if erro_inicio is not None:
        raise RuntimeError(
            f"Falha ao iniciar OPC UA: {erro_inicio}"
        ) from erro_inicio

    if not rodando:
        raise RuntimeError("Servidor OPC UA nao iniciou.")


# Encerra o servidor OPC UA
def parar():

    global thread_servidor

    if thread_servidor is None:
        return

    # Solicita o encerramento
    evento_parada.set()

    # Aguarda a thread terminar
    thread_servidor.join(timeout=5)

    if thread_servidor.is_alive():
        raise RuntimeError("Servidor OPC UA nao encerrou.")

    thread_servidor = None

    print("OPC UA parado com sucesso.")
