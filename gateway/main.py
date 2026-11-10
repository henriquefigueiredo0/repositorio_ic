import threading
import time

import mqtt
import opcua
import controle_esp
import config


# Estado do gateway
protocolo_ativo = None
gateway_ativo = False

# Ultima medicao
ultima_distancia = None
instante_ultima_distancia = None
sequencia_distancia = 0

# Estado do CLP
status_clp = "Nao monitorado"
estado_bomba = None

# Protege as operacoes
controle = threading.Lock()
controle_dados = threading.Lock()

# Controla a thread do CLP
thread_clp = None
evento_parada_clp = threading.Event()

# Limite para considerar dados recentes
TEMPO_LIMITE = 2.5


# Recebe a distancia da ESP32
def receber_distancia(distancia):
    global ultima_distancia
    global instante_ultima_distancia
    global sequencia_distancia

    with controle_dados:
        ultima_distancia = float(distancia)
        instante_ultima_distancia = time.monotonic()
        sequencia_distancia += 1

    print(f"Distancia recebida: {distancia:.2f} cm")


# Limpa a medicao armazenada
def limpar_distancia():
    global ultima_distancia
    global instante_ultima_distancia

    with controle_dados:
        ultima_distancia = None
        instante_ultima_distancia = None


# Atualiza o estado do CLP
def atualizar_estado_clp(status, bomba=None):
    global status_clp, estado_bomba

    with controle_dados:
        status_clp = status
        estado_bomba = bomba


# Executa a comunicacao com o CLP
def executar_clp():
    import clp

    ultima_sequencia_enviada = -1

    while not evento_parada_clp.is_set():

        try:
            # Conecta caso necessario
            if not clp.cliente.get_connected():
                atualizar_estado_clp("Conectando")
                clp.conectar()
                ultima_sequencia_enviada = -1

            if not clp.cliente.get_connected():
                raise ConnectionError("CLP nao conectado.")

            # Copia a ultima medicao
            with controle_dados:
                distancia = ultima_distancia
                instante = instante_ultima_distancia
                sequencia = sequencia_distancia

            # Envia somente dados recentes e novos
            recente = (
                instante is not None
                and time.monotonic() - instante <= TEMPO_LIMITE
            )

            if (
                distancia is not None
                and recente
                and sequencia != ultima_sequencia_enviada
                and not evento_parada_clp.is_set()
            ):
                clp.escrever_distancia(distancia)
                ultima_sequencia_enviada = sequencia

            # Le a saida que representa a bomba
            if evento_parada_clp.is_set():
                break

            saidas = clp.ler_saidas()
            bit = config.bit_bomba

            if not 0 <= bit <= 7:
                raise ValueError("Bit da bomba invalido.")

            bomba = "Ligada" if saidas[bit] else "Desligada"

            atualizar_estado_clp("Conectado", bomba)

            # Evita consultas excessivas
            evento_parada_clp.wait(0.2)

        except Exception as erro:
            print("Erro de comunicacao com CLP:", erro)
            atualizar_estado_clp("Desconectado")

            try:
                clp.desconectar()
            except Exception as erro_desconexao:
                print("Erro ao desconectar CLP:", erro_desconexao)

            ultima_sequencia_enviada = -1

            # Tenta reconectar posteriormente
            evento_parada_clp.wait(2)

    try:
        clp.desconectar()
    except Exception as erro:
        print("Erro ao encerrar CLP:", erro)

    atualizar_estado_clp("Nao monitorado")


# Inicia a thread de comunicacao com o CLP
def iniciar_clp():
    global thread_clp

    if not config.habilitar_clp:
        atualizar_estado_clp("Nao monitorado")
        return

    evento_parada_clp.clear()
    atualizar_estado_clp("Conectando")

    thread_clp = threading.Thread(
        target=executar_clp,
        daemon=True
    )

    thread_clp.start()


