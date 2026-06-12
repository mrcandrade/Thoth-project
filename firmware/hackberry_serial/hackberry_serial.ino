/*
 * hackberry_serial.ino — Firmware host-controlled para a MÃO HACKberry (Mk2 / Arduino Nano)
 * Projeto Thoth — UFRGS / Enfitec Jr. / CTA-IF
 *
 * Licença: GPLv3 (deriva do sketch HACKberry de exiii Inc. / Mission ARM Japan).
 *
 * Protocolo serial (ASCII, 115200 8N1, terminador '\n'):
 *   Host -> MCU:
 *     G:<thumb>,<index>,<other>   define angulos absolutos (graus); aplica CLAMP
 *     P:<nome>                    gesto nomeado: OPEN | FIST | POINT | PINCH | SHAKE
 *     S                           STOP seguro = abre a mao (libera objeto)
 *     H                           heartbeat (mantem o watchdog vivo)
 *     ?                           query de status
 *   MCU -> Host:
 *     R                           banner de boot/ready
 *     A:<eco>                     ACK do comando aceito (ex.: A:G  A:P:FIST)
 *     E:<cod>:<msg>               erro (1=range,2=parse,3=wdt,4=cmd)
 *     S:<th>,<idx>,<ot>,<mode>    status (angulos atuais + modo: HOST|SAFE)
 *
 * ATENCAO DE PINAGEM: estes pinos seguem os FATOS do projeto Thoth (manual Mk2).
 * O sketch oficial mission-arm/HACKberry usa outro mapeamento — confira o silk
 * da SUA placa Mk2 V3/V4 antes de compilar e ajuste as constantes de pino.
 */

#include <Servo.h>
#include <avr/wdt.h>     // watchdog de hardware (anti-travamento de software)

// ---------- Pinos dos 3 servos de dedos (conectores rotulados da placa Mk2) ----------
// Padrao do manual (pag. 156): cada servo no header com o nome correspondente.
//   INDEX header -> D5 ; MIDDLE header -> D6 ; THUMB header -> D9.
const uint8_t PIN_THUMB = 9;   // conector THUMB  -> polegar. SEM PPTC!
const uint8_t PIN_INDEX = 5;   // conector INDEX  -> indicador (servo grande). PPTC 500mA
const uint8_t PIN_OTHER = 6;   // conector MIDDLE -> medio+anelar+minimo. PPTC 500mA

// Inversao de sentido por servo (este modelo gira ao contrario: angulo menor = fechado).
// Se um dedo ficar invertido (open fecha / fist abre), alterne o flag dele.
const bool REV_THUMB = true;
const bool REV_INDEX = true;
const bool REV_OTHER = true;

// ---------- Limites de angulo por servo (equivalentes a outThumbMax/Min etc.) ----------
// 0 grau = totalmente ABERTO/ESTENDIDO; valor MAX = totalmente FLEXIONADO/FECHADO.
// CALIBRE estes valores com a SUA mao montada antes de operar com objeto na mao.
// Curso SEGURO (manual usa ~30-150 p/ mao direita). CALIBRE por dedo depois.
// menor = aberto no LOGICO; com REV_* a inversao cuida do sentido fisico.
const int THUMB_MIN = 40,  THUMB_MAX = 140;   // polegar
const int INDEX_MIN = 40,  INDEX_MAX = 140;   // indicador
const int OTHER_MIN = 40,  OTHER_MAX = 140;   // tres dedos

// ---------- Parametros de controle ----------
const uint8_t STEP_BIG   = 8;     // graus/ciclo Index/Other (movimento rapido)
const uint8_t STEP_THUMB = 5;     // graus/ciclo polegar (SEM PPTC -> um pouco mais suave)
const uint16_t TICK_MS   = 20;    // periodo do loop de controle (50 Hz)
const uint16_t WDT_MS    = 1000;  // sem heartbeat por este tempo -> fail-safe = abrir
const uint16_t IDLE_MS   = 800;   // parado neste tempo apos atingir alvo -> detach()

