#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

const char* ap_ssid = "Sim_Var_Dual";

// --- CONFIGURAZIONE PIN ---
#define PIN_CH1 18  // Output 1 (Default / R1)
#define PIN_CH2 19  // Output 2 (Alta Energia / R2)
#define LED_PIN 2   
#define BUTTON_PIN 0 

// --- PARAMETRI SIMULAZIONE ---
volatile double mean_T1 = 250.0;   
volatile double std_T1 = 80.0;     
volatile double mean_Ts = 6950.0;  

// --- PARAMETRI MODALITÀ ---
volatile double prob_ch2 = 0.10;   // Probabilità CH2 (0.0 - 1.0)
bool single_channel_mode = false;  // Se true, usa SOLO CH1 (prob_ch2 ignorata)
bool ts_fixed_mode = false;        

// --- CONFIGURAZIONE SISTEMA ---
unsigned long integration_time_us = 50000; 
bool calibration_mode = false;             

// --- PARAMETRI FISICI ---
volatile double phys_V_pulse = 3.3;    
volatile double phys_R1_mohm = 1000.0; 
volatile double phys_R2_mohm = 100.0;  
volatile double phys_C_pf = 100.0;     
volatile double phys_ADC_Vref = 5.0;   

// --- STATO DEL SISTEMA ---
volatile bool configModeRequest = false; 
bool inConfigMode = false;               

// --- STATISTICHE WELFORD ---
double welford_mean = 0;
double welford_M2 = 0;
long welford_count = 0;

double accum_t1_us = 0; 
double accum_t2_us = 0;
unsigned long integration_start_us = 0;

// --- VARIABILI TEMPORALI ---
double next_T1 = 0;
double next_Ts = 0;
bool next_is_ch2 = false; 
long delay_T1 = 0;
long delay_T2 = 0;

WebServer server(80);
DNSServer dnsServer;

// ============================================================
// --- 1. MATEMATICA ---
// ============================================================

double getGaussian(double mean, double std) {
  if (std <= 0) return mean;
  double u1 = (esp_random() + 1.0) / 4294967297.0;
  double u2 = (esp_random() + 1.0) / 4294967297.0;
  double z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * PI * u2);
  return mean + z0 * std;
}

double getPoissonInterval(double mean) {
  double u = (esp_random() + 1.0) / 4294967297.0;
  return -mean * log(u);
}

void calculateNextPulse() {
  next_T1 = getGaussian(mean_T1, std_T1);
  if (next_T1 < 1.0) next_T1 = 1.0; 

  // DECISIONE CANALE
  if (single_channel_mode) {
      next_is_ch2 = false; // Forza CH1
  } else {
      double p = (esp_random() + 1.0) / 4294967297.0;
      next_is_ch2 = (p < prob_ch2); // Branching basato su probabilità
  }

  if (ts_fixed_mode) {
      next_Ts = mean_Ts; 
  } else {
      next_Ts = getPoissonInterval(mean_Ts);
  }
  
  if (next_Ts <= next_T1) next_Ts = next_T1 + 5.0; 
  
  delay_T1 = (long)next_T1;
  delay_T2 = (long)(next_Ts - next_T1);
}

// ============================================================
// --- 2. INTERFACCIA WEB ---
// ============================================================

void IRAM_ATTR handleButtonPress() { configModeRequest = true; }
void handleCaptive() { server.sendHeader("Location", "http://" + WiFi.softAPIP().toString(), true); server.send(302, "text/plain", "Redirect..."); }

