
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "open62541.h"

// Estados possiveis da comunicacao
enum Protocolos { PARADO, MQTT, OPCUA };

Protocolos protocoloAtivo = PARADO;
Protocolos protocoloDesejado = PARADO;

// Configuracoes da rede local
const char* ssid = "Caverna_do_Dragao";
const char* senha = "xupafederal";

// Endereco dos servicos da TV Box
const char* broker = "192.168.0.123";
const int porta_mqtt = 1883;
const char* endpoint_opcua = "opc.tcp://192.168.0.123:4840/ic/";

// Topicos MQTT
const char* topico_distancia = "ic/esp/distancia";
const char* topico_protocolo = "ic/esp/protocolo";

// Cliente MQTT
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// Cliente OPC UA
UA_Client* clienteOPCUA = nullptr;
bool opcuaConectado = false;

// Identifica a variavel de distancia
UA_NodeId nodeIdDistancia = UA_NODEID_NUMERIC(2, 2);

// Controle de reconexao
unsigned long ultimaTentativaMQTT = 0;
unsigned long ultimaTentativaOPCUA = 0;
unsigned long ultimaTentativaWiFi = 0;

const unsigned long intervaloReconexao = 2000;

// Sensor ultrassonico
const int trigPin = 5;
const int echoPin = 18;

// Controle das medicoes
unsigned long ultimaMedicao = 0;
const unsigned long intervaloMedicao = 300;


// Conecta a ESP32 ao Wi-Fi
void conectarWifi() {

    Serial.print("Conectando ao Wi-Fi");
    WiFi.begin(ssid, senha);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.println();
    Serial.print("IP da ESP32: ");
    Serial.println(WiFi.localIP());
}


// Recebe comandos pelo topico MQTT
void receberComandoMQTT(char* topico, byte* payload,
                       unsigned int tamanho) {

    if (strcmp(topico, topico_protocolo) != 0) {
        return;
    }

    String comando = "";

    // Converte a mensagem recebida em texto
    for (unsigned int i = 0; i < tamanho; i++) {
        comando += (char)payload[i];
    }

    comando.trim();

    Serial.print("Comando recebido: ");
    Serial.println(comando);

    // Escolhe o protocolo desejado
    if (comando == "MQTT") {
        protocoloDesejado = MQTT;
    }

    else if (comando == "OPCUA") {
        protocoloDesejado = OPCUA;
    }

    else if (comando == "PARAR") {
        protocoloDesejado = PARADO;
    }

    else {
        Serial.println("Comando invalido.");
    }
}


// Tenta conectar ao broker MQTT
void conectarMQTT() {

    if (WiFi.status() != WL_CONNECTED || mqtt.connected()) {
        return;
    }

    // Limita a frequencia das tentativas
    if (millis() - ultimaTentativaMQTT < intervaloReconexao) {
        return;
    }

    ultimaTentativaMQTT = millis();

    Serial.println("Conectando ao broker MQTT...");

    if (mqtt.connect("ESP32_IC")) {

        Serial.println("MQTT conectado!");

        // Escuta o canal de configuracao
        mqtt.subscribe(topico_protocolo);
    }

    else {
        Serial.print("Erro MQTT: ");
        Serial.println(mqtt.state());
    }
}


// Mede a distancia com o sensor ultrassonico
float medirDistancia() {

    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);

    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    // Aguarda o retorno do pulso
    long duracao = pulseIn(echoPin, HIGH, 30000);

    if (duracao == 0) {
        return -1;
    }

    // Converte o tempo em centimetros
    return duracao * 0.0343f / 2.0f;
}


// Publica a distancia via MQTT
void enviarMQTT(float distancia) {

    if (!mqtt.connected()) {
        return;
    }

    char mensagem[20];

    dtostrf(distancia, 1, 2, mensagem);

    mqtt.publish(topico_distancia, mensagem);
}


// Encerra a conexao OPC UA
void desconectarOPCUA() {

    if (clienteOPCUA != nullptr) {
        UA_Client_disconnect(clienteOPCUA);
        UA_Client_delete(clienteOPCUA);
        clienteOPCUA = nullptr;
    }

    opcuaConectado = false;
}