// ---------- Estado ----------
Servo svThumb, svIndex, svOther;
int curThumb, curIndex, curOther;     // angulos atuais (suavizados)
int tgtThumb, tgtIndex, tgtOther;     // angulos alvo
bool attached = false;
bool safeMode = false;                // true apos watchdog/STOP
unsigned long lastHeartbeat = 0;
unsigned long lastTick = 0;
unsigned long reachedAt = 0;          // quando atingiu o alvo (para detach por ociosidade)

// ---------- Buffer de linha serial ----------
char lineBuf[48];
uint8_t lineLen = 0;

// --- utilidades -------------------------------------------------------------
int clampThumb(int a) { return constrain(a, THUMB_MIN, THUMB_MAX); }
int clampIndex(int a) { return constrain(a, INDEX_MIN, INDEX_MAX); }
int clampOther(int a) { return constrain(a, OTHER_MIN, OTHER_MAX); }

// Converte o angulo LOGICO (0=aberto..180=fechado) no angulo FISICO do servo,
// invertendo o sentido quando o servo esta montado ao contrario.
int outAngle(int logical, bool rev) { return rev ? (180 - logical) : logical; }

// Escreve os 3 servos aplicando a inversao de sentido (usado no attach e no tick).
void writeServos() {
  svThumb.write(outAngle(curThumb, REV_THUMB));
  svIndex.write(outAngle(curIndex, REV_INDEX));
  svOther.write(outAngle(curOther, REV_OTHER));
}

void attachAll() {
  if (!attached) {
    svThumb.attach(PIN_THUMB);
    svIndex.attach(PIN_INDEX);
    svOther.attach(PIN_OTHER);
    // re-escreve a posicao atual ANTES de mover, para evitar salto brusco
    writeServos();
    attached = true;
  }
}

void detachAll() {
  if (attached) {
    svThumb.detach();   // corta PWM -> elimina jitter e corrente de holding
    svIndex.detach();
    svOther.detach();
    attached = false;
  }
}

void sendStatus() {
  Serial.print(F("S:"));
  Serial.print(curThumb); Serial.print(',');
  Serial.print(curIndex); Serial.print(',');
  Serial.print(curOther); Serial.print(',');
  Serial.println(safeMode ? F("SAFE") : F("HOST"));
}

// Define alvos absolutos com CLAMP. Retorna false se algum vier fora do range.
bool setTargets(int t, int i, int o) {
  int ct = clampThumb(t), ci = clampIndex(i), co = clampOther(o);
  bool inRange = (ct == t && ci == i && co == o);
  tgtThumb = ct; tgtIndex = ci; tgtOther = co;
  safeMode = false;          // novo comando valido sai do modo seguro
  attachAll();
  reachedAt = 0;
  return inRange;
}

// Gestos nomeados -> resolvem para combinacoes dos limites (sempre dentro do CLAMP).
bool applyGesture(const char* name) {
  if      (!strcmp(name, "OPEN"))  return setTargets(THUMB_MIN, INDEX_MIN, OTHER_MIN);
  else if (!strcmp(name, "FIST"))  return setTargets(THUMB_MAX, INDEX_MAX, OTHER_MAX);
  else if (!strcmp(name, "POINT")) return setTargets(THUMB_MAX, INDEX_MIN, OTHER_MAX); // indicador estendido
  else if (!strcmp(name, "PINCH")) return setTargets(THUMB_MAX, (INDEX_MIN+INDEX_MAX)/2, OTHER_MIN);
  else if (!strcmp(name, "SHAKE")) // "apertar a mao": fecho suave (~70% do curso)
    return setTargets(THUMB_MIN + (THUMB_MAX-THUMB_MIN)*7/10,
                      INDEX_MIN + (INDEX_MAX-INDEX_MIN)*7/10,
                      OTHER_MIN + (OTHER_MAX-OTHER_MIN)*7/10);
  return false; // gesto desconhecido -> trata como erro de comando
}

