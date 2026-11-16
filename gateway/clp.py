
import re
import struct
import threading

import snap7
from snap7.type import Areas

import config

class ComunicacaoCLP:

    def __init__(self):
        # Guarda as conexoes abertas, identificadas pelo IP do CLP
        self.clientes = {}

        # Cada CLP possui um lock para impedir acessos simultaneos
        self.locks = {}

        # Protege a criacao e remocao das conexoes
        self.lock_geral = threading.RLock()

    # Obtem uma conexao existente ou cria uma nova
    def obter_cliente(self, ip):
        with self.lock_geral:
            if ip not in self.clientes:
                self.clientes[ip] = snap7.client.Client()
                self.locks[ip] = threading.RLock()

            return self.clientes[ip]

    # Conecta ao CLP informado pela regra
    def conectar(self, ip):
        cliente = self.obter_cliente(ip)

        if cliente.get_connected():
            return cliente

        # Rack e slot configurados para o S7-1200
        cliente.connect(ip, config.CLP_RACK, config.CLP_SLOT)

        if not cliente.get_connected():
            raise ConnectionError(f"Nao foi possivel conectar ao CLP {ip}.")

        print(f"CLP conectado: {ip}")
        return cliente

    # Remove uma conexao que apresentou erro
    def desconectar(self, ip):
        with self.lock_geral:
            cliente = self.clientes.get(ip)

            if cliente is None:
                return

            lock = self.locks[ip]

        with lock:
            if cliente.get_connected():
                cliente.disconnect()

    # Interpreta o endereco de memoria informado pelo usuario
    def interpretar_endereco(self, memoria, tipo, direcao):
        memoria = memoria.strip().upper()
        tipo = tipo.upper()

        # BOOL ocupa um unico bit dentro de um byte
        if tipo == "BOOL":
            resultado = re.fullmatch(r"([MQ])(\d+)\.([0-7])", memoria)

            if resultado is None:
                raise ValueError(f"Endereco BOOL invalido: {memoria}")

            area, byte, bit = resultado.groups()

            # Nunca permitimos escrever diretamente nas saidas
            if area == "Q" and direcao != "CLP_PARA_SERVIDOR":
                raise ValueError("A escrita em saidas Q nao e permitida.")

            return area, int(byte), int(bit)

        # Os demais tipos usam enderecos que iniciam em M
        prefixos = {
            "REAL": "MD",
            "INT": "MW",
            "STRING": "MB"
        }

        if tipo not in prefixos:
            raise ValueError(f"Tipo de dado invalido: {tipo}")

        resultado = re.fullmatch(rf"{prefixos[tipo]}(\d+)", memoria)

        if resultado is None:
            raise ValueError(f"Endereco invalido para {tipo}: {memoria}")

        return "M", int(resultado.group(1)), None

    # Seleciona a area de memoria utilizada pelo Snap7
    def obter_area(self, area):
        if area == "M":
            return Areas.MK

        if area == "Q":
            return Areas.PA

        raise ValueError(f"Area de memoria nao suportada: {area}")

    # Converte um valor Python para bytes utilizados pelo Siemens
    def codificar_valor(self, tipo, valor, tamanho_string):
        if tipo == "REAL":
            if type(valor) not in (int, float):
                raise ValueError("REAL deve ser um numero.")

            # REAL Siemens utiliza IEEE 754 de 32 bits
            return bytearray(struct.pack(">f", float(valor)))

        if tipo == "INT":
            if type(valor) is not int or not -32768 <= valor <= 32767:
                raise ValueError("INT deve estar entre -32768 e 32767.")

            # INT Siemens utiliza 16 bits com sinal
            return bytearray(struct.pack(">h", valor))

        if tipo == "STRING":
            if not isinstance(valor, str):
                raise ValueError("STRING deve conter texto.")

            if not 1 <= tamanho_string <= config.MAX_STRING:
                raise ValueError("Tamanho de STRING invalido.")

            # A representacao STRING utiliza dois bytes de cabecalho:
            # primeiro o tamanho maximo, depois o comprimento atual
            # Converte o texto para a codificacao utilizada nesta implementacao
            try:
                texto = valor.encode("latin-1")
            except UnicodeEncodeError as erro:
                raise ValueError("A STRING possui caracteres nao suportados.") from erro

            if len(texto) > tamanho_string:
                raise ValueError("Texto maior que a memoria reservada.")

            dados = bytearray(tamanho_string + 2)
            dados[0] = tamanho_string
            dados[1] = len(texto)
            dados[2:2 + len(texto)] = texto

            return dados

        raise ValueError(f"Tipo nao suportado: {tipo}")

    # Converte os bytes recebidos do CLP para um valor Python
    def decodificar_valor(self, tipo, dados, tamanho_string):
        if tipo == "REAL":
            return struct.unpack(">f", dados)[0]

        if tipo == "INT":
            return struct.unpack(">h", dados)[0]

        if tipo == "STRING":
            # O cabecalho informa quantos caracteres sao validos
            tamanho_maximo = dados[0]
            comprimento = dados[1]

            if tamanho_maximo != tamanho_string:
                raise ValueError("Tamanho STRING diferente do configurado.")

            if comprimento > tamanho_maximo:
                raise ValueError("Comprimento STRING invalido no CLP.")

            return bytes(dados[2:2 + comprimento]).decode("latin-1")

        raise ValueError(f"Tipo nao suportado: {tipo}")

    # Escreve um valor na memoria M do CLP
    def escrever(self, regra, valor):
        if not config.HABILITAR_CLP:
            raise RuntimeError("Comunicacao com CLP desabilitada.")

        ip = regra["ip_clp"]
        tipo = regra["tipo"]
        memoria = regra["memoria"]
        tamanho_string = regra.get("tamanho_string", 32)

        if regra["direcao"] != "SERVIDOR_PARA_CLP":
            raise ValueError("A regra nao permite escrita no CLP.")

        area, byte, bit = self.interpretar_endereco(memoria, tipo, regra["direcao"])

        if area != "M":
            raise ValueError("A escrita e permitida apenas na memoria M.")

        # Serializa as operacoes destinadas ao mesmo CLP
        self.obter_cliente(ip)

        with self.locks[ip]:
            try:
                cliente = self.conectar(ip)

                if tipo == "BOOL":
                    if not isinstance(valor, bool):
                        raise ValueError("BOOL deve ser verdadeiro ou falso.")

                    # Le o byte para preservar os outros sete bits
                    dados = cliente.read_area(Areas.MK, 0, byte, 1)

                    if valor:
                        dados[0] |= 1 << bit
                    else:
                        dados[0] &= ~(1 << bit)

                else:
                    dados = self.codificar_valor(tipo, valor, tamanho_string)

                # Escreve os bytes na area de memoria configurada
                cliente.write_area(Areas.MK, 0, byte, dados)

            except Exception:
                self.desconectar(ip)
                raise

    # Le um valor da memoria M ou de uma saida Q
    def ler(self, regra):
        if not config.HABILITAR_CLP:
            raise RuntimeError("Comunicacao com CLP desabilitada.")

        ip = regra["ip_clp"]
        tipo = regra["tipo"]
        memoria = regra["memoria"]
        tamanho_string = regra.get("tamanho_string", 32)

        if regra["direcao"] != "CLP_PARA_SERVIDOR":
            raise ValueError("A regra nao permite leitura do CLP.")

        area, byte, bit = self.interpretar_endereco(memoria, tipo, regra["direcao"])

        # Define quantos bytes serao lidos
        if tipo == "BOOL":
            tamanho = 1
        elif tipo == "INT":
            tamanho = 2
        elif tipo == "REAL":
            tamanho = 4
        elif tipo == "STRING":
            tamanho = tamanho_string + 2
        else:
            raise ValueError("Tipo de dado invalido.")

        self.obter_cliente(ip)

        with self.locks[ip]:
            try:
                cliente = self.conectar(ip)

                # Le a area MK (memoria) ou PA (saida)
                dados = cliente.read_area(self.obter_area(area), 0, byte, tamanho)

                if tipo == "BOOL":
                    # Extrai somente o bit solicitado
                    return bool(dados[0] & (1 << bit))

                return self.decodificar_valor(tipo, dados, tamanho_string)

            except Exception:
                self.desconectar(ip)
                raise

    # Encerra todas as conexoes ao desligar o gateway
    def encerrar(self):
        with self.lock_geral:
            ips = list(self.clientes.keys())

        for ip in ips:
            try:
                self.desconectar(ip)
            except Exception as erro:
                print(f"Erro ao desconectar CLP {ip}: {erro}")

        with self.lock_geral:
            self.clientes.clear()
            self.locks.clear()

        print("Conexoes Snap7 encerradas.")
