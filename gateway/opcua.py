
import asyncio
import threading
import time

from asyncua import Server, ua

import config


# Relaciona os tipos definidos na interface aos tipos OPC UA
TIPOS_OPCUA = {
    "REAL": ua.VariantType.Double,
    "INT": ua.VariantType.Int16,
    "BOOL": ua.VariantType.Boolean,
    "STRING": ua.VariantType.String
}


# Converte valores Python para o tipo OPC UA correto
def criar_valor_opcua(tipo, valor):
    if tipo not in TIPOS_OPCUA:
        raise ValueError(f"Tipo OPC UA invalido: {tipo}")

    if tipo == "REAL":
        valor = float(valor)

    elif tipo == "INT":
        if type(valor) is not int or not -32768 <= valor <= 32767:
            raise ValueError("INT deve estar entre -32768 e 32767.")

    elif tipo == "BOOL":
        if not isinstance(valor, bool):
            raise ValueError("BOOL deve ser verdadeiro ou falso.")

    elif tipo == "STRING":
        if not isinstance(valor, str):
            raise ValueError("STRING deve ser texto.")

    return ua.Variant(valor, TIPOS_OPCUA[tipo])


# Recebe notificacoes de alteracoes nas variaveis OPC UA
class HandlerOPCUA:

    def __init__(self, receber_dados):
        self.receber_dados = receber_dados

        # Relaciona NodeIds aos nomes usados pelo motor de regras
        self.nomes = {}

        # Identifica notificacoes iniciais das assinaturas
        self.iniciais = set()

        # Registra escritas realizadas pelo proprio gateway
        self.escritas_locais = {}

    # Registra uma escrita local antes de atualizar um no
    def registrar_escrita(self, identificador, valor):
        agora = time.monotonic()
        pendentes = self.escritas_locais.setdefault(identificador, [])

        # Descarta registros antigos para evitar crescimento indefinido
        pendentes[:] = [(v, t) for v, t in pendentes if agora - t < 5]
        pendentes.append((valor, agora))

    # Cancela um registro quando a escrita falha
    def cancelar_escrita(self, identificador, valor):
        pendentes = self.escritas_locais.get(identificador, [])

        for indice, (registrado, instante) in enumerate(pendentes):
            if registrado == valor:
                pendentes.pop(indice)
                break

    # Executada quando o valor de uma variavel e alterado
    def datachange_notification(self, node, valor, data):
        identificador = str(node.nodeid)
        nome = self.nomes.get(identificador)

        if nome is None:
            return

        # A primeira notificacao informa o valor inicial do no
        if identificador not in self.iniciais:
            self.iniciais.add(identificador)
            return

        agora = time.monotonic()
        pendentes = self.escritas_locais.get(identificador, [])
        pendentes[:] = [(v, t) for v, t in pendentes if agora - t < 5]

        # Evita encaminhar novamente uma escrita feita pelo gateway
        for indice, (registrado, instante) in enumerate(pendentes):
            if registrado == valor:
                pendentes.pop(indice)
                return

        # Alteracoes externas sao encaminhadas ao motor de regras
        self.receber_dados(nome, valor)


