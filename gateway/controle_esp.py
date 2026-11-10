
import paho.mqtt.publish as publish

import config


TOPICO_CONTROLE = "ic/esp/protocolo"
COMANDOS_VALIDOS = {"MQTT", "OPCUA", "PARAR"}


def enviar_comando(comando):
    # Verifica se o comando e valido
    if comando not in COMANDOS_VALIDOS:
        raise ValueError(f"Comando invalido: {comando}")

    # Envia o comando ao broker da TV Box
    publish.single(
        topic=TOPICO_CONTROLE,
        payload=comando,
        hostname=config.ip_tvbox,
        port=config.porta_mqtt,
        qos=1,
        retain=False,
    )

    print(f"Comando enviado a ESP32: {comando}")
