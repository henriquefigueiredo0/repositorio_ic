import asyncio
import threading

from asyncio import Server

funcao_distancia = None
servidor = None
thread_servervidor = None
rodando = False

# Ativa o servidor OPC-UA de forma assincrona
async def servidor_opcua():

    global servidor
    global rodando

    servidor = Server()     # Cria o objeto servidor 
    await servidor.init()   # Inicializa o servidor

    servidor.set_endpoint("opc.tcp://0.0.0.0:4840/ic/")             # Define o endereco do servidor
    indice = await servidor.register_namespace("urn:ic:henrique")   # Registra o namespace do servidor

    objeto = servidor.nodes.objects # Pasta padrao de OPC-UA chamada "Objects"
    