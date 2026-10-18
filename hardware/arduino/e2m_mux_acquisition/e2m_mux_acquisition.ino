/*
 * E2M mux acquisition firmware  --  Arduino Uno or compatible.
 *
 * STATUS: COMPILES AGAINST A FAKE SENSOR DRIVER ONLY. NOT RUN ON HARDWARE.
 *
 * The real sensor driver is deliberately absent. The repository has no sensor
 * inventory (research/bus_provenance/E2M_GATE_STATUS.md, gate 2), so there is
 * no part number, no I2C address and no register map to write one against.
 * Guessing a register map is how a plausible number gets read out of the wrong
 * register, and the owner's decision forbids it in as many words.
 *
 * The TCA9548A constants below are NOT compiled in either: the datasheet has
 * not been retrieved (gate 1), so E2M_MUX_ADDR must be supplied at build time
 * and the build fails without it. Remembered device constants are not written
 * into hardware code.
 *
 * AUTHORITY: this firmware reads. It never writes to anything except the mux
 * channel register, never drives a pin as an output except I2C, and contains
 * no servo, motor, ESC, PWM or actuator code of any kind.
 *
 * Build (after gates 1 and 2 pass):
 *   arduino-cli compile --fqbn arduino:avr:uno \
 *     --build-property "compiler.cpp.extra_flags=-DE2M_MUX_ADDR=0x70 \
 *                       -DE2M_REAL_DRIVER=1" \
 *     hardware/arduino/e2m_mux_acquisition
 *
 * Build today (fake driver, no hardware claim):
 *   arduino-cli compile --fqbn arduino:avr:uno \
 *     hardware/arduino/e2m_mux_acquisition
 */

#include <Wire.h>

/* ---- build-time configuration -------------------------------------- */

#ifndef E2M_REAL_DRIVER
#define E2M_REAL_DRIVER 0
#endif

#if E2M_REAL_DRIVER
#  ifndef E2M_MUX_ADDR
#    error "E2M_MUX_ADDR must be supplied from the verified datasheet. \
It is not compiled in from memory. See E2M_GATE_STATUS.md gate 1."
#  endif
#  ifndef E2M_SENSOR_ADDR
#    error "E2M_SENSOR_ADDR must come from the sensor inventory. \
See E2M_GATE_STATUS.md gate 2."
#  endif
#endif

#ifndef E2M_VERIFY_READBACK
#define E2M_VERIFY_READBACK 1
#endif

#ifndef E2M_CHANNELS
#define E2M_CHANNELS 3
#endif

static const long  E2M_BAUD      = 115200;
static const int   E2M_RETRIES   = 3;
static const int   READBACK_NONE = -1;

/* ---- protocol ------------------------------------------------------- */
/* CRC-16/CCITT-FALSE. The identical eight lines live in
 * csia_e2m/protocol.py so the two ends cannot drift through a library. */
