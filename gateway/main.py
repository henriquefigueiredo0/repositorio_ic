import clp
import mqtt
import time

from config import protocolo_ativo

def main():

    # Conecta ao CLP
    if not clp.conectar():
        print("Nao foi possivel iniciar o programa.")
        return

    if (protocolo_ativo == "MQTT"): 
        mqtt.iniciar(clp.escrever_distancia)
    # elif (protocolo_ativo == "OPC-UA"): 
        # opcua.iniciar(clp.escrever_distancia)
    else: 
        print("Protocolo ativo invalido. Escolha MQTT ou OPC-UA.")
        clp.desconectar()
        return

    try:
        # Mantem o programa principal rodando
        while True:
            time.sleep(1)

    # Para o programa quando apertar Ctrl+C
    except KeyboardInterrupt:
        print("Encerrando programa...")

    # Encerra as comunicacoes
    finally:
        
        if (protocolo_ativo == "MQTT"): mqtt.parar()
        # elif (protocolo_ativo == "OPC-UA"): opcua.parar()

        clp.desconectar()

        print("Programa encerrado.")

# So executa o main se o arquivo for executado diretamente
if __name__ == "__main__":
    main()