const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE HTML><html lang="it"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sim Dual-LET</title><style>
body{font-family:sans-serif;text-align:center;background:#1a1a1a;color:#eee;padding:10px}
.card{background:#333;max-width:650px;margin:auto;padding:15px;border-radius:10px;box-shadow:0 4px 10px #000}
h2{color:#0f0;margin-bottom:5px} .val{font-weight:bold;color:#0f0} .phys{color:#00e5ff} .warn{color:#ff9800}
input{width:80px;padding:5px;background:#444;border:1px solid #666;color:#fff;text-align:right}
input[type=checkbox]{transform:scale(1.5)}
.row{display:flex;justify-content:space-between;margin:6px 0;align-items:center;font-size:0.9em}
.sect{color:#aaa;font-size:0.85em;text-transform:uppercase;margin-top:15px;border-bottom:1px solid #555}
button{width:100%;padding:12px;background:#d32f2f;color:#fff;border:none;border-radius:5px;font-size:1.1em;cursor:pointer;margin-top:15px}
</style></head><body>
<div class="card">
  <h2>DUAL CHANNEL SIMULATOR</h2>
  <div style="color:#aaa; font-size:0.8em; margin-bottom:10px">Stato: <span id="status" style="color:orange">IN CONFIGURAZIONE (PAUSA)</span></div>
  
  <div class="sect">Modalità Canali</div>
  <div class="row"><span><b>USA SOLO 1 CANALE (CH1)</b></span><input id="sgl" type="checkbox" %SGL%></div>
  <div class="row"><span class="warn">Probabilità CH2 (Se attivo) [%]</span><input id="p2" type="number" step="0.1" value="%P2%"></div>

  <div class="sect">Statistica Eventi</div>
  <div class="row"><span>Media T1 (Durata) [µs]</span><input id="t1" type="number" value="%T1%"></div>
  <div class="row"><span>DevStd T1 (Gauss) [µs]</span><input id="s1" type="number" value="%S1%"></div>
  <div class="row"><span>Media Ts (Intervallo) [µs]</span><input id="ts" type="number" value="%TS%"></div>
  <div class="row"><span><b>Ts COSTANTE (No Poisson)</b></span><input id="fix" type="checkbox" %FIX%></div>

  <div class="sect">Configurazione</div>
  <div class="row"><span>Tempo Integrazione [ms]</span><input id="int" type="number" value="%INT%"></div>
  <div class="row"><span>MODO CALIBRAZIONE (LED ON)</span><input id="cal" type="checkbox" %CAL%></div>
  
  <div class="sect">Parametri Fisici</div>
  <div class="row"><span>Tensione Pulse [V]</span><input id="vp" type="number" step="0.1" value="%VP%"></div>
  <div class="row"><span>R1 (Ch1) [M&Omega;]</span><input id="r1" type="number" value="%R1%"></div>
  <div class="row"><span>R2 (Ch2) [M&Omega;]</span><input id="r2" type="number" value="%R2%"></div>
  
  <div class="sect">Risultati (Ultima Sessione)</div>
  <div class="row"><span>Media Carica:</span><span class="val">%QAVG% pC</span></div>
  <div class="row"><span>Varianza Misurata:</span><span class="val">%QVAR% pC²</span></div>
  
  <div class="sect">Predizione Teorica</div>
  <div class="row"><span>Varianza Attesa:</span><span class="phys" id="qvar_theo">---</span></div>

  <br><button onclick="save()">SALVA E AVVIA (START)</button>
</div>
<script>
function calc() {
  let t1 = parseFloat(document.getElementById('t1').value);
  let s1 = parseFloat(document.getElementById('s1').value);
  let ts = parseFloat(document.getElementById('ts').value);
  let tint_us = parseFloat(document.getElementById('int').value) * 1000;
  let v = parseFloat(document.getElementById('vp').value);
  let r1 = parseFloat(document.getElementById('r1').value);
  let r2 = parseFloat(document.getElementById('r2').value);
  
  let single = document.getElementById('sgl').checked;
  let prob2 = single ? 0.0 : (parseFloat(document.getElementById('p2').value) / 100.0);
  let prob1 = 1.0 - prob2;

  let I1 = (v / r1) * 1000.0; 
  let I2 = (v / r2) * 1000.0;
  
  let n_tot = (1.0 / ts) * tint_us;
  let E_T2 = (s1 * s1) + (t1 * t1);
  
  let var_1 = (I1 * I1) * (n_tot * prob1) * E_T2 * 1e-6;
  let var_2 = (I2 * I2) * (n_tot * prob2) * E_T2 * 1e-6;
  
  document.getElementById('qvar_theo').innerText = (var_1 + var_2).toFixed(2) + " pC²";
}
setTimeout(calc, 500);

function save() {
  let args = "";
  let ids = ['t1','s1','ts','p2','int','vp','r1','r2'];
  ids.forEach(id => { args += "&" + id + "=" + document.getElementById(id).value; });
  args += "&fix=" + (document.getElementById('fix').checked ? 1 : 0);
  args += "&cal=" + (document.getElementById('cal').checked ? 1 : 0);
  args += "&sgl=" + (document.getElementById('sgl').checked ? 1 : 0);
  
  fetch("/set?" + args).then(() => { 
    document.body.innerHTML = "<h1>AVVIO SIMULAZIONE...</h1><h2>LED DI STATO FISSO = RUNNING</h2>"; 
    setTimeout(()=>location.reload(), 1500); 
  });
}
</script></body></html>
)rawliteral";

void handleRoot() {
  String html = String(index_html);
  html.replace("%T1%", String(mean_T1));
  html.replace("%S1%", String(std_T1));
  html.replace("%TS%", String(mean_Ts));
  html.replace("%P2%", String(prob_ch2 * 100.0)); 
  html.replace("%FIX%", ts_fixed_mode ? "checked" : "");
  html.replace("%SGL%", single_channel_mode ? "checked" : ""); 
  html.replace("%INT%", String(integration_time_us / 1000)); 
  html.replace("%CAL%", calibration_mode ? "checked" : "");  
  html.replace("%VP%", String(phys_V_pulse));
  html.replace("%R1%", String(phys_R1_mohm));
  html.replace("%R2%", String(phys_R2_mohm));
  html.replace("%QAVG%", String(welford_mean, 2));
  double var = (welford_count > 1) ? welford_M2 / (welford_count - 1) : 0;
  html.replace("%QVAR%", String(var, 3));
  server.send(200, "text/html", html);
}

void handleSet() {
  if (server.hasArg("t1")) mean_T1 = server.arg("t1").toFloat();
  if (server.hasArg("s1")) std_T1 = server.arg("s1").toFloat();
  if (server.hasArg("ts")) mean_Ts = server.arg("ts").toFloat();
  if (server.hasArg("p2")) prob_ch2 = server.arg("p2").toFloat() / 100.0;
  if (server.hasArg("fix")) ts_fixed_mode = (server.arg("fix").toInt() == 1);
  if (server.hasArg("sgl")) single_channel_mode = (server.arg("sgl").toInt() == 1);

  if (server.hasArg("int")) {
    long val = server.arg("int").toInt();
    if (val < 10) val = 10; 
    integration_time_us = val * 1000UL; 
  }
  
  if (server.hasArg("vp")) phys_V_pulse = server.arg("vp").toFloat();
  if (server.hasArg("r1")) phys_R1_mohm = server.arg("r1").toFloat();
  if (server.hasArg("r2")) phys_R2_mohm = server.arg("r2").toFloat();
  
  calibration_mode = (server.hasArg("cal") && server.arg("cal").toInt() == 1);
  
  // RESETTO TUTTO QUANDO PARTO
  welford_count = 0; welford_mean = 0; welford_M2 = 0; 
  accum_t1_us = 0; accum_t2_us = 0;
  
  server.send(200, "text/plain", "OK");
  inConfigMode = false; configModeRequest = false;
}

// ============================================================
// --- 3. LOOP ---
// ============================================================

void setup() {
  Serial.begin(115200);
  pinMode(PIN_CH1, OUTPUT); pinMode(PIN_CH2, OUTPUT);
  pinMode(LED_PIN, OUTPUT); pinMode(BUTTON_PIN, INPUT_PULLUP); 
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);
  WiFi.softAP(ap_ssid, NULL);
  dnsServer.start(53, "*", WiFi.softAPIP());
  server.on("/", handleRoot); server.on("/set", handleSet);
  server.onNotFound(handleCaptive); server.begin();
  
  configModeRequest = true; 
  
  Serial.println("System Ready. Waiting for START command.");
}

void loop() {
  if (configModeRequest) {
    inConfigMode = true;
    // Spegni tutto mentre sei in pausa
    digitalWrite(PIN_CH1, LOW); 
    digitalWrite(PIN_CH2, LOW);
    
    Serial.println("--- PAUSED (Config Mode) ---");
    
    while (inConfigMode) {
      dnsServer.processNextRequest(); 
      server.handleClient(); 
      
      // Blink LED per indicare "Standby/Config"
      digitalWrite(LED_PIN, (millis() / 500) % 2); 
      
      delay(5); 
      if (digitalRead(BUTTON_PIN) == LOW) { delay(200); if(digitalRead(BUTTON_PIN)==LOW) inConfigMode=false; }
    }
    
    // Uscita dalla Config -> INIZIO GENERAZIONE
    digitalWrite(LED_PIN, HIGH); // LED fisso quando genera
    configModeRequest = false; 
    integration_start_us = micros(); 
    accum_t1_us = 0; accum_t2_us = 0;
    calculateNextPulse();
    Serial.println("--- RUNNING ---");
  }

  if (calibration_mode) { digitalWrite(PIN_CH1, HIGH); delay(10); return; }
  
  // GENERAZIONE IMPULSO
  if (next_is_ch2 && !single_channel_mode) { 
      digitalWrite(PIN_CH2, HIGH); delayMicroseconds(delay_T1); digitalWrite(PIN_CH2, LOW);
      accum_t2_us += (double)delay_T1;
  } else {
      digitalWrite(PIN_CH1, HIGH); delayMicroseconds(delay_T1); digitalWrite(PIN_CH1, LOW);
      accum_t1_us += (double)delay_T1;
  }
  
  unsigned long now = micros();
  
  // FINESTRA INTEGRAZIONE
  if (now - integration_start_us >= integration_time_us) {
    double i1_na = (phys_V_pulse / phys_R1_mohm) * 1000.0;
    double i2_na = (phys_V_pulse / phys_R2_mohm) * 1000.0;
    
    double q_tot_pC = ( (i1_na * accum_t1_us) + (i2_na * accum_t2_us) ) * 0.001;
    
    welford_count++;
    double delta = q_tot_pC - welford_mean;
    welford_mean += delta / welford_count;
    welford_M2 += delta * (q_tot_pC - welford_mean);
    
    accum_t1_us = 0; accum_t2_us = 0;
    integration_start_us += integration_time_us; 
  }

  calculateNextPulse(); 
  long elapsed = micros() - now; 
  long remaining_T2 = delay_T2 - elapsed;
  if (remaining_T2 > 0) delayMicroseconds(remaining_T2);
}
