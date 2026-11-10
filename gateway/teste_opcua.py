
import time
import opcua


# Recebe a distancia enviada ao servidor
def receber_distancia(distancia):
    print(f"Distancia recebida: {distancia:.2f} cm")


# Testa a inicializacao e parada do servidor
def testar_servidor(numero_teste):

    print(f"\n=== TESTE {numero_teste} ===")

    # Inicia o servidor OPC UA
    opcua.iniciar(receber_distancia)

    try:
        # Mantem o servidor ativo por 5 segundos
        print("Servidor ativo durante 5 segundos...")
        time.sleep(5)

    finally:
        # Encerra o servidor mesmo se ocorrer um erro
        opcua.parar()


# Executa dois ciclos de inicializacao e parada
def main():

    try:
        testar_servidor(1)
        testar_servidor(2)

        print("\nTESTES CONCLUIDOS!")

    except Exception as erro:
        print("\nERRO NO TESTE:", erro)


if __name__ == "__main__":
    main()
