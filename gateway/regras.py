
import ipaddress
import math
import queue
import re
import sqlite3
import struct
import threading
import time

from contextlib import contextmanager

import config
from clp import ComunicacaoCLP
from mqtt import ServicoMQTT
from opcua import ServicoOPCUA


# Protocolos, direcoes e tipos aceitos pelo gateway
TIPOS = {"REAL", "INT", "BOOL", "STRING"}
PROTOCOLOS = {"MQTT", "OPCUA"}
DIRECOES = {"SERVIDOR_PARA_CLP", "CLP_PARA_SERVIDOR"}

# Tempo maximo de espera de uma mensagem na fila
IDADE_MAXIMA_MENSAGEM = 2.0

# Campos armazenados para cada regra no banco SQLite
COLUNAS = (
    "protocolo", "direcao", "porta", "topico",
    "parametro", "tipo", "ip_clp", "memoria",
    "tamanho_string", "intervalo_ms", "ativo"
)


# ============================================================
# VALIDACAO DOS DADOS E ENDERECOS
# ============================================================

# Verifica se o valor recebido corresponde ao tipo configurado
def conferir_valor(tipo, valor, tamanho_string=32):

    if tipo == "BOOL":
        return isinstance(valor, bool)

    if tipo == "INT":
        # INT Siemens utiliza 16 bits com sinal
        return type(valor) is int and -32768 <= valor <= 32767

    if tipo == "REAL":
        # REAL Siemens utiliza ponto flutuante de 32 bits
        if type(valor) not in (int, float) or not math.isfinite(valor):
            return False

        try:
            struct.pack(">f", valor)
            return True
        except (OverflowError, struct.error):
            return False

    if tipo == "STRING":
        # Nesta implementacao, usamos codificacao latin-1
        if not isinstance(valor, str) or len(valor) > tamanho_string:
            return False

        try:
            return len(valor.encode("latin-1")) <= tamanho_string
        except UnicodeEncodeError:
            return False

    return False


# Interpreta um endereco de memoria e determina os bytes utilizados
def endereco_memoria(endereco, tipo, direcao, tamanho_string):
    endereco = endereco.upper().strip()
    leitura = direcao == "CLP_PARA_SERVIDOR"

    # BOOL ocupa apenas um bit de um byte
    if tipo == "BOOL":
        prefixo = "[MQ]" if leitura else "M"
        resultado = re.fullmatch(rf"({prefixo})(\d+)\.([0-7])", endereco)

        if resultado:
            area, byte, bit = resultado.groups()
            return area, int(byte), 1, int(bit)

    else:
        # REAL, INT e STRING ocupam varios bytes
        prefixos = {"REAL": "MD", "INT": "MW", "STRING": "MB"}

        if tipo not in prefixos:
            raise ValueError(f"Tipo de dado invalido: {tipo}")

        resultado = re.fullmatch(rf"{prefixos[tipo]}(\d+)", endereco)

        if resultado:
            byte = int(resultado.group(1))

            tamanhos = {
                "REAL": 4,
                "INT": 2,
                "STRING": tamanho_string + 2
            }

            return "M", byte, tamanhos[tipo], None

    raise ValueError(f"Endereco {endereco!r} incompativel com {tipo} e {direcao}.")


