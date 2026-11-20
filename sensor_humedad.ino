const int PIN_AO = A0;
const int PIN_RELE = 6;
const int PIN_LED = 8;
const int PIN_BUZZER = 9;

// Calibracion real anterior
const int SECO = 305;
const int MOJADO = 33;

// Umbrales de humedad
const int UMBRAL_ENCENDER = 35;
const int UMBRAL_APAGAR = 55;

// Ajustar segun el comportamiento del rele
const int RELE_ON = LOW;
const int RELE_OFF = HIGH;

// Riego por pulsos: bomba PULSO_MS encendida, ESPERA_MS apagada para que el agua llegue
// al sensor; si sigue bajo UMBRAL_APAGAR, otro pulso.
const unsigned long PULSO_MS = 5000;
const unsigned long ESPERA_MS = 5000;
enum Fase { LIBRE, PULSO, ESPERA };
Fase fase = LIBRE;
unsigned long tFase = 0;

// true: el riego automatico empieza al encender el Arduino.
// false: espera a que lo inicies desde el panel (comando E).
const bool INICIAR_AL_ENCENDER = false;
bool habilitado = INICIAR_AL_ENCENDER;

bool regando = false;

// Control desde el panel web (por serie)
int simPct = -1;  // >=0: humedad simulada en vez del sensor
bool silencio = false;  // buzzer silenciado
int manual = -1;  // -1 auto, 0 forzada apagada, 1 forzada encendida

// Comandos (una linea cada uno): H<n> humedad simulada, R sensor real, A auto, 1 bomba on, 0 bomba off, S silenciar buzzer, V buzzer activo, E iniciar riego automatico, D detenerlo
bool leerComandos() {
  static char buf[8];
  static byte n = 0;
  bool hubo = false;
  while (Serial.available()) {
    char c = Serial.read();
    if (c != '\n' && c != '\r') {
      if (n < sizeof(buf) - 1) buf[n++] = c;
      continue;
    }
    if (n == 0) continue;
    buf[n] = 0;
    n = 0;
    if (buf[0] == 'H') simPct = constrain(atoi(buf + 1), 0, 100);
    else if (buf[0] == 'R') simPct = -1;
    else if (buf[0] == 'A') manual = -1;
    else if (buf[0] == '1') manual = 1;
    else if (buf[0] == '0') manual = 0;
    else if (buf[0] == 'S') silencio = true;
    else if (buf[0] == 'V') silencio = false;
    else if (buf[0] == 'E') habilitado = true;
    else if (buf[0] == 'D') habilitado = false;
    else continue;
    hubo = true;
  }
  return hubo;
}

void setup() {
  Serial.begin(9600);

  pinMode(PIN_RELE, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  digitalWrite(PIN_RELE, RELE_OFF);
  digitalWrite(PIN_LED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  Serial.println("Sistema de riego automatico iniciado");
}

void loop() {
  int raw = analogRead(PIN_AO);

  int pct = simPct >= 0 ? simPct : constrain(
    map(raw, SECO, MOJADO, 0, 100),
    0,
    100
  );

  // Control por pulsos con histeresis (solo si el riego automatico esta iniciado)
  unsigned long ahora = millis();
  if (!habilitado) {
    fase = LIBRE;
  } else if (fase == LIBRE && pct < UMBRAL_ENCENDER) {
    fase = PULSO; tFase = ahora;
  } else if (fase == PULSO && pct >= UMBRAL_APAGAR) {
    fase = LIBRE;
  } else if (fase == PULSO && ahora - tFase >= PULSO_MS) {
    fase = ESPERA; tFase = ahora;
  } else if (fase == ESPERA && ahora - tFase >= ESPERA_MS) {
    if (pct >= UMBRAL_APAGAR) fase = LIBRE;
    else { fase = PULSO; tFase = ahora; }
  }
  regando = (fase == PULSO);

  // Forzado manual desde el panel
  if (manual >= 0) regando = (manual == 1);

  // Control de actuadores
  digitalWrite(PIN_RELE, regando ? RELE_ON : RELE_OFF);
  digitalWrite(PIN_LED, regando ? HIGH : LOW);
  digitalWrite(PIN_BUZZER, regando && !silencio ? HIGH : LOW);

  // Monitor serial
  Serial.print("raw=");
  Serial.print(raw);

  Serial.print("  humedad=");
  Serial.print(pct);
  Serial.print("%");

  Serial.print("  estado=");
  Serial.print(regando ? "REGANDO" : "ESPERANDO");

  Serial.print("  modo=");
  Serial.print(manual >= 0 ? "MANUAL" : simPct >= 0 ? "SIM" : "REAL");

  Serial.print("  silencio=");
  Serial.print(silencio ? 1 : 0);

  Serial.print("  riego=");
  Serial.println(habilitado ? 1 : 0);

  // Espera 100 ms, pero sale antes si llega un comando
  unsigned long t = millis();
  while (millis() - t < 100 && !leerComandos());
}
