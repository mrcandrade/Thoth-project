/*
 * servo_scan.ino — Diagnóstico de mapeamento de pinos dos servos (HACKberry / Nano)
 * Projeto Thoth — UFRGS
 *
 * Testa UM pino por vez: anuncia pela serial (115200) e faz o servo varrer
 * ~35°..115°..35°. Observe a mão e veja QUAL dedo se move em cada pino.
 * Use para descobrir onde está o servo dos "três dedos" se ele não responder no D6.
 *
 * Abra o monitor serial:
 *   arduino-cli monitor -p COM16 -c baudrate=115200
 */

#include <Servo.h>

// Pinos candidatos (PWM/IO comuns na placa Mk2). D5=indicador, D9=polegar (conhecidos).
const uint8_t PINS[] = {3, 5, 6, 9, 10, 11};
const uint8_t N = sizeof(PINS) / sizeof(PINS[0]);

Servo s;

void sweep(uint8_t pin) {
  s.attach(pin);
  for (int a = 35; a <= 115; a += 5) { s.write(a); delay(25); }
  for (int a = 115; a >= 35; a -= 5) { s.write(a); delay(25); }
  s.write(35);
  delay(150);
  s.detach();   // libera o pino antes do proximo
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println(F("=== SERVO SCAN: observe qual dedo se move em cada pino ==="));
}

void loop() {
  for (uint8_t i = 0; i < N; i++) {
    Serial.print(F(">>> Testando pino D"));
    Serial.println(PINS[i]);
    sweep(PINS[i]);
    delay(2500);   // pausa para voce anotar qual dedo mexeu
  }
  Serial.println(F("--- reiniciando varredura ---"));
}
