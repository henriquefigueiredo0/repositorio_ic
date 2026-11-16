
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "open62541.h"

// Protocolo escolhido no firmware
enum Protocolos { MQTT, OPCUA };
const Protocolos PROTOCOLO_CONFIGURADO = MQTT;

// Configuracoes de rede
const char* ssid = "Caverna_do_Dragao";
const char* senha = "xupafederal";

// Endereco da TV Box
const char* broker = "192.168.15.147";
const int porta_mqtt = 1883;
const char* endpoint_opcua = "opc.tcp://192.168.15.147:4840/ic/";

// Identificacao da origem dos dados
const char* id_dispositivo = "esp32_01";
const char* topico_distancia = "ic/esp/distancia";

// Cliente MQTT
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// Cliente OPC UA
UA_Client* clienteOPCUA = nullptr;
bool opcuaConectado = false;

// No OPC UA da distancia
UA_NodeId nodeIdDistancia = UA_NODEID_NUMERIC(2, 2);

// Sensor ultrassonico
const int trigPin = 5;
const int echoPin = 18;

// Controle de tempo
unsigned long ultimaTentativaWiFi = 0;
unsigned long ultimaTentativaMQTT = 0;
unsigned long ultimaTentativaOPCUA = 0;
unsigned long ultimaMedicao = 0;

const unsigned long intervaloReconexao = 2000;
const unsigned long intervaloMedicao = 300;

// Identifica cada medicao
unsigned long sequencia = 0;


// Conecta ao Wi-Fi
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


// Conecta ao broker MQTT
void conectarMQTT() {

    if (WiFi.status() != WL_CONNECTED || mqtt.connected()) {
        return;
    }

    if (millis() - ultimaTentativaMQTT < intervaloReconexao) {
        return;
    }

    ultimaTentativaMQTT = millis();

    Serial.println("Conectando ao MQTT...");

    if (mqtt.connect(id_dispositivo)) {
        Serial.println("MQTT conectado!");
    }
    else {
        Serial.print("Erro MQTT: ");
        Serial.println(mqtt.state());
    }
}


// Mede a distancia em centimetros
float medirDistancia() {

    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);

    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    long duracao = pulseIn(echoPin, HIGH, 30000);

    if (duracao == 0) {
        return -1;
    }

    return duracao * 0.0343f / 2.0f;
}


// Publica a distancia em JSON
void enviarMQTT(float distancia) {

    if (!mqtt.connected()) {
        return;
    }

    char mensagem[256];

   int tamanho = snprintf(
    mensagem,
    sizeof(mensagem),
    "{\"dispositivo\":\"%s\","
    "\"sequencia\":%lu,"
    "\"timestamp_ms\":%lu,"
    "\"dados\":{\"distancia\":{"
    "\"tipo\":\"REAL\","
    "\"valor\":%.2f}}}",
    id_dispositivo, sequencia, millis(), distancia
);

    if (tamanho < 0 || tamanho >= (int)sizeof(mensagem)) {
        Serial.println("Erro ao montar JSON.");
        return;
    }

    if (mqtt.publish(topico_distancia, mensagem)) {
        Serial.println(mensagem);
    }
    
    else {
        Serial.println("Falha ao publicar MQTT.");
    }
}


// Desconecta do servidor OPC UA
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


// Escreve a distancia no servidor OPC UA
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
        Serial.printf(
            "Erro ao enviar OPC UA: 0x%08lX\n",
            (unsigned long)status
        );

        desconectarOPCUA();
    }
}


// Configuracao inicial
void setup() {

    Serial.begin(115200);

    pinMode(trigPin, OUTPUT);
    pinMode(echoPin, INPUT);

    conectarWifi();

    if (PROTOCOLO_CONFIGURADO == MQTT) {
        mqtt.setServer(broker, porta_mqtt);
        mqtt.setBufferSize(512);
        ultimaTentativaMQTT =
            millis() - intervaloReconexao;

        Serial.println("Protocolo configurado: MQTT");
    }
    else {
        ultimaTentativaOPCUA =
            millis() - intervaloReconexao;

        Serial.println("Protocolo configurado: OPC UA");
    }
}


// Execucao continua
void loop() {

    // Recupera o Wi-Fi
    if (WiFi.status() != WL_CONNECTED) {

        if (millis() - ultimaTentativaWiFi >=
            intervaloReconexao) {

            ultimaTentativaWiFi = millis();
            WiFi.reconnect();
        }

        if (opcuaConectado) {
            desconectarOPCUA();
        }

        delay(10);
        return;
    }

    // Mantem o protocolo configurado conectado
    if (PROTOCOLO_CONFIGURADO == MQTT) {

        if (!mqtt.connected()) {
            conectarMQTT();
        }
        else {
            mqtt.loop();
        }
    }
    else {

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

    // Mede a distancia periodicamente
    if (millis() - ultimaMedicao >= intervaloMedicao) {

        ultimaMedicao = millis();

        float distancia = medirDistancia();

        if (distancia >= 0) {

            sequencia++;

            Serial.printf(
                "Distancia: %.2f cm\n",
                distancia
            );

            if (PROTOCOLO_CONFIGURADO == MQTT) {
                enviarMQTT(distancia);
            }
            else {
                enviarOPCUA(distancia);
            }
        }
        else {
            Serial.println("Erro na medicao.");
        }
    }

    delay(1);
}
