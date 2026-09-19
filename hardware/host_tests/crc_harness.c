/*
 * Standalone host harness for the firmware's CRC-16/CCITT-FALSE.
 *
 * WHY THIS EXISTS
 * ---------------
 * csia_e2m/protocol.py and e2m_mux_acquisition.ino each carry their own copy
 * of the CRC loop, and the Python module's docstring CLAIMS they cannot drift
 * apart "through a library version". That was an assertion, not evidence: the
 * two are separate source files in separate languages and nothing compared
 * them.
 *
 * This harness makes the claim testable without an Arduino. The function below
 * is COPIED VERBATIM from the .ino -- same body, same types, same order of
 * operations -- and a test extracts the firmware's copy and diffs it against
 * this one, so the harness cannot silently drift from the firmware it stands
 * in for.
 *
 * It reads hex payloads on stdin, one per line, and prints the CRC as four
 * uppercase hex digits. An empty line is the empty payload, which is a real
 * case: CRC of zero bytes is 0xFFFF and an off-by-one init would miss it.
 *
 *   cc -O2 -Wall -Wextra -Werror -o crc_harness crc_harness.c
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/* ---- BEGIN COPY FROM e2m_mux_acquisition.ino ---- */
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
/* ---- END COPY FROM e2m_mux_acquisition.ino ---- */

static int hexval(int c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

int main(void) {
  static char line[65536];
  static char buf[32768];
  while (fgets(line, sizeof(line), stdin)) {
    size_t n = strlen(line);
    while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
    if (n % 2 != 0) {
      fprintf(stderr, "odd-length hex input\n");
      return 2;
    }
    size_t bytes = n / 2;
    if (bytes > sizeof(buf)) {
      fprintf(stderr, "payload too long\n");
      return 2;
    }
    for (size_t i = 0; i < bytes; i++) {
      int hi = hexval((unsigned char)line[2 * i]);
      int lo = hexval((unsigned char)line[2 * i + 1]);
      if (hi < 0 || lo < 0) {
        fprintf(stderr, "bad hex\n");
        return 2;
      }
      buf[i] = (char)((hi << 4) | lo);
    }
    printf("%04X\n", crc16_ccitt(buf, bytes));
    fflush(stdout);
  }
  return 0;
}