class ServicoOPCUA:

    def __init__(self, receber_dados):
        # Funcao do motor que recebera os valores OPC UA
        self.receber_dados = receber_dados

        # Objetos utilizados pelo servidor asyncua
        self.servidor = None
        self.loop = None
        self.subscription = None
        self.objeto_dados = None
        self.indice_namespace = None

        # Dicionarios de variaveis existentes no servidor
        self.nos = {}
        self.tipos = {}

        # Estado da thread e do servidor
        self.rodando = False
        self.thread = None
        self.evento_inicio = threading.Event()
        self.evento_parada = threading.Event()
        self.erro_inicio = None

        # Recebe notificacoes de mudancas nos nos
        self.handler = HandlerOPCUA(receber_dados)

    # Cria uma variavel OPC UA com identificador estavel
    async def criar_no(self, nome, tipo):
        # Se o no ja existe, apenas verifica seu tipo
        if nome in self.nos:
            if self.tipos[nome] != tipo:
                raise ValueError(f"No {nome} ja existe com outro tipo.")
            return

        # Define o valor inicial conforme o tipo selecionado
        valores_iniciais = {
            "REAL": 0.0,
            "INT": 0,
            "BOOL": False,
            "STRING": ""
        }

        if tipo not in valores_iniciais:
            raise ValueError(f"Tipo OPC UA invalido: {tipo}")

        valor = criar_valor_opcua(tipo, valores_iniciais[tipo])

        # Preserva o NodeId utilizado pela ESP32 no prototipo
        if nome == "esp32/distancia":
            if tipo != "REAL":
                raise ValueError("esp32/distancia deve ser REAL.")

            nodeid = ua.NodeId(2, self.indice_namespace)

        else:
            # Os demais nos possuem identificadores textuais
            nodeid = ua.NodeId(f"gateway:{nome}", self.indice_namespace)

        # Adiciona a variavel ao servidor e permite escrita externa
        no = await self.objeto_dados.add_variable(nodeid, nome, valor)
        await no.set_writable()

        # Guarda a referencia para consultas e publicacoes futuras
        self.nos[nome] = no
        self.tipos[nome] = tipo
        self.handler.nomes[str(no.nodeid)] = nome

        # Se o servidor ja estiver funcionando, monitora o novo no
        if self.subscription is not None:
            await self.subscription.subscribe_data_change(no)

        print(f"No OPC UA criado: {nome} | {no.nodeid}")

    # Inicializa e mantem o servidor OPC UA funcionando
    async def executar_servidor(self, definicoes):
        try:
            self.loop = asyncio.get_running_loop()

            self.servidor = Server()
            await self.servidor.init()

            # Configura o endereco de acesso ao servidor
            self.servidor.set_endpoint(config.ENDPOINT_OPCUA)

            # Registra o namespace que identifica o gateway
            self.indice_namespace = await self.servidor.register_namespace(config.NAMESPACE_OPCUA)

            # O firmware antigo utiliza o namespace 2
            if self.indice_namespace != 2:
                raise RuntimeError("O namespace OPC UA deve ter indice 2 para manter compatibilidade com a ESP32.")

            # Cria uma pasta logica para organizar as variaveis
            self.objeto_dados = await self.servidor.nodes.objects.add_object(self.indice_namespace, "Gateway")

            # Mantem o no usado pela ESP32
            await self.criar_no("esp32/distancia", "REAL")

            # Cria as demais variaveis recuperadas das regras
            for nome, tipo in definicoes.items():
                await self.criar_no(nome, tipo)

            # Inicia a comunicacao com os clientes OPC UA
            async with self.servidor:
                # Cria uma assinatura para observar alteracoes externas
                self.subscription = await self.servidor.create_subscription(100, self.handler)

                for no in self.nos.values():
                    await self.subscription.subscribe_data_change(no)

                self.rodando = True
                self.evento_inicio.set()

                print("Servidor OPC UA iniciado!")
                print("Endpoint:", config.ENDPOINT_OPCUA)

                # Mantem o servidor ativo ate o encerramento do gateway
                while not self.evento_parada.is_set():
                    await asyncio.sleep(0.1)

        except Exception as erro:
            self.erro_inicio = erro
            print("Erro no servidor OPC UA:", erro)

        finally:
            self.rodando = False
            self.subscription = None
            self.servidor = None
            self.loop = None
            self.evento_inicio.set()

            print("Servidor OPC UA encerrado.")

    # Cria o loop asyncio em uma thread separada
    def executar_thread(self, definicoes):
        asyncio.run(self.executar_servidor(definicoes))

    # Inicia o servidor e aguarda a inicializacao
    def iniciar(self, definicoes=None):
        if self.rodando:
            return

        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("Servidor OPC UA ainda esta encerrando.")

        definicoes = dict(definicoes or {})

        # Reinicia os estados de controle
        self.evento_inicio.clear()
        self.evento_parada.clear()
        self.erro_inicio = None

        self.nos = {}
        self.tipos = {}
        self.handler = HandlerOPCUA(self.receber_dados)

        # Executa o servidor sem bloquear o Flask
        self.thread = threading.Thread(target=self.executar_thread, args=(definicoes,), daemon=True)
        self.thread.start()

        # Aguarda o servidor ficar disponivel
        if not self.evento_inicio.wait(timeout=15):
            self.evento_parada.set()
            raise TimeoutError("Tempo limite ao iniciar servidor OPC UA.")

        if self.erro_inicio is not None:
            raise RuntimeError(f"Falha ao iniciar OPC UA: {self.erro_inicio}") from self.erro_inicio

        if not self.rodando:
            raise RuntimeError("Servidor OPC UA nao iniciou.")

    # Executa uma operacao assincrona na thread do OPC UA
    def executar_operacao(self, operacao):
        if not self.rodando or self.loop is None:
            operacao.close()
            raise RuntimeError("Servidor OPC UA nao esta funcionando.")

        try:
            tarefa = asyncio.run_coroutine_threadsafe(operacao, self.loop)
            return tarefa.result(timeout=10)

        except Exception:
            tarefa.cancel()
            raise

    # Cria novos nos quando uma regra e adicionada pela interface
    def garantir_no(self, nome, tipo):
        return self.executar_operacao(self.criar_no(nome, tipo))

    # Atualiza o valor de uma variavel OPC UA
    async def escrever_no(self, nome, tipo, valor):
        # Confere se o no existe e possui o tipo esperado
        if nome not in self.nos:
            raise ValueError(f"No OPC UA inexistente: {nome}")

        if self.tipos[nome] != tipo:
            raise ValueError("Tipo diferente do configurado no OPC UA.")

        no = self.nos[nome]
        valor_opcua = criar_valor_opcua(tipo, valor)
        identificador = str(no.nodeid)

        # Marca a escrita para nao confundi-la com dados externos
        self.handler.registrar_escrita(identificador, valor_opcua.Value)

        try:
            # Atualiza o valor disponibilizado pelo servidor
            await no.write_value(valor_opcua)

        except Exception:
            self.handler.cancelar_escrita(identificador, valor_opcua.Value)
            raise

    # Publica uma leitura do CLP em um no OPC UA
    def publicar(self, nome, tipo, valor):
        self.executar_operacao(self.escrever_no(nome, tipo, valor))

    # Encerra o servidor quando a aplicacao finalizar
    def parar(self):
        if self.thread is None:
            return

        self.evento_parada.set()
        self.thread.join(timeout=10)

        if self.thread.is_alive():
            raise RuntimeError("Servidor OPC UA nao encerrou.")

        self.thread = None
        self.rodando = False

        print("Servico OPC UA encerrado.")
