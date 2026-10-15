import snap7
from snap7.type import Areas
import struct

from config import ip_clp

clp = snap7.client.Client() # Cria o objeto CLP

# Funcao que conecta o CLP
def conectar():

    clp.connect(ip_clp, 0, 1)

    # Retorna True se a conexao deu certp
    if clp.get_connected():
        print("CLP conectado!")
        return True

    # Retorna False se a conexao deu ruim
    else:
        print("Erro ao conectar ao CLP")
        return False

# Funcao que desconecta o CLP
def desconectar():

    if clp.get_connected():
        clp.disconnect()

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

# Escreve um numero real (float) na memoria do CLP
def escrever_real_clp(byte_inicial, valor):

    dados = bytearray(struct.pack(">f", valor))
    clp.write_area(Areas.MK, 0, byte_inicial, dados)

# Escreve a distancia recebida da ESP na memoria do CLP (4 bytes: M10 a M13)
def escrever_distancia(distancia):

    escrever_real_clp(10, distancia)