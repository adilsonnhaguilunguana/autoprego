#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>

// Configurações de Wi-Fi
const char* ssid = "SUA_REDE_WIFI";
const char* password = "SUA_SENHA_WIFI";

// Configurações do servidor
const char* serverUrl = "http://SEU_IP:5000";
const char* apiKey = "SUA_CHAVE_API_SECRETA";

// Pinos dos relés (ajuste conforme sua ligação)
const int numReles = 4;
int pinosReles[] = {D1, D2, D5, D6};
bool estadosReles[] = {false, false, false, false};

// Simulação dos sensores PZEM (em um projeto real, conecte os PZEMs)
float voltage1 = 220.0;
float current1 = 0.0;
float power1 = 0.0;
float energy1 = 0.0;
float frequency1 = 60.0;
float pf1 = 0.95;

float voltage2 = 220.0;
float current2 = 0.0;
float power2 = 0.0;
float energy2 = 0.0;
float frequency2 = 60.0;
float pf2 = 0.95;

// Limites de consumo
const int LIMITE_PZEM1 = 1000;
const int LIMITE_PZEM2 = 1000;

void setup() {
  Serial.begin(115200);
  
  // Inicializar relés
  for (int i = 0; i < numReles; i++) {
    pinMode(pinosReles[i], OUTPUT);
    digitalWrite(pinosReles[i], LOW);
  }
  
  // Conectar ao Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Conectando ao Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("Conectado ao Wi-Fi");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Iniciar leituras
  Serial.println("Sistema de Automação Residencial Iniciado");
}

void loop() {
  // Simular leituras dos sensores (substitua por leituras reais do PZEM)
  simularLeiturasSensores();
  
  // Enviar dados para o servidor
  enviarDadosParaServidor();
  
  // Verificar comandos do servidor
  verificarComandosDoServidor();
  
  // Controle automático baseado no consumo
  controlarRelesAutomatico(power1, power2);
  
  delay(5000); // Aguardar 5 segundos entre leituras
}

void simularLeiturasSensores() {
  // Simular variações nos valores (substitua por leituras reais do PZEM)
  voltage1 = 220.0 + random(-5, 5);
  current1 = 0.5 + random(0, 100) / 100.0;
  power1 = voltage1 * current1;
  energy1 += power1 / 3600; // Simular acumulação de energia
  frequency1 = 60.0 + random(-1, 1) / 10.0;
  pf1 = 0.95 + random(-5, 5) / 100.0;
  
  voltage2 = 220.0 + random(-5, 5);
  current2 = 0.8 + random(0, 100) / 100.0;
  power2 = voltage2 * current2;
  energy2 += power2 / 3600;
  frequency2 = 60.0 + random(-1, 1) / 10.0;
  pf2 = 0.92 + random(-5, 5) / 100.0;
}

void enviarDadosParaServidor() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    
    // Criar JSON com os dados
    DynamicJsonDocument doc(1024);
    doc["api_key"] = apiKey;
    
    JsonObject pzem1 = doc.createNestedObject("pzem1");
    pzem1["voltage"] = voltage1;
    pzem1["current"] = current1;
    pzem1["power"] = power1;
    pzem1["energy"] = energy1;
    pzem1["frequency"] = frequency1;
    pzem1["pf"] = pf1;
    pzem1["limite"] = LIMITE_PZEM1;
    
    JsonObject pzem2 = doc.createNestedObject("pzem2");
    pzem2["voltage"] = voltage2;
    pzem2["current"] = current2;
    pzem2["power"] = power2;
    pzem2["energy"] = energy2;
    pzem2["frequency"] = frequency2;
    pzem2["pf"] = pf2;
    pzem2["limite"] = LIMITE_PZEM2;
    
    JsonArray reles = doc.createNestedArray("reles");
    for (int i = 0; i < numReles; i++) {
      JsonObject rele = reles.createNestedObject();
      rele["id"] = i + 1;
      rele["estado"] = estadosReles[i];
    }
    
    String jsonString;
    serializeJson(doc, jsonString);
    
    // Enviar dados para o servidor
    http.begin(client, String(serverUrl) + "/api/dados");
    http.addHeader("Content-Type", "application/json");
    
    int httpCode = http.POST(jsonString);
    
    if (httpCode > 0) {
      String payload = http.getString();
      Serial.println("Dados enviados: " + payload);
    } else {
      Serial.println("Erro no envio: " + String(httpCode));
    }
    
    http.end();
  } else {
    Serial.println("Wi-Fi desconectado");
  }
}

void verificarComandosDoServidor() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    
    http.begin(client, String(serverUrl) + "/api/comandos?api_key=" + String(apiKey));
    int httpCode = http.GET();
    
    if (httpCode == 200) {
      String payload = http.getString();
      DynamicJsonDocument doc(256);
      deserializeJson(doc, payload);
      
      if (doc.containsKey("comando")) {
        String comando = doc["comando"];
        processarComando(comando);
      }
    }
    
    http.end();
  }
}

void processarComando(String comando) {
  if (comando.startsWith("RELE")) {
    int releNum = comando.substring(4, 5).toInt();
    int acao = comando.substring(5).toInt();
    
    if (releNum >= 1 && releNum <= numReles) {
      if (acao == 1) {
        digitalWrite(pinosReles[releNum-1], HIGH);
        estadosReles[releNum-1] = true;
        Serial.println("RELE" + String(releNum) + " LIGADO");
      } else if (acao == 0) {
        digitalWrite(pinosReles[releNum-1], LOW);
        estadosReles[releNum-1] = false;
        Serial.println("RELE" + String(releNum) + " DESLIGADO");
      }
    }
  }
}

void controlarRelesAutomatico(float power1, float power2) {
  // Desligar relés prioritários se o consumo exceder o limite
  if (power1 > LIMITE_PZEM1) {
    for (int i = numReles-1; i >= 0; i--) {
      if (estadosReles[i]) {
        digitalWrite(pinosReles[i], LOW);
        estadosReles[i] = false;
        Serial.println("RELE" + String(i+1) + " DESLIGADO AUTOMATICAMENTE");
        break; // Desliga apenas um relé por vez
      }
    }
  }
  
  if (power2 > LIMITE_PZEM2) {
    for (int i = numReles-1; i >= 0; i--) {
      if (estadosReles[i]) {
        digitalWrite(pinosReles[i], LOW);
        estadosReles[i] = false;
        Serial.println("RELE" + String(i+1) + " DESLIGADO AUTOMATICAMENTE");
        break;
      }
    }
  }
}