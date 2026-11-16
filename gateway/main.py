
import threading

from regras import MotorRegras


# Guarda a instancia principal do gateway
motor = None

# Protege a inicializacao para nao criar dois motores
controle = threading.RLock()


# Inicializa o motor de regras e os servicos de comunicacao
def iniciar_gateway():
    global motor

    with controle:
        # Evita inicializar os servicos mais de uma vez
        if motor is not None and motor.iniciado:
            return motor

        # Cria o motor, que recupera as regras salvas no SQLite
        if motor is None:
            motor = MotorRegras()

        # Inicia o servidor OPC UA, o cliente MQTT e os trabalhadores
        motor.iniciar()

        print("Gateway industrial iniciado.")
        return motor


# Retorna o motor utilizado pela interface web
def obter_motor():
    with controle:
        if motor is None or not motor.iniciado:
            raise RuntimeError("Gateway ainda nao foi inicializado.")

        return motor


# Retorna as regras cadastradas e os ultimos valores
def listar_regras():
    return obter_motor().listar()


# Cadastra uma nova regra de comunicacao
def criar_regra(dados):
    return obter_motor().criar(dados)


# Atualiza os dados de uma regra existente
def atualizar_regra(id_regra, dados):
    obter_motor().atualizar(id_regra, dados)


# Remove uma regra do gateway e do banco SQLite
def remover_regra(id_regra):
    obter_motor().remover(id_regra)


# Ativa ou desativa uma regra sem afetar as demais
def ativar_regra(id_regra, ativo):
    obter_motor().ativar(id_regra, ativo)


# Consulta a disponibilidade dos servicos de comunicacao
def obter_servicos():
    return obter_motor().servicos()


# Encerra os servicos quando o processo finalizar
def encerrar_gateway():
    global motor

    with controle:
        if motor is None:
            return

        try:
            # Interrompe as threads e fecha as conexoes de comunicacao
            motor.encerrar()
            print("Gateway industrial encerrado.")

        finally:
            motor = None


# Permite iniciar o gateway diretamente para diagnosticos
if __name__ == "__main__":
    print("Inicie o sistema com: python app.py")
