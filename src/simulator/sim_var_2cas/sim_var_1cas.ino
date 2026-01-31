#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>

const char* ap_ssid = "Sim_Var";
#define LED_PIN 18
#define BUTTON_PIN 0 

volatile double mean_T1 = 250.0;   
volatile double std_T1 = 80.0;     
volatile double mean_Ts = 6950.0;  

unsigned long integration_time_us = 50000;
bool calibration_mode = false;            
bool ts_fixed_mode = false;               

volatile double phys_V_pulse = 3.3;    
volatile double phys_R_mohm = 1000.0;  
volatile double phys_C_pf = 100.0;     
volatile double phys_ADC_Vref = 5.0;   

volatile bool configModeRequest = false; 
bool inConfigMode = false;               

double welford_mean = 0;
double welford_M2 = 0;
long welford_count = 0;
double current_window_energy = 0; 
unsigned long integration_start_us = 0;

double next_T1 = 0;
double next_Ts = 0;
long delay_T1 = 0;
long delay_T2 = 0;

WebServer server(80);
DNSServer dnsServer;

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
  
  if (ts_fixed_mode) {
      next_Ts = mean_Ts;
  } else {
      next_Ts = getPoissonInterval(mean_Ts);
  }
  
  if (next_T1 < 1.0) next_T1 = 1.0; 
  if (next_Ts <= next_T1) next_Ts = next_T1 + 1.0; 
  
  double t2_val = next_Ts - next_T1;
  
  delay_T1 = (long)next_T1;
  delay_T2 = (long)t2_val;
}

void IRAM_ATTR handleButtonPress() {
  configModeRequest = true;
}

void handleCaptive() {
  server.sendHeader("Location", "http://" + WiFi.softAPIP().toString(), true);
  server.send(302, "text/plain", "Redirecting...");
}