# Encerra a thread do CLP
def parar_clp():
    global thread_clp

    if thread_clp is None:
        atualizar_estado_clp("Nao monitorado")
        return True

    evento_parada_clp.set()
    thread_clp.join(timeout=5)

    if thread_clp.is_alive():
        print("Thread do CLP ainda esta encerrando.")
        atualizar_estado_clp("Encerrando")
        return False

    thread_clp = None
    atualizar_estado_clp("Nao monitorado")
    return True


# Para um receptor de distancia
def parar_receptor(protocolo):
    if protocolo == "MQTT":
        mqtt.parar()
    elif protocolo == "OPCUA":
        opcua.parar()


# Inicia o gateway
def iniciar_gateway(protocolo):
    global protocolo_ativo, gateway_ativo

    with controle:

        if gateway_ativo:
            print("Gateway ja esta ativo.")
            return False

        if thread_clp is not None and thread_clp.is_alive():
            print("CLP ainda esta encerrando.")
            return False

        if protocolo not in ("MQTT", "OPCUA"):
            print("Protocolo invalido.")
            return False

        limpar_distancia()

        # Inicia o receptor na TV Box
        try:
            if protocolo == "MQTT":
                mqtt.iniciar(receber_distancia)
            else:
                opcua.iniciar(receber_distancia)

        except Exception as erro:
            print("Erro ao iniciar receptor:", erro)

            try:
                parar_receptor(protocolo)
            except Exception as erro_limpeza:
                print("Erro na limpeza:", erro_limpeza)

            return False

        # Solicita que a ESP32 transmita
        try:
            controle_esp.enviar_comando(protocolo)

        except Exception as erro:
            print("Erro ao comandar ESP32:", erro)

            try:
                controle_esp.enviar_comando("PARAR")
            except Exception:
                pass

            try:
                parar_receptor(protocolo)
            except Exception as erro_limpeza:
                print("Erro na limpeza:", erro_limpeza)

            limpar_distancia()
            return False

        protocolo_ativo = protocolo
        gateway_ativo = True

        # Inicia o monitoramento do CLP
        iniciar_clp()

        print("Gateway iniciado:", protocolo)
        return True


# Para o gateway
def parar_gateway():
    global protocolo_ativo, gateway_ativo

    with controle:

        if not gateway_ativo:
            print("Gateway ja esta parado.")
            return False

        # Primeiro manda a ESP32 parar
        try:
            controle_esp.enviar_comando("PARAR")

        except Exception as erro:
            print("Erro ao enviar PARAR:", erro)
            return False

        # Depois encerra o receptor
        try:
            parar_receptor(protocolo_ativo)

        except Exception as erro:
            print("Erro ao parar receptor:", erro)
            return False

        # Encerra o monitoramento do CLP
        clp_parado = parar_clp()

        if not clp_parado:
            print("Aguardando encerramento do CLP.")
            return False

        gateway_ativo = False
        protocolo_ativo = None
        limpar_distancia()

        print("Gateway parado.")
        return True


# Retorna o estado para a interface
def obter_estado():

    with controle:
        ativo = gateway_ativo
        protocolo = protocolo_ativo

        with controle_dados:
            distancia = ultima_distancia
            instante = instante_ultima_distancia
            status_atual_clp = status_clp
            bomba = estado_bomba

    # Verifica a idade da medicao
    recente = (
        instante is not None
        and time.monotonic() - instante <= TEMPO_LIMITE
    )

    if not ativo:
        status_esp = "Parada"
        distancia = None

    elif recente:
        status_esp = "Recebendo dados"

    else:
        status_esp = "Aguardando dados"
        distancia = None

    return {
        "ativo": ativo,
        "protocolo": protocolo,
        "status_esp": status_esp,
        "distancia": distancia,
        "status_clp": status_atual_clp,
        "estado_bomba": bomba
    }


if __name__ == "__main__":
    print("Modulo do gateway carregado.")
