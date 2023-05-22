#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "env.h"
#include <OneWire.h>
#include <DallasTemperature.h>

const char* postEndpoint = API_URL_POST;
const char* getEndpoint = API_URL_GET;

#define ONE_WIRE_BUS 4
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);	

const int fanPin = 22;
const int lightPin = 23;
const int pirPin = 15;
bool pirState;

float generateRandomFloat(float min, float max)
{
    float scale = rand() / (float) RAND_MAX; /* [0, 1.0] */
    return min + scale * (max - min);      /* [min, max] */
}

void setup() {
  sensors.begin();
  Serial.begin(9600);
  pinMode(fanPin, OUTPUT);
  pinMode(lightPin, OUTPUT);
  pinMode(pirPin, INPUT);
  pinMode(ONE_WIRE_BUS, INPUT);

  WiFi.begin(WIFI_USER, WIFI_PASS);
  Serial.println("Connecting");
  while(WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("The Bluetooth Device is Ready to Pair");
  Serial.println("Connected @");
  Serial.print(WiFi.localIP());
}

void loop() {

  // Read temperature
  sensors.requestTemperatures(); 
  Serial.print("Temperature: ");
  float temperature = sensors.getTempCByIndex(0);
  temperature = sensors.getTempCByIndex(0);
  Serial.print(temperature);
  Serial.print((char)176); // shows degrees character
  Serial.print("C  |  "); 
  pirState = digitalRead(pirPin);
  Serial.print("\n");
  Serial.print("");
  Serial.print(pirState);
  Serial.println("");
  
  // POST Request
  if (WiFi.status() == WL_CONNECTED) {   
    
    HTTPClient http;
    String httpResponse;

    // POST REQUEST
    http.begin(postEndpoint);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<1024> postJson; // Empty JSONDocument
    String httpRequestData; // Empty string to store HTTP request data string
    
    postJson["temperature"] = temperature;
    postJson["presence"] = pirState;
    serializeJson(postJson, httpRequestData);

    int postResponseCode = http.POST(httpRequestData);

    if (postResponseCode > 0) {
        Serial.print("Response:");
        Serial.print(postResponseCode);
    }
    else {
        Serial.print("Error: ");
        Serial.println(postResponseCode);
    }
      
    http.end();
      
    // GET REQUEST
    http.begin(getEndpoint);
  
    int httpResponseCode = http.GET();

    if (httpResponseCode > 0) {
        Serial.print("Response:");
        Serial.print(httpResponseCode);
        httpResponse = http.getString();
        Serial.println(httpResponse);
    }
    else {
        Serial.print("Error: ");
        Serial.println(httpResponseCode);
    }
    http.end();

    StaticJsonDocument<1024> getJson;
    DeserializationError jsonError = deserializeJson(getJson, httpResponse);

    if (jsonError) { 
        Serial.print("deserializeJson() failed: ");
        Serial.println(jsonError.c_str());
        return;
    }
      
    bool lightState = getJson["light"];
    bool fanState = getJson["fan"];

    Serial.println("Light:");
    Serial.println(lightState);
    Serial.println("Fan:");
    Serial.println(fanState);

    digitalWrite(fanPin, fanState);
    digitalWrite(lightPin, lightState);
      
    Serial.println("Light and Fan Switched Successfully");
      
    delay(1000);   
  }
  else {
    Serial.println("Not Connected");
  }
}