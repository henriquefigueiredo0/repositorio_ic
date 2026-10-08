#include <WiFi.h>
#include <PubSubClient.h>

// Wi-Fi do roteador local
const char* ssid = "Henrique_IC";
const char* senha = "henrique";

// IP do PC onde está rodando o Mosquitto
const char* broker = "192.168.0.123";
const int porta_mqtt = 1883;

// Topicos que a ESP vai se inscrever
const char* topico_distancia = "ic/esp/distancia";

// Cria os objetos
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// Para o ultrassonico
const int trigPin = 5;
const int echoPin = 18;

// Guarda o momento da última medição
unsigned long ultimaMedicao = 0;

// Funcao que conecta a esp na rede local
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

  // Converte tempo para distância em centímetros
  float distancia = duracao * 0.0343 / 2;

  return distancia;
}

void setup() {

  Serial.begin(115200);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  conectarWifi();                     // Chama a funcao que conecta a ESP na rede local
  mqtt.setServer(broker, porta_mqtt); // Diz para a ESP onde esta o broker MQTT

  Serial.println();
 
}


void loop() {

  // Garante que a ESP continua conectada ao MQTT
  if (!mqtt.connected()) {
    conectarMQTT();
  }

  // Funcao que mantem a comunicacao em segundo plano
  mqtt.loop();

  if (millis() - ultimaMedicao >= 300) {   // Acontece a cada tantos segundos sem parar o resto do programa

    ultimaMedicao = millis();
    float distancia = medirDistancia();

    if (distancia >= 0) {

      Serial.print("Distancia: ");
      Serial.print(distancia);
      Serial.println(" cm");

      // Converte float para texto
      char mensagemDistancia[20];
      dtostrf(distancia, 1, 2, mensagemDistancia);

      // Publica via MQTT
      mqtt.publish(topico_distancia, mensagemDistancia);
    }

    else {
      Serial.println("Erro na medicao ultrassonica");
    }
  }
}