
import json
import threading
import paho.mqtt.client as mqtt

import config


class ServicoMQTT:

    def __init__(self, receber_dados):
        # Funcao do motor de regras que recebera as mensagens
        self.receber_dados = receber_dados

        # Cria o cliente que se conectara ao broker Mosquitto
        self.cliente = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="gateway_ic"
        )

        # Define as funcoes executadas nos eventos MQTT
        self.cliente.on_connect = self.ao_conectar
        self.cliente.on_disconnect = self.ao_desconectar
        self.cliente.on_message = self.ao_receber

        # Guarda os topicos utilizados pelas regras ativas
        self.topicos = set()

        # Guarda o estado da comunicacao
        self.conectado = False
        self.iniciado = False

        # Protege as configuracoes contra acessos simultaneos
        self.lock = threading.RLock()

        # Configura tentativas automaticas de reconexao
        self.cliente.reconnect_delay_set(min_delay=1, max_delay=10)

    # Executada automaticamente quando conecta ao broker
    def ao_conectar(self, cliente, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            with self.lock:
                self.conectado = False

            print(f"Falha na conexao MQTT: {reason_code}")
            return

        with self.lock:
            self.conectado = True

            # Reinscreve os topicos apos uma reconexao
            for topico in self.topicos:
                cliente.subscribe(topico, qos=1)

        print("MQTT conectado ao broker!")

    # Executada automaticamente quando perde ou encerra a conexao
    def ao_desconectar(self, cliente, userdata, disconnect_flags, reason_code, properties):
        with self.lock:
            self.conectado = False

        print(f"MQTT desconectado: {reason_code}")

    # Executada quando chega uma mensagem em um topico assinado
    def ao_receber(self, cliente, userdata, mensagem):
        try:
            if mensagem.retain:
                print(f"Mensagem MQTT retida ignorada: {mensagem.topic}")
                return

            # Converte os bytes recebidos em texto UTF-8
            texto = mensagem.payload.decode("utf-8")

            # Transforma o JSON em um dicionario Python
            pacote = json.loads(texto)

            if not isinstance(pacote, dict):
                raise ValueError("A mensagem MQTT deve ser um objeto JSON.")

            # O formato padrao exige o campo dados
            dados = pacote.get("dados")

            if not isinstance(dados, dict):
                raise ValueError("O JSON deve conter o objeto 'dados'.")

            # Envia o pacote ao motor, que selecionara os parametros
            self.receber_dados(mensagem.topic, pacote)

        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as erro:
            print(f"Mensagem MQTT invalida no topico {mensagem.topic}: {erro}")

        except Exception as erro:
            print(f"Erro ao processar MQTT no topico {mensagem.topic}: {erro}")

    # Inicia a conexao MQTT sem bloquear o servidor web
    def iniciar(self):
        if self.iniciado:
            return

        # Agenda a conexao com o broker configurado
        self.cliente.connect_async(config.BROKER_MQTT, config.PORTA_MQTT)

        # O loop em segundo plano processa mensagens e reconexoes
        self.cliente.loop_start()

        self.iniciado = True
        print("Servico MQTT iniciado.")

    # Atualiza as assinaturas quando as regras forem modificadas
    def configurar_topicos(self, novos_topicos):
        novos_topicos = set(novos_topicos)

        with self.lock:
            # Descobre quais topicos foram adicionados ou removidos
            adicionar = novos_topicos - self.topicos
            remover = self.topicos - novos_topicos

            self.topicos = novos_topicos

            if not self.conectado:
                return

            # Remove assinaturas que nao sao mais necessarias
            for topico in remover:
                self.cliente.unsubscribe(topico)

            # Assina novos topicos sem reiniciar o MQTT
            for topico in adicionar:
                self.cliente.subscribe(topico, qos=1)

    # Publica um pacote JSON no topico escolhido
    def publicar(self, topico, pacote):
        with self.lock:
            conectado = self.conectado

        if not conectado:
            raise ConnectionError("Broker MQTT desconectado.")

        # Converte o dicionario Python em JSON valido
        mensagem = json.dumps(pacote, ensure_ascii=False, allow_nan=False)

        # Publica com QoS 1 para solicitar confirmacao do broker
        resultado = self.cliente.publish(topico, mensagem, qos=1, retain=False)

        if resultado.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"Falha ao publicar MQTT: {resultado.rc}")

        # Aguarda a confirmacao para nao informar sucesso prematuramente
        resultado.wait_for_publish(timeout=5)

        if not resultado.is_published():
            raise TimeoutError("Tempo limite para confirmar publicacao MQTT.")

    # Encerra a conexao quando o processo do gateway finalizar
    def parar(self):
        if not self.iniciado:
            return

        self.cliente.disconnect()
        self.cliente.loop_stop()

        with self.lock:
            self.conectado = False
            self.iniciado = False

        print("Servico MQTT encerrado.")