# Valida os dados recebidos do formulario da interface
def validar_regra(entrada):
    protocolo = str(entrada.get("protocolo", "")).upper().strip()
    direcao = str(entrada.get("direcao", "")).upper().strip()
    tipo = str(entrada.get("tipo", "")).upper().strip()
    topico = str(entrada.get("topico", "")).strip()
    parametro = str(entrada.get("parametro", "")).strip()
    memoria = str(entrada.get("memoria", "")).upper().strip()
    ip_clp = str(entrada.get("ip_clp", "")).strip()

    # Confere protocolo, direcao e tipo
    if protocolo not in PROTOCOLOS:
        raise ValueError("Protocolo invalido.")

    if direcao not in DIRECOES:
        raise ValueError("Direcao invalida.")

    if tipo not in TIPOS:
        raise ValueError("Tipo de dado invalido.")

    # MQTT usa topicos, enquanto OPC UA usa nomes logicos de nos
    if not topico or len(topico) > 200:
        raise ValueError("Topico ou identificador do no invalido.")

    if not parametro or len(parametro) > 80:
        raise ValueError("Parametro invalido.")

    if protocolo == "MQTT":
        if "#" in topico or "+" in topico or "\x00" in topico:
            raise ValueError("Informe um topico MQTT exato, sem curingas.")

    if protocolo == "OPCUA":
        if "\x00" in topico or topico.startswith("ns="):
            raise ValueError("Informe o nome logico do no OPC UA, sem ns=.")

    # Confere se o IP informado pertence a um formato valido
    try:
        ip = ipaddress.ip_address(ip_clp)

        if ip.version != 4:
            raise ValueError("Utilize um endereco IPv4 para o CLP.")

    except ValueError as erro:
        raise ValueError("IP do CLP invalido ou nao suportado.") from erro

    # Converte os campos numericos da interface
    try:
        tamanho_string = int(entrada.get("tamanho_string", 32))
        intervalo_ms = int(entrada.get("intervalo_ms", config.INTERVALO_PADRAO_MS))

        porta_padrao = config.PORTA_MQTT if protocolo == "MQTT" else config.PORTA_OPCUA
        porta = int(entrada.get("porta", porta_padrao))

    except (TypeError, ValueError, OverflowError) as erro:
        raise ValueError("Porta, tamanho STRING e intervalo devem ser inteiros validos.") from erro

    if not 1 <= tamanho_string <= config.MAX_STRING:
        raise ValueError(f"Tamanho STRING deve estar entre 1 e {config.MAX_STRING}.")

    if not 50 <= intervalo_ms <= 60000:
        raise ValueError("Intervalo deve estar entre 50 e 60000 ms.")

    # Cada protocolo usa a porta do seu servidor permanente
    if porta != porta_padrao:
        raise ValueError(f"O servico {protocolo} utiliza a porta {porta_padrao}.")

    # Confere endereco de memoria e tamanho da regiao utilizada
    area, byte, tamanho, bit = endereco_memoria(memoria, tipo, direcao, tamanho_string)

    if byte > 65535 or byte + tamanho > 65536:
        raise ValueError("Endereco fora do limite permitido.")

    if area == "Q" and tipo != "BOOL":
        raise ValueError("A leitura de saidas Q aceita apenas BOOL nesta versao.")

    # O estado de ativacao deve ser um booleano verdadeiro
    ativo = entrada.get("ativo", False)

    if not isinstance(ativo, bool):
        raise ValueError("O campo ativo deve ser booleano.")

    # Retorna a regra padronizada para armazenamento e execucao
    return {
        "protocolo": protocolo,
        "direcao": direcao,
        "porta": porta,
        "topico": topico,
        "parametro": parametro,
        "tipo": tipo,
        "ip_clp": ip_clp,
        "memoria": memoria,
        "tamanho_string": tamanho_string,
        "intervalo_ms": intervalo_ms,
        "ativo": ativo
    }


# Detecta se duas regras escrevem na mesma regiao de memoria
def sobrepoe_escritas(a, b):

    # Apenas regras ativas podem disputar escritas
    if not a["ativo"] or not b["ativo"]:
        return False

    if a["direcao"] != "SERVIDOR_PARA_CLP":
        return False

    if b["direcao"] != "SERVIDOR_PARA_CLP":
        return False

    # CLPs diferentes possuem memorias independentes
    if a["ip_clp"] != b["ip_clp"]:
        return False

    area_a, inicio_a, tamanho_a, bit_a = endereco_memoria(a["memoria"], a["tipo"], a["direcao"], a["tamanho_string"])
    area_b, inicio_b, tamanho_b, bit_b = endereco_memoria(b["memoria"], b["tipo"], b["direcao"], b["tamanho_string"])

    if area_a != area_b:
        return False

    # Dois BOOL no mesmo byte so entram em conflito se usam o mesmo bit
    if bit_a is not None and bit_b is not None:
        return inicio_a == inicio_b and bit_a == bit_b

    # Se uma regra utiliza varios bytes, qualquer intersecao e conflito
    return max(inicio_a, inicio_b) < min(inicio_a + tamanho_a, inicio_b + tamanho_b)