// Conecta ao servidor OPC UA
void conectarOPCUA() {

    if (WiFi.status() != WL_CONNECTED) {
        return;
    }

    ultimaTentativaOPCUA = millis();

    // Descarta uma conexao anterior
    desconectarOPCUA();

    clienteOPCUA = UA_Client_new();

    if (clienteOPCUA == nullptr) {
        Serial.println("Erro ao criar cliente OPC UA.");
        return;
    }

    Serial.println("Conectando ao OPC UA...");

    UA_StatusCode status =
        UA_Client_connect(clienteOPCUA, endpoint_opcua);

    if (status == UA_STATUSCODE_GOOD) {
        opcuaConectado = true;
        Serial.println("OPC UA conectado!");
    }

    else {
        Serial.printf(
            "Erro OPC UA: 0x%08lX\n",
            (unsigned long)status
        );

        desconectarOPCUA();
    }
}


// Envia a distancia via OPC UA
void enviarOPCUA(float distancia) {

    if (!opcuaConectado || clienteOPCUA == nullptr) {
        return;
    }

    UA_Double valor = (UA_Double)distancia;

    UA_StatusCode status =
        UA_Client_writeValueAttribute_scalar(
            clienteOPCUA,
            nodeIdDistancia,
            &valor,
            &UA_TYPES[UA_TYPES_DOUBLE]
        );

    if (status == UA_STATUSCODE_GOOD) {
        Serial.printf(
            "Distancia OPC UA: %.2f cm\n",
            distancia
        );
    }

    else {
        Serial.println("Erro ao enviar distancia OPC UA.");
        desconectarOPCUA();
    }
}


// Aplica a troca de protocolo
void atualizarProtocolo() {

    if (protocoloDesejado == protocoloAtivo) {
        return;
    }

    // Encerra OPC UA quando deixa de utiliza-lo
    if (protocoloAtivo == OPCUA) {
        desconectarOPCUA();
    }

    protocoloAtivo = protocoloDesejado;

    if (protocoloAtivo == PARADO) {
        Serial.println("Transmissao parada.");
    }

    else if (protocoloAtivo == MQTT) {
        Serial.println("Protocolo ativo: MQTT");
    }

    else if (protocoloAtivo == OPCUA) {
        Serial.println("Protocolo ativo: OPC UA");

        // Permite uma tentativa imediata de conexao
        ultimaTentativaOPCUA =
            millis() - intervaloReconexao;
    }
}


// Configuracao inicial da ESP32
void setup() {

    Serial.begin(115200);

    pinMode(trigPin, OUTPUT);
    pinMode(echoPin, INPUT);

    conectarWifi();

    // Configura o MQTT para receber comandos
    mqtt.setServer(broker, porta_mqtt);
    mqtt.setCallback(receberComandoMQTT);

    // Inicia sem transmitir medicoes
    protocoloAtivo = PARADO;
    protocoloDesejado = PARADO;

    ultimaTentativaMQTT =
        millis() - intervaloReconexao;

    Serial.println("ESP32 aguardando comando.");
}


// Executa continuamente
void loop() {

    // Recupera a conexao Wi-Fi
    if (WiFi.status() != WL_CONNECTED) {

        if (millis() - ultimaTentativaWiFi >=
            intervaloReconexao) {

            ultimaTentativaWiFi = millis();
            WiFi.reconnect();
        }
    }

    else {

        // Mantem o MQTT de configuracao conectado
        if (!mqtt.connected()) {
            conectarMQTT();
        }

        else {
            mqtt.loop();
        }
    }

    // Aplica comandos recebidos
    atualizarProtocolo();

    // Mantem o cliente OPC UA funcionando
    if (protocoloAtivo == OPCUA) {

        if (!opcuaConectado) {

            if (millis() - ultimaTentativaOPCUA >=
                intervaloReconexao) {

                conectarOPCUA();
            }
        }

        else if (clienteOPCUA != nullptr) {

            UA_StatusCode status =
                UA_Client_run_iterate(clienteOPCUA, 0);

            if (status != UA_STATUSCODE_GOOD) {
                desconectarOPCUA();
                ultimaTentativaOPCUA = millis();
            }
        }
    }

    // Mede somente quando existe protocolo ativo
    if (protocoloAtivo != PARADO &&
        millis() - ultimaMedicao >= intervaloMedicao) {

        ultimaMedicao = millis();

        float distancia = medirDistancia();

        if (distancia >= 0) {

            Serial.printf(
                "Distancia: %.2f cm\n",
                distancia
            );

            if (protocoloAtivo == MQTT) {
                enviarMQTT(distancia);
            }

            else if (protocoloAtivo == OPCUA) {
                enviarOPCUA(distancia);
            }
        }

        else {
            Serial.println("Erro na medicao.");
        }
    }

    delay(1);
}
