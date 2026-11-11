// Semaforo Inteligente IoT - cruce peatonal en bulevar dividido (dos calzadas + camellon).
// Dos calzadas (2 carriles c/u) separadas por camellon. El peaton cruza en dos
// etapas y el camellon es refugio. Por eso hay DOS semaforos independientes:
// mientras se cruza la calzada 1, la calzada 2 puede seguir en verde.
//
// La inteligencia (vision) corre en la laptop; este sketch es el actuador:
//   - enciende las luces de cada calzada segun lo que manda la PC
//   - lee los botones (banqueta A, banqueta B, camellon) y los reporta
//   - puede generar peatones simulados para probar sin gente real
//
// Protocolo PC -> Arduino (token + salto de linea):
//   G1 Y1 R1 P1 = calzada 1 en VERDE/AMBAR/ROJO/CUENTA
//   G2 Y2 R2 P2 = calzada 2 idem
//   S = activar simulacion (el Arduino suelta peatones)   N = apagarla
// Arduino -> PC:  A / B / M = boton banqueta A / banqueta B / camellon
//                 SA / SB = peaton simulado que cruza A->B / B->A
//                 LISTO al arrancar.
//
// Sin LEDs conectados: el pin 13 integrado refleja "alguna calzada en rojo".

const int C1V = 2, C1A = 3, C1R = 4;     // calzada 1: verde/ambar/rojo
const int C2V = 5, C2A = 6, C2R = 7;     // calzada 2
const int PR = 8, PV = 9;                // peaton rojo/verde
const int BUZ = 10;                      // chicharra
const int BTN_A = A0, BTN_B = A1, BTN_M = A2;   // botones (pull-up)

char e1 = 'G', e2 = 'G';
char buf[8]; int bi = 0;
bool sim = false; unsigned long tSim = 0; bool ladoSim = false;
const unsigned long INTERVALO_SIM = 6000;
unsigned long tBuz = 0; bool parp = false;

bool prevA = HIGH, prevB = HIGH, prevM = HIGH;
unsigned long tA = 0, tB = 0, tM = 0;
const unsigned long REBOTE = 40;

bool detenida(char e) { return e == 'R' || e == 'P'; }

void aplicar() {
  digitalWrite(C1V, e1 == 'G');  digitalWrite(C1A, e1 == 'Y');  digitalWrite(C1R, detenida(e1));
  digitalWrite(C2V, e2 == 'G');  digitalWrite(C2A, e2 == 'Y');  digitalWrite(C2R, detenida(e2));
  bool algunRojo = detenida(e1) || detenida(e2);
  digitalWrite(LED_BUILTIN, algunRojo);
  digitalWrite(PV, algunRojo);          // peaton puede cruzar si alguna calzada esta detenida
  digitalWrite(PR, !algunRojo);
}

void token(char *t) {
  if ((t[0] == 'G' || t[0] == 'Y' || t[0] == 'R' || t[0] == 'P') && (t[1] == '1' || t[1] == '2')) {
    if (t[1] == '1') e1 = t[0]; else e2 = t[0];
    aplicar();
  } else if (t[0] == 'S' && t[1] == 0) {
    sim = true; tSim = millis();
  } else if (t[0] == 'N' && t[1] == 0) {
    sim = false;
  }
}

void setup() {
  int outs[] = {C1V, C1A, C1R, C2V, C2A, C2R, PR, PV, BUZ, LED_BUILTIN};
  for (int i = 0; i < 10; i++) pinMode(outs[i], OUTPUT);
  pinMode(BTN_A, INPUT_PULLUP); pinMode(BTN_B, INPUT_PULLUP); pinMode(BTN_M, INPUT_PULLUP);
  Serial.begin(9600);
  aplicar();
  Serial.println("LISTO");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (bi) { buf[bi] = 0; token(buf); bi = 0; }
    } else if (bi < 6) {
      buf[bi++] = c;
    }
  }

  unsigned long ahora = millis();

  // chicharra: lenta si cruza, rapida en cuenta regresiva
  bool cruce = detenida(e1) || detenida(e2);
  bool cuenta = (e1 == 'P' || e2 == 'P');
  if (cruce) {
    unsigned long periodo = cuenta ? 250 : 650;
    if (ahora - tBuz > periodo) { tBuz = ahora; parp = !parp; if (parp) tone(BUZ, cuenta ? 1600 : 1200, 70); }
    if (cuenta) digitalWrite(PV, parp);
  } else {
    noTone(BUZ);
  }

  // generador de peatones simulados (lo controla el Arduino)
  if (sim && ahora - tSim > INTERVALO_SIM) {
    tSim = ahora; ladoSim = !ladoSim;
    Serial.println(ladoSim ? "SA" : "SB");
  }

  // botones con antirrebote
  bool a = digitalRead(BTN_A);
  if (a != prevA && ahora - tA > REBOTE) { tA = ahora; prevA = a; if (a == LOW) Serial.println("A"); }
  bool b = digitalRead(BTN_B);
  if (b != prevB && ahora - tB > REBOTE) { tB = ahora; prevB = b; if (b == LOW) Serial.println("B"); }
  bool m = digitalRead(BTN_M);
  if (m != prevM && ahora - tM > REBOTE) { tM = ahora; prevM = m; if (m == LOW) Serial.println("M"); }
}
