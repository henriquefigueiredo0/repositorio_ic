#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "open62541.h"

enum Protocolos {MQTT, OPCUA};      // Cria o tipo de protocolo que pode ser MQTT ou OPCUA
Protocolos protocoloAtivo = OPCUA;  // Define qual protocolo vai ser usado

// Wi-Fi do roteador local
const char* ssid = "Caverna_do_Dragao";
const char* senha = "xupafederal";

// IP da TV Box onde está rodando o Mosquitto e o servidor OPC UA
const char* broker = "192.168.15.147";
const int porta_mqtt = 1883;
const char* endpoint_opcua = "opc.tcp://192.168.15.147:4840/ic/";

// Topico em que a ESP vai publicar a distancia
const char* topico_distancia = "ic/esp/distancia";

// Cria os objetos de Wi-Fi e MQTT
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// Cria o cliente OPC UA
UA_Client* clienteOPCUA = nullptr;
bool opcuaConectado = false;

// Identifica a variavel Distancia no servidor OPC UA
UA_NodeId nodeIdDistancia = UA_NODEID_NUMERIC(2, 2);

// Guarda o momento da ultima tentativa de conexao OPC UA
unsigned long ultimaTentativaOPCUA = 0;
const unsigned long intervaloReconexaoOPCUA = 2000;

// Sensor ultrassonico
const int trigPin = 5;
const int echoPin = 18;

// Guarda o momento da ultima medicao
unsigned long ultimaMedicao = 0;

// Funcao que conecta a ESP na rede local
void conectarWifi() {

  Serial.print("Conectando ao Wi-Fi");
  WiFi.begin(ssid, senha);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi conectado!");

  Serial.print("IP da ESP: ");
  Serial.println(WiFi.localIP());
}

// Funcao que conecta a ESP no broker MQTT
void conectarMQTT() {

  while (!mqtt.connected()) {

    Serial.print("Conectando ao MQTT...");

    if (mqtt.connect("ESP32_IC")) {
      Serial.println("conectado!");
    }

    else {
      Serial.print("Erro MQTT: ");
      Serial.println(mqtt.state());
      delay(2000);
    }
  }
}

// Mede a distancia utilizando o sensor ultrassonico
float medirDistancia() {

  // Garante que TRIG começa desligado
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  // Envia pulso de 10 microssegundos
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // Mede quanto tempo o pulso levou para voltar
  long duracao = pulseIn(echoPin, HIGH, 30000);

  // Se não recebeu eco
  if (duracao == 0) {
    return -1;
  }

  // Converte tempo para distancia em centimetros
  float distancia = duracao * 0.0343f / 2.0f;

  return distancia;
}

// Envia a distancia por MQTT
void enviarMQTT(float distancia) {

  char mensagemDistancia[20];

  // Converte a distancia de float para string
  dtostrf(distancia, 1, 2, mensagemDistancia);

  // Publica a distancia no topico MQTT
  mqtt.publish(topico_distancia, mensagemDistancia);
}

// Funcao que conecta a ESP no servidor OPC UA da TV Box
void conectarOPCUA() {

  // Verifica se a ESP está conectada ao Wi-Fi
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  // Guarda o momento da tentativa de conexao
  ultimaTentativaOPCUA = millis();

  Serial.println("Conectando ao servidor OPC UA...");

  // Remove o cliente anterior, caso exista
  if (clienteOPCUA != nullptr) {
    UA_Client_delete(clienteOPCUA);
    clienteOPCUA = nullptr;
  }

  opcuaConectado = false;

  // Cria um novo cliente OPC UA
  clienteOPCUA = UA_Client_new();

  if (clienteOPCUA == nullptr) {
    Serial.println("Erro ao criar cliente OPC UA");
    return;
  }

  // Tenta conectar ao servidor OPC UA
  UA_StatusCode status = UA_Client_connect(clienteOPCUA, endpoint_opcua);

  if (status == UA_STATUSCODE_GOOD) {
    opcuaConectado = true;
    Serial.println("Conectado ao servidor OPC UA!");
  }

  else {
    Serial.printf("Erro de conexao OPC UA: 0x%08lX\n", (unsigned long)status);
    UA_Client_delete(clienteOPCUA);
    clienteOPCUA = nullptr;
  }
}