void goSafeOpen() {            // fail-safe: abre a mao e marca SAFE
  tgtThumb = THUMB_MIN; tgtIndex = INDEX_MIN; tgtOther = OTHER_MIN;
  safeMode = true;
  attachAll();
}

// --- parser de comando ------------------------------------------------------
void handleLine(char* s) {
  if (s[0] == '\0') return;            // ignora linha vazia
  wdt_reset();

  switch (s[0]) {
    case 'H':                          // heartbeat
      lastHeartbeat = millis();
      Serial.println(F("A:H"));
      return;

    case '?':                          // status
      sendStatus();
      return;

    case 'S':                          // STOP seguro
      goSafeOpen();
      Serial.println(F("A:S"));
      return;

    case 'P': {                        // gesto nomeado: "P:FIST"
      if (s[1] != ':') { Serial.println(F("E:2:parse")); return; }
      char* name = s + 2;
      if (applyGesture(name)) { Serial.print(F("A:P:")); Serial.println(name); }
      else                    { Serial.println(F("E:4:cmd")); }
      return;
    }

    case 'G': {                        // angulos: "G:120,30,30"
      if (s[1] != ':') { Serial.println(F("E:2:parse")); return; }
      int t, i, o;
      // sscanf e' pesado mas roda fora do hot-path (so a cada comando)
      if (sscanf(s + 2, "%d,%d,%d", &t, &i, &o) != 3) {
        Serial.println(F("E:2:parse")); return;
      }
      if (setTargets(t, i, o)) Serial.println(F("A:G"));
      else                     Serial.println(F("E:1:range"));  // ainda assim aplica o CLAMP
      return;
    }

    default:
      Serial.println(F("E:4:cmd"));
  }
}

// --- loop de controle nao-bloqueante (slew-rate) ----------------------------
void controlTick() {
  bool moving = false;
  if (curThumb != tgtThumb) { curThumb += constrain(tgtThumb - curThumb, -STEP_THUMB, STEP_THUMB); moving = true; }
  if (curIndex != tgtIndex) { curIndex += constrain(tgtIndex - curIndex, -STEP_BIG,   STEP_BIG);   moving = true; }
  if (curOther != tgtOther) { curOther += constrain(tgtOther - curOther, -STEP_BIG,   STEP_BIG);   moving = true; }

  if (attached) {
    writeServos();
  }

  unsigned long now = millis();
  if (moving) {
    reachedAt = 0;
  } else {
    if (reachedAt == 0) reachedAt = now;
    // anti-stall / anti-jitter: detach apos ficar parado IDLE_MS no alvo
    if (now - reachedAt > IDLE_MS) detachAll();
  }
}

void setup() {
  Serial.begin(115200);
  // posicao inicial segura = mao aberta
  curThumb = tgtThumb = THUMB_MIN;
  curIndex = tgtIndex = INDEX_MIN;
  curOther = tgtOther = OTHER_MIN;
  attachAll();
  lastHeartbeat = millis();
  wdt_enable(WDTO_2S);          // watchdog de HW: se o loop travar > 2s, reseta a placa
  Serial.println(F("R"));       // banner de ready
}

void loop() {
  wdt_reset();
  unsigned long now = millis();

  // 1) leitura serial nao-bloqueante, linha a linha
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      lineBuf[lineLen] = '\0';
      handleLine(lineBuf);
      lineLen = 0;
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineLen = 0;                       // overflow -> descarta a linha (anti-desync)
      Serial.println(F("E:2:parse"));
    }
  }

  // 2) watchdog de heartbeat -> fail-safe = abrir a mao
  if (!safeMode && (now - lastHeartbeat > WDT_MS)) {
    goSafeOpen();
    Serial.println(F("E:3:wdt"));
  }

  // 3) tick de controle a 50 Hz (slew-rate + detach por ociosidade)
  if (now - lastTick >= TICK_MS) {
    lastTick = now;
    controlTick();
  }
}
