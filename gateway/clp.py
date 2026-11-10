import struct
import snap7

from snap7.type import Areas
from config import ip_clp

# Cliente de comunicacao com o CLP
cliente = snap7.client.Client()

# Conecta ao CLP
def conectar():
    if cliente.get_connected():
        return True

    cliente.connect(ip_clp, 0, 1)

    if cliente.get_connected():
        print("CLP conectado!")
        return True

    return False

# Desconecta do CLP
def desconectar():
    if cliente.get_connected():
        cliente.disconnect()

# Le Q0.0 ate Q0.7
def ler_saidas():
    dados = cliente.read_area(Areas.PA, 0, 0, 1)
    byte_q0 = dados[0]

    return [
        (byte_q0 >> bit) & 1
        for bit in range(8)
    ]


# Escreve um bit no byte M0
def escrever_memoria_clp(numero_memoria, valor_memoria):
    if not 0 <= numero_memoria <= 7:
        raise ValueError("Bit de memoria invalido.")

    dados = cliente.read_area(Areas.MK, 0, 0, 1)

    if valor_memoria:
        dados[0] |= 1 << numero_memoria
    else:
        dados[0] &= ~(1 << numero_memoria)

    cliente.write_area(Areas.MK, 0, 0, dados)


# Escreve um REAL na memoria
def escrever_real_clp(byte_inicial, valor):
    dados = bytearray(struct.pack(">f", float(valor)))

    cliente.write_area(
        Areas.MK,
        0,
        byte_inicial,
        dados
    )


# Escreve a distancia em M10 a M13
def escrever_distancia(distancia):
    escrever_real_clp(10, distancia)