static uint16_t crc16_ccitt(const char *data, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= ((uint16_t)data[i]) << 8;
    for (uint8_t b = 0; b < 8; b++) {
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021)
                           : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

static char line_buf[160];

static void emit(unsigned long seq, unsigned long sweep, int cmd_ch,
                 int rb_ch, const char *sensor, const char *status,
                 long milli, const char *unit, unsigned long ctrl_us,
                 int i2c_err, int retries) {
  int n = snprintf(line_buf, sizeof(line_buf),
                   "E2M1,%lu,%lu,%d,%d,%s,%s,%ld,%s,%lu,%d,%d",
                   seq, sweep, cmd_ch, rb_ch, sensor, status, milli, unit,
                   ctrl_us, i2c_err, retries);
  if (n <= 0 || (size_t)n >= sizeof(line_buf)) {
    /* Never emit a truncated frame that might still parse. */
    Serial.println("E2M1,0,0,0,-1,-,SAFE_IDLE,0,,0,0,0*0000");
    return;
  }
  uint16_t crc = crc16_ccitt(line_buf, (size_t)n);
  Serial.print(line_buf);
  Serial.print('*');
  if (crc < 0x1000) Serial.print('0');
  if (crc < 0x0100) Serial.print('0');
  if (crc < 0x0010) Serial.print('0');
  Serial.println(crc, HEX);
}

/* ---- mux ------------------------------------------------------------ */

#if E2M_REAL_DRIVER
static bool mux_select(uint8_t channel, int *i2c_err) {
  Wire.beginTransmission(E2M_MUX_ADDR);
  Wire.write((uint8_t)(1 << channel));
  *i2c_err = Wire.endTransmission();
  return *i2c_err == 0;
}

static int mux_readback(void) {
  if (Wire.requestFrom((uint8_t)E2M_MUX_ADDR, (uint8_t)1) != 1) {
    return READBACK_NONE;
  }
  uint8_t reg = Wire.read();
  /* Exactly one bit set is the only state this firmware commands. Anything
   * else is reported as a mismatch rather than reduced to a channel number. */
  for (uint8_t c = 0; c < 8; c++) {
    if (reg == (uint8_t)(1 << c)) return (int)c;
  }
  return READBACK_NONE;
}
#endif

/* ---- sensor driver -------------------------------------------------- */
/* Pluggable. The fake one is deterministic; the real one does not exist. */

static bool read_sensor(uint8_t channel, unsigned long sweep, long *milli,
                        const char **unit, int *i2c_err) {
#if E2M_REAL_DRIVER
  (void)channel; (void)sweep; (void)milli; (void)unit; (void)i2c_err;
#  error "No real sensor driver is implemented. The sensor inventory is empty \
(E2M_GATE_STATUS.md gate 2); a guessed register map is forbidden by the owner \
decision. Fill hardware/inventory/e2m_sensors.yaml, then write the driver."
#else
  *milli = 25000L + 1000L * (long)channel + (long)sweep * (3L + (long)channel);
  *unit = "milliC";
  *i2c_err = 0;
  return true;
#endif
}

/* ---- run ------------------------------------------------------------ */

static unsigned long seq = 0;
static unsigned long sweep = 0;
static bool safe_idle = false;

void setup(void) {
  Serial.begin(E2M_BAUD);
  while (!Serial) { ; }
  Wire.begin();
  if (E2M_CHANNELS < 1 || E2M_CHANNELS > 8) {
    safe_idle = true;
  }
}

void loop(void) {
  if (safe_idle) {
    emit(++seq, sweep, 0, READBACK_NONE, "-", "SAFE_IDLE", 0, "", micros(),
         0, 0);
    delay(1000);
    return;
  }

  for (uint8_t ch = 0; ch < E2M_CHANNELS; ch++) {
    char sensor_id[8];
    snprintf(sensor_id, sizeof(sensor_id), "ch%u", (unsigned)ch);

    int i2c_err = 0;
    int rb = READBACK_NONE;
    int retries = 0;

#if E2M_REAL_DRIVER
    bool ok = false;
    for (retries = 0; retries < E2M_RETRIES && !ok; retries++) {
      ok = mux_select(ch, &i2c_err);
    }
    if (!ok) {
      emit(++seq, sweep, ch, READBACK_NONE, sensor_id, "ERR_MUX_WRITE", 0, "",
           micros(), i2c_err, retries);
      continue;
    }
#  if E2M_VERIFY_READBACK
    rb = mux_readback();
    if (rb == READBACK_NONE) {
      emit(++seq, sweep, ch, READBACK_NONE, sensor_id, "ERR_MUX_READBACK", 0,
           "", micros(), i2c_err, retries);
      continue;
    }
    if (rb != (int)ch) {
      emit(++seq, sweep, ch, rb, sensor_id, "ERR_READBACK_MISMATCH", 0, "",
           micros(), i2c_err, retries);
      continue;
    }
#  endif
#else
    rb = E2M_VERIFY_READBACK ? (int)ch : READBACK_NONE;
#endif

    long milli = 0;
    const char *unit = "";
    if (!read_sensor(ch, sweep, &milli, &unit, &i2c_err)) {
      emit(++seq, sweep, ch, rb, sensor_id, "ERR_SENSOR_NACK", 0, "",
           micros(), i2c_err, retries);
      continue;
    }
    emit(++seq, sweep, ch, rb, sensor_id, "OK", milli, unit, micros(),
         i2c_err, retries);
  }
  sweep++;
  delay(100);
}