# ============================================================
# PERSISTENCIA DAS REGRAS COM SQLITE
# ============================================================

class Persistencia:

    def __init__(self, caminho=None):
        # Caminho do banco definido em config.py
        self.caminho = caminho or config.BANCO_DADOS

        # Protege operacoes simultaneas feitas pela interface
        self.lock = threading.RLock()

        # Cria a tabela caso o banco ainda nao exista
        with self.conexao() as banco:
            banco.execute("""
                CREATE TABLE IF NOT EXISTS regras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    protocolo TEXT NOT NULL,
                    direcao TEXT NOT NULL,
                    porta INTEGER NOT NULL,
                    topico TEXT NOT NULL,
                    parametro TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    ip_clp TEXT NOT NULL,
                    memoria TEXT NOT NULL,
                    tamanho_string INTEGER NOT NULL,
                    intervalo_ms INTEGER NOT NULL,
                    ativo INTEGER NOT NULL DEFAULT 0
                )
            """)

    # Abre uma conexao e garante commit, rollback e fechamento
    @contextmanager
    def conexao(self):
        banco = sqlite3.connect(self.caminho, timeout=5)
        banco.row_factory = sqlite3.Row

        try:
            yield banco
            banco.commit()

        except Exception:
            banco.rollback()
            raise

        finally:
            banco.close()

    # Recupera todas as regras salvas
    def listar(self):
        with self.lock, self.conexao() as banco:
            linhas = banco.execute("SELECT * FROM regras ORDER BY id")

            return [
                dict(linha) | {"ativo": bool(linha["ativo"])}
                for linha in linhas
            ]

    # Insere uma nova regra e retorna seu identificador
    def criar(self, regra):
        with self.lock, self.conexao() as banco:
            colunas = ", ".join(COLUNAS)
            marcadores = ", ".join("?" for _ in COLUNAS)
            valores = [int(regra[c]) if c == "ativo" else regra[c] for c in COLUNAS]

            cursor = banco.execute(f"INSERT INTO regras ({colunas}) VALUES ({marcadores})", valores)
            return cursor.lastrowid

    # Atualiza os dados de uma regra existente
    def atualizar(self, id_regra, regra):
        with self.lock, self.conexao() as banco:
            campos = ", ".join(f"{coluna} = ?" for coluna in COLUNAS)
            valores = [int(regra[c]) if c == "ativo" else regra[c] for c in COLUNAS]

            cursor = banco.execute(f"UPDATE regras SET {campos} WHERE id = ?", valores + [id_regra])
            return cursor.rowcount > 0

    # Remove uma regra do banco
    def remover(self, id_regra):
        with self.lock, self.conexao() as banco:
            cursor = banco.execute("DELETE FROM regras WHERE id = ?", (id_regra,))
            return cursor.rowcount > 0


# ============================================================
# MOTOR DE REGRAS DO GATEWAY
# ============================================================