// Envia a distancia para a variavel Distancia do servidor OPC UA
void enviarOPCUA(float distancia) {

  // Verifica se o cliente OPC UA está conectado
  if (!opcuaConectado || clienteOPCUA == nullptr) {
    return;
  }

  // Converte a distancia para o tipo Double do OPC UA
  UA_Double valor = (UA_Double)distancia;

  // Escreve a distancia no nó do servidor OPC UA
  UA_StatusCode status = UA_Client_writeValueAttribute_scalar(clienteOPCUA, nodeIdDistancia, &valor, &UA_TYPES[UA_TYPES_DOUBLE]);

  if (status == UA_STATUSCODE_GOOD) {
    Serial.printf("Distancia enviada via OPC UA: %.2f cm\n", distancia);
  }

  else {
    Serial.printf("Erro ao enviar OPC UA: 0x%08lX\n", (unsigned long)status);

    // Marca a conexao como perdida para tentar novamente
    opcuaConectado = false;
    UA_Client_delete(clienteOPCUA);
    clienteOPCUA = nullptr;
    ultimaTentativaOPCUA = millis();
  }
}

void setup() {

  Serial.begin(115200);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  conectarWifi();

  // Configura o endereco do broker MQTT
  if (protocoloAtivo == MQTT) {
    mqtt.setServer(broker, porta_mqtt);
  }

  // Conecta ao servidor OPC UA caso esse protocolo esteja ativo
  if (protocoloAtivo == OPCUA) {
    conectarOPCUA();
  }

  Serial.println();
}

void loop() {

  // Mantem a comunicacao MQTT somente quando o protocolo MQTT estiver ativo
  if (protocoloAtivo == MQTT) {

    // Garante que a ESP continua conectada ao MQTT
    if (!mqtt.connected()) {
      conectarMQTT();
    }

    // Mantem a comunicacao em segundo plano
    mqtt.loop();
  }

  // Mantem a comunicacao OPC UA somente quando o protocolo OPC UA estiver ativo
  else if (protocoloAtivo == OPCUA) {

    // Tenta reconectar caso a conexao OPC UA tenha sido perdida
    if (!opcuaConectado) {
      if (millis() - ultimaTentativaOPCUA >= intervaloReconexaoOPCUA) {
        conectarOPCUA();
      }
    }

    // Mantem o cliente OPC UA em funcionamento
    else if (clienteOPCUA != nullptr) {
      UA_StatusCode status = UA_Client_run_iterate(clienteOPCUA, 0);

      if (status != UA_STATUSCODE_GOOD) {
        Serial.printf("Erro na comunicacao OPC UA: 0x%08lX\n", (unsigned long)status);
        opcuaConectado = false;
        UA_Client_delete(clienteOPCUA);
        clienteOPCUA = nullptr;
        ultimaTentativaOPCUA = millis();
      }
    }
  }

  // Realiza uma medicao a cada 300 ms
  if (millis() - ultimaMedicao >= 300) {

    ultimaMedicao = millis();

    float distancia = medirDistancia();

    if (distancia >= 0) {

      Serial.print("Distancia: ");
      Serial.print(distancia);
      Serial.println(" cm");

      // Caso o protocolo seja MQTT
      if (protocoloAtivo == MQTT) {
        enviarMQTT(distancia);
      }

      // Caso o protocolo seja OPC UA
      else if (protocoloAtivo == OPCUA) {
        enviarOPCUA(distancia);
      }
    }

    else {
      Serial.println("Erro na medicao ultrassonica");
    }
  }

  // Libera tempo de CPU para outras tarefas do FreeRTOS
  // Evita o disparo do Task Watchdog
  delay(1);
}