const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE HTML><html lang="it"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sim Var</title><style>
body{font-family:sans-serif;text-align:center;background:#222;color:#eee;padding:10px}
.card{background:#333;max-width:600px;margin:auto;padding:15px;border-radius:10px;box-shadow:0 4px 8px #000}
h2{color:#0f0;font-size:1.2em} .val{font-weight:bold;color:#0f0} .phys{color:#00e5ff}
input{width:90px;padding:5px;background:#444;border:1px solid #666;color:#fff;text-align:right}
input[type=checkbox]{transform:scale(1.5)}
.row{display:flex;justify-content:space-between;margin:8px 0;align-items:center;font-size:0.9em}
.sub-row{display:flex;justify-content:flex-end;margin:-5px 0 8px 0;font-size:0.85em;color:#aaa}
hr{border-color:#555}
button{width:100%;padding:12px;background:#d32f2f;color:#fff;border:none;border-radius:5px;font-size:1.1em;cursor:pointer;margin-top:10px}
</style></head><body>
<div class="card">
  <h2>Configurazione</h2>
  <h2>(SIMULAZIONE IN PAUSA)</h2>
  
  <div class="row"><span>Media T1 (Impulso) [µs]</span><input id="t1" type="number" value="%T1%"></div>
  <div class="row"><span>DevStd T1 (Gauss) [µs]</span><input id="s1" type="number" value="%S1%"></div>
  <div class="row"><span>Media Ts (Occorrenza) [µs]</span><input id="ts" type="number" value="%TS%"></div>
  <div class="row"><span><b>Ts COSTANTE (Fisso)</b></span><input id="fix" type="checkbox" %FIX%></div>
  <hr>
  <div class="row"><span>Tempo Integrazione [ms]</span><input id="int" type="number" value="%INT%"></div>
  <div class="row"><span><b>MODO CALIBRAZIONE (LED ON)</b></span><input id="cal" type="checkbox" %CAL%></div>
  
  <hr>
  <div class="row" style="color:#aaa">--- Parametri Fisici ---</div>
  <div class="row"><span>Tensione Pulse [V]</span><input id="vp" type="number" step="0.1" value="%VP%"></div>
  <div class="row"><span>Resistenza [M&Omega;]</span><input id="rm" type="number" value="%RM%"></div>
  <div class="row"><span>Capacità Int. [pF]</span><input id="cp" type="number" value="%CP%"></div>
  <div class="row"><span>Vref ADC [V]</span><input id="vr" type="number" step="0.1" value="%VR%"></div>
  
  <hr>
  <h3>Statistiche Ultima Sessione</h3>
  <div class="row"><span>Finestre Integrate:</span><span class="val">%CNT%</span></div>
  <div class="row"><span>Media (su finestra):</span><span class="val">%AVG% µs</span></div>
  
  <div class="row"><span>Varianza (Tempo):</span><span class="val">%VAR% µs²</span></div>
  <div class="sub-row"><span>Dev.Std: <span id="std_t">---</span> µs</span></div>
  
  <div class="row"><span>Predizione Carica (Q²):</span><span class="phys" id="vq">---</span></div>
  <div class="sub-row"><span>Dev.Std: <span id="std_q">---</span> pC</span></div>

  <div class="row"><span>Predizione ADC (Ch²):</span><span class="phys" id="vadc">---</span></div>
  <div class="sub-row"><span>Dev.Std: <span id="std_adc">---</span> Ch</span></div>

  <br>
  <button onclick="save()">SALVA E RIPRENDI</button>
</div>
<script>
function calc() {
  let var_t = parseFloat("%VAR%"); 
  
  if(var_t >= 0) {
      document.getElementById('std_t').innerText = Math.sqrt(var_t).toFixed(2);
  }

  let v_pulse = parseFloat(document.getElementById('vp').value);
  let r_mohm = parseFloat(document.getElementById('rm').value);
  let c_pf = parseFloat(document.getElementById('cp').value);
  let v_ref = parseFloat(document.getElementById('vr').value);
  
  let i_nanoA = (v_pulse / r_mohm) * 1000.0; 
  
  let var_q_pC2 = (i_nanoA * i_nanoA) * var_t * 0.000001;
  
  let gain = (1.0 / c_pf) * (4096.0 / v_ref);
  let var_adc = var_q_pC2 * (gain * gain);
  
  if(!isNaN(var_q_pC2)) {
    document.getElementById('vq').innerText = var_q_pC2.toFixed(2) + " pC²";
    document.getElementById('vadc').innerText = var_adc.toFixed(2) + " Ch²";
    
    document.getElementById('std_q').innerText = Math.sqrt(var_q_pC2).toFixed(3);
    document.getElementById('std_adc').innerText = Math.sqrt(var_adc).toFixed(3);
  }
}
setTimeout(calc, 200);

function save() {
  let calMode = document.getElementById('cal').checked ? 1 : 0;
  let fixMode = document.getElementById('fix').checked ? 1 : 0;
  let q = "/set?t1="+document.getElementById('t1').value +
          "&s1="+document.getElementById('s1').value +
          "&ts="+document.getElementById('ts').value +
          "&fix="+fixMode +
          "&int="+document.getElementById('int').value +
          "&vp="+document.getElementById('vp').value +
          "&rm="+document.getElementById('rm').value +
          "&cp="+document.getElementById('cp').value +
          "&vr="+document.getElementById('vr').value +
          "&cal="+calMode;
  
  fetch(q).then(() => { 
    document.body.innerHTML = "<h1>SIMULAZIONE IN CORSO</h1><h2>PREMERE IL TASTO PER MODIFICARE</h2>"; 
    setTimeout(()=>location.reload(), 2000); 
  });
}
</script></body></html>
)rawliteral";

void handleRoot() {
  String html = String(index_html);
  
  html.replace("%T1%", String(mean_T1));
  html.replace("%S1%", String(std_T1));
  html.replace("%TS%", String(mean_Ts));
  html.replace("%FIX%", ts_fixed_mode ? "checked" : ""); 
  
  html.replace("%INT%", String(integration_time_us / 1000)); 
  html.replace("%CAL%", calibration_mode ? "checked" : "");  
  
  html.replace("%VP%", String(phys_V_pulse));
  html.replace("%RM%", String(phys_R_mohm));
  html.replace("%CP%", String(phys_C_pf));
  html.replace("%VR%", String(phys_ADC_Vref));
  
  html.replace("%CNT%", String(welford_count));
  html.replace("%AVG%", String(welford_mean, 2));
  
  double var = (welford_count > 1) ? welford_M2 / (welford_count - 1) : 0;
  html.replace("%VAR%", String(var, 2));
  
  server.send(200, "text/html", html);
}

void handleSet() {
  if (server.hasArg("t1")) mean_T1 = server.arg("t1").toFloat();
  if (server.hasArg("s1")) std_T1 = server.arg("s1").toFloat();
  if (server.hasArg("ts")) mean_Ts = server.arg("ts").toFloat();
  
  if (server.hasArg("fix")) {
    ts_fixed_mode = (server.arg("fix").toInt() == 1);
  } else {
    ts_fixed_mode = false;
  }

  if (server.hasArg("int")) {
    long val = server.arg("int").toInt();
    if (val < 10) val = 10; 
    integration_time_us = val * 1000UL; 
  }
  
  if (server.hasArg("vp")) phys_V_pulse = server.arg("vp").toFloat();
  if (server.hasArg("rm")) phys_R_mohm = server.arg("rm").toFloat();
  if (server.hasArg("cp")) phys_C_pf = server.arg("cp").toFloat();
  if (server.hasArg("vr")) phys_ADC_Vref = server.arg("vr").toFloat();
  
  if (server.hasArg("cal")) {
    calibration_mode = (server.arg("cal").toInt() == 1);
  } else {
    calibration_mode = false;
  }
  
  welford_count = 0; 
  welford_mean = 0; 
  welford_M2 = 0; 
  current_window_energy = 0;
  
  server.send(200, "text/plain", "OK");
  inConfigMode = false; 
  configModeRequest = false;
}

void setup() {
  Serial.begin(115200);
  delay(1000); 
  
  Serial.println("\n\n=== SIMULATORE AVVIATO ===");

  pinMode(LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP); 
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), handleButtonPress, FALLING);

  WiFi.softAP(ap_ssid, NULL);
  dnsServer.start(53, "*", WiFi.softAPIP());
  
  server.on("/", handleRoot);
  server.on("/set", handleSet);
  
  server.on("/hotspot-detect.html", handleCaptive);
  server.on("/generate_204", handleCaptive);
  server.on("/gen_204", handleCaptive);
  server.on("/success.html", handleRoot);
  server.on("/ncsi.txt", handleCaptive);
  server.on("/connecttest.txt", handleCaptive);
  server.onNotFound(handleRoot);
  
  server.begin();

  calculateNextPulse();
  integration_start_us = micros();
  
  Serial.println("Premi BOOT per configurare.");
}

void loop() {
  if (configModeRequest) {
    inConfigMode = true;
    digitalWrite(LED_PIN, LOW); 
  
    delay(50);
    while(digitalRead(BUTTON_PIN) == LOW) delay(10);
    delay(50);
    
    Serial.println("\n--- CONFIG MODE ---");
    
    while (inConfigMode) {
      dnsServer.processNextRequest(); 
      server.handleClient(); 
      delay(5); 
      
      if (digitalRead(BUTTON_PIN) == LOW) {
         delay(50); 
         if (digitalRead(BUTTON_PIN) == LOW) { 
             inConfigMode = false; 
             while(digitalRead(BUTTON_PIN) == LOW) delay(50);
         }
      }
    }
    
    Serial.println("-> RIPRESA...");
    configModeRequest = false;
    integration_start_us = micros();
    current_window_energy = 0; 
    calculateNextPulse();
  }

  if (calibration_mode) {
    digitalWrite(LED_PIN, HIGH);
    delay(10); 
    return; 
  }
  
  digitalWrite(LED_PIN, HIGH);
  delayMicroseconds(delay_T1); 
  
  digitalWrite(LED_PIN, LOW);
  
  unsigned long start_calc = micros();
  current_window_energy += (double)(delay_T1);

  if (micros() - integration_start_us >= integration_time_us) {
    welford_count++;
    
    double delta = current_window_energy - welford_mean; 
    welford_mean += delta / welford_count;           
    welford_M2 += delta * (current_window_energy - welford_mean); 
    
    current_window_energy = 0;
    integration_start_us += integration_time_us; 
  }

  calculateNextPulse();

  long elapsed_calc = micros() - start_calc;
  long remaining_T2 = delay_T2 - elapsed_calc;

  if (remaining_T2 > 0) {
    delayMicroseconds(remaining_T2);
  } 
}