class MotorRegras:

    def __init__(self):
        # Banco de dados e interfaces de comunicacao
        self.banco = Persistencia()
        self.clp = ComunicacaoCLP()
        self.mqtt = ServicoMQTT(self.receber_mqtt)
        self.opcua = ServicoOPCUA(self.receber_opcua)

        # Protege regras e estados contra acessos simultaneos
        self.lock = threading.RLock()

        # Recupera as regras cadastradas anteriormente
        self.regras = {regra["id"]: regra for regra in self.banco.listar()}

        # Guarda ultimo valor, situacao e erros de cada regra
        self.estados = {}

        # Fila compartilhada para mensagens recebidas dos servidores
        self.fila = queue.Queue(maxsize=2000)

        # Contabiliza mensagens descartadas por fila cheia ou atraso
        self.eventos_descartados = 0

        # Controle de funcionamento das threads
        self.parada = threading.Event()
        self.iniciado = False
        self.threads = []

    # Atualiza as informacoes mostradas na interface web
    def atualizar_estado(self, id_regra, situacao, valor=None, erro=""):
        with self.lock:
            # Nao recria estados de regras que ja foram excluidas
            if id_regra not in self.regras:
                return

            anterior = self.estados.get(id_regra, {})

            self.estados[id_regra] = {
                "situacao": situacao,
                "ultimo_valor": valor if valor is not None else anterior.get("ultimo_valor"),
                "erro": str(erro),
                "atualizado_em": time.time() if valor is not None else anterior.get("atualizado_em")
            }

    # Reune os nos OPC UA necessarios para as regras cadastradas
    def definicoes_opcua(self):
        # No antigo da ESP32 permanece disponivel
        definicoes = {"esp32/distancia": "REAL"}

        for regra in self.regras.values():
            if regra["protocolo"] != "OPCUA":
                continue

            nome = regra["topico"]
            tipo = regra["tipo"]

            # Um mesmo no OPC UA precisa possuir um tipo definido
            if nome in definicoes and definicoes[nome] != tipo:
                raise ValueError(f"No OPC UA {nome} configurado com tipos incompatíveis.")

            definicoes[nome] = tipo

        return definicoes

    # Inicia os dois protocolos e o processamento das regras
    def iniciar(self):
        with self.lock:
            if self.iniciado:
                return

            definicoes = self.definicoes_opcua()

            # O OPC UA e o MQTT ficam ativos independentemente das regras
            self.opcua.iniciar(definicoes)
            self.mqtt.iniciar()

            # Assina os topicos utilizados pelas regras ativas
            self.atualizar_assinaturas()

            self.parada.clear()
            self.iniciado = True

        # Uma thread processa mensagens de entrada
        # Outra consulta periodicamente os CLPs
        self.threads = [
            threading.Thread(target=self.trabalhador, daemon=True),
            threading.Thread(target=self.consultar_clps, daemon=True)
        ]

        for thread in self.threads:
            thread.start()

    # Atualiza os topicos assinados pelo cliente MQTT
    def atualizar_assinaturas(self):
        topicos = {
            regra["topico"]
            for regra in self.regras.values()
            if regra["ativo"]
            and regra["protocolo"] == "MQTT"
            and regra["direcao"] == "SERVIDOR_PARA_CLP"
        }

        self.mqtt.configurar_topicos(topicos)

    # Verifica conflitos de memoria e tipos OPC UA
    def validar_conflitos(self, nova, ignorar_id=None):
        for atual in self.regras.values():

            if atual["id"] == ignorar_id:
                continue

            # Impede escritas sobrepostas no mesmo CLP
            if sobrepoe_escritas(nova, atual):
                raise ValueError(f"Conflito de escrita com a regra {atual['id']}.")

            # Um mesmo no OPC UA nao pode ter dois tipos diferentes
            if nova["protocolo"] == atual["protocolo"] == "OPCUA":
                if nova["topico"] == atual["topico"] and nova["tipo"] != atual["tipo"]:
                    raise ValueError("O mesmo no OPC UA nao pode possuir tipos diferentes.")

        # Mantem o tipo do no antigo usado pelo firmware da ESP32
        if nova["protocolo"] == "OPCUA" and nova["topico"] == "esp32/distancia":
            if nova["tipo"] != "REAL":
                raise ValueError("O no esp32/distancia e reservado para REAL.")

        # Nos ja criados nao podem mudar de tipo durante a execucao
        if self.iniciado and nova["protocolo"] == "OPCUA":
            existente = self.opcua.tipos.get(nova["topico"])

            if existente and existente != nova["tipo"]:
                raise ValueError("No OPC UA ja criado com outro tipo.")

    # Retorna as regras com seus valores e estados atuais
    def listar(self):
        with self.lock:
            resultado = []

            for regra in self.regras.values():
                estado_padrao = {
                    "situacao": "Aguardando dados" if regra["ativo"] else "Desativada",
                    "ultimo_valor": None,
                    "erro": "",
                    "atualizado_em": None
                }

                resultado.append(dict(regra) | self.estados.get(regra["id"], estado_padrao))

            return resultado

    # Cadastra uma regra e salva no SQLite
    def criar(self, entrada):
        nova = validar_regra(entrada)

        with self.lock:
            self.validar_conflitos(nova)

            # Cria o no OPC UA, se for necessario
            if self.iniciado and nova["protocolo"] == "OPCUA":
                self.opcua.garantir_no(nova["topico"], nova["tipo"])

            id_regra = self.banco.criar(nova)
            self.regras[id_regra] = {"id": id_regra} | nova

            self.atualizar_assinaturas()
            return id_regra

    # Edita uma regra existente
    def atualizar(self, id_regra, entrada):
        nova = validar_regra(entrada)

        with self.lock:
            if id_regra not in self.regras:
                raise KeyError("Regra nao encontrada.")

            self.validar_conflitos(nova, ignorar_id=id_regra)

            # Garante a existencia do no OPC UA selecionado
            if self.iniciado and nova["protocolo"] == "OPCUA":
                self.opcua.garantir_no(nova["topico"], nova["tipo"])

            self.banco.atualizar(id_regra, nova)
            self.regras[id_regra] = {"id": id_regra} | nova

            # Limpa o ultimo valor, pois a configuracao mudou
            self.estados.pop(id_regra, None)
            self.atualizar_assinaturas()

    # Exclui uma regra cadastrada
    def remover(self, id_regra):
        with self.lock:
            if id_regra not in self.regras:
                raise KeyError("Regra nao encontrada.")

            self.banco.remover(id_regra)
            del self.regras[id_regra]

            self.estados.pop(id_regra, None)
            self.atualizar_assinaturas()

    # Ativa ou desativa uma regra individualmente
    def ativar(self, id_regra, ativo):
        if not isinstance(ativo, bool):
            raise ValueError("O estado ativo deve ser booleano.")

        with self.lock:
            if id_regra not in self.regras:
                raise KeyError("Regra nao encontrada.")

            nova = dict(self.regras[id_regra], ativo=ativo)
            self.validar_conflitos(nova, ignorar_id=id_regra)

            self.banco.atualizar(id_regra, nova)
            self.regras[id_regra] = nova

            # Nao conserva o ultimo valor de uma ativacao anterior
            self.estados.pop(id_regra, None)

            situacao = "Aguardando dados" if ativo else "Desativada"
            self.atualizar_estado(id_regra, situacao)

            self.atualizar_assinaturas()

    # ========================================================
    # RECEBIMENTO DE DADOS DOS SERVIDORES
    # ========================================================

    # Recebe pacotes JSON do modulo MQTT
    def receber_mqtt(self, topico, pacote):
        self.enfileirar(("MQTT", topico, pacote))

    # Recebe alteracoes de valores nos nos OPC UA
    def receber_opcua(self, nome, valor):
        self.enfileirar(("OPCUA", nome, valor))

    # Registra o instante de chegada e coloca o evento na fila
    def enfileirar(self, evento):
        try:
            instante = time.monotonic()
            self.fila.put_nowait((instante, evento))

        except queue.Full:
            self.eventos_descartados += 1
            print("Fila cheia: uma atualizacao foi descartada.")

    # Processa os eventos recebidos por MQTT ou OPC UA
    def trabalhador(self):
        while not self.parada.is_set():

            try:
                instante, evento = self.fila.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                protocolo, origem, pacote = evento

                # Descarta mensagens que ficaram tempo demais na fila
                if time.monotonic() - instante > IDADE_MAXIMA_MENSAGEM:
                    self.eventos_descartados += 1
                    continue

                # Procura regras ativas que correspondem ao evento
                with self.lock:
                    regras = [
                        dict(regra)
                        for regra in self.regras.values()
                        if regra["ativo"]
                        and regra["protocolo"] == protocolo
                        and regra["direcao"] == "SERVIDOR_PARA_CLP"
                        and regra["topico"] == origem
                    ]

                # Uma mensagem pode alimentar varias regras
                for regra in regras:
                    try:
                        # Confirma que a regra nao foi editada ou desativada
                        with self.lock:
                            atual = self.regras.get(regra["id"])

                            if atual is None or not atual["ativo"] or atual != regra:
                                continue

                        if protocolo == "MQTT":
                            # MQTT transporta o pacote JSON com varios dados
                            if not isinstance(pacote, dict):
                                raise ValueError("Mensagem MQTT deve ser um objeto JSON.")

                            dados = pacote.get("dados")

                            if not isinstance(dados, dict):
                                raise ValueError("JSON deve conter o objeto 'dados'.")

                            dado = dados.get(regra["parametro"])

                            if not isinstance(dado, dict):
                                raise ValueError(f"Parametro {regra['parametro']} ausente.")

                            if dado.get("tipo") != regra["tipo"]:
                                raise ValueError("Tipo recebido diferente do configurado.")

                            valor = dado.get("valor")

                        else:
                            # OPC UA transporta diretamente o valor do no
                            valor = pacote

                        # Confere o tipo e os limites antes de escrever
                        if not conferir_valor(regra["tipo"], valor, regra["tamanho_string"]):
                            raise ValueError("Valor fora dos limites do tipo definido.")

                        if config.HABILITAR_CLP:
                            # Escrita fisica na memoria do CLP
                            self.clp.escrever(regra, valor)
                            self.atualizar_estado(regra["id"], "Encaminhado", valor)

                        else:
                            # Permite acompanhar dados sem equipamento
                            self.atualizar_estado(regra["id"], "CLP desabilitado (sem escrita)", valor)

                    except Exception as erro:
                        self.atualizar_estado(regra["id"], "Erro", erro=erro)

            finally:
                # Informa que o evento foi retirado da fila
                self.fila.task_done()

    # ========================================================
    # LEITURA DOS CLPS E PUBLICACAO NOS SERVIDORES
    # ========================================================

    # Consulta os CLPs conforme o intervalo de cada regra
    def consultar_clps(self):
        ultima_consulta = {}

        while not self.parada.wait(0.02):

            # Sem hardware, nao tenta estabelecer conexoes Snap7
            if not config.HABILITAR_CLP:
                continue

            agora = time.monotonic()

            # Seleciona as regras de leitura atualmente ativas
            with self.lock:
                regras = [
                    dict(regra)
                    for regra in self.regras.values()
                    if regra["ativo"]
                    and regra["direcao"] == "CLP_PARA_SERVIDOR"
                ]

            for regra in regras:
                id_regra = regra["id"]

                # Respeita o intervalo configurado para cada regra
                if agora - ultima_consulta.get(id_regra, 0) < regra["intervalo_ms"] / 1000:
                    continue

                ultima_consulta[id_regra] = agora

                try:
                    # Verifica se a regra permanece ativa e inalterada
                    with self.lock:
                        atual = self.regras.get(id_regra)

                        if atual is None or not atual["ativo"] or atual != regra:
                            continue

                    # Le o valor do endereco indicado na regra
                    valor = self.clp.ler(regra)

                    if not conferir_valor(regra["tipo"], valor, regra["tamanho_string"]):
                        raise ValueError("Leitura incompativel com a regra.")

                    if regra["protocolo"] == "MQTT":
                        # Construi o JSON padrao utilizado no gateway
                        pacote = {
                            "dispositivo": f"clp_{regra['ip_clp']}",
                            "dados": {
                                regra["parametro"]: {
                                    "tipo": regra["tipo"],
                                    "valor": valor
                                }
                            }
                        }

                        self.mqtt.publicar(regra["topico"], pacote)

                    else:
                        # Atualiza diretamente a variavel OPC UA
                        self.opcua.publicar(regra["topico"], regra["tipo"], valor)

                    self.atualizar_estado(id_regra, "Publicado", valor)

                except Exception as erro:
                    self.atualizar_estado(id_regra, "Erro", erro=erro)

    # ========================================================
    # ESTADO GERAL E ENCERRAMENTO
    # ========================================================

    # Retorna a disponibilidade dos servicos para o Flask
    def servicos(self):
        return {
            "mqtt": self.mqtt.conectado,
            "opcua": self.opcua.rodando,
            "clp_habilitado": config.HABILITAR_CLP,
            "eventos_descartados": self.eventos_descartados
        }

    # Encerra as threads e os servicos de comunicacao
    def encerrar(self):
        self.parada.set()

        for thread in self.threads:
            thread.join(timeout=2)

        self.mqtt.parar()
        self.opcua.parar()
        self.clp.encerrar()

        self.iniciado = False
