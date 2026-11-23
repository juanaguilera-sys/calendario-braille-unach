# Calendario Braille - Raspberry Pi Pico - WOKWI (MicroPython)
# OLED SSD1306 + RTC DS1307/DS3231 + 4 servos de 180 grados
#
# I2C: SDA=GP0, SCL=GP1
# Servos: GP2 (dia dec), GP6 (dia uni), GP10 (mes dec), GP14 (mes uni)
# Boton 1 (GP18): enciende/apaga la pantalla OLED
# Boton 2 (GP19): enciende/apaga el dispositivo

from machine import Pin, I2C, PWM
from time import sleep_ms, ticks_ms, ticks_diff
import framebuf

# ---------------- CONFIGURACION ----------------

I2C_SDA = 0
I2C_SCL = 1
I2C_FREQ = 100000

SERVO_PINS = (2, 6, 10, 14)
POSITIONS = (4, 10, 2, 10)

BUTTON1_PIN = 18
BUTTON2_PIN = 19

RTC_ADDR = 0x68
OLED_ADDR = 0x3C

SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_FREQ = 50
SERVO_STEP_DEG = 3
SERVO_STEP_DELAY_MS = 10

STARTUP_IGNORE_MS = 2000   # ignora botones al arrancar
DEFAULT_DATE = (2026, 11, 9, 12, 0, 0)

# ---------------- UTILIDADES ----------------

def bcd_to_int(v):
    return ((v >> 4) * 10) + (v & 0x0F)

def int_to_bcd(v):
    return ((v // 10) << 4) | (v % 10)

def is_leap_year(y):
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)

def days_in_month(m, y):
    if m == 2:
        return 29 if is_leap_year(y) else 28
    if m in (4, 6, 9, 11):
        return 30
    return 31

def date_is_valid(y, m, d):
    return 2000 <= y <= 2099 and 1 <= m <= 12 and 1 <= d <= days_in_month(m, y)

def weekday_name(y, m, d):
    offsets = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if m < 3:
        y -= 1
    w = (y + y // 4 - y // 100 + y // 400 + offsets[m - 1] + d) % 7
    return ("Domingo", "Lunes", "Martes", "Miercoles",
            "Jueves", "Viernes", "Sabado")[w]

# ---------------- I2C CON REINTENTOS ----------------

def i2c_write(i2c, addr, data):
    for _ in range(5):
        try:
            i2c.writeto(addr, data)
            return True
        except OSError:
            sleep_ms(5)
    return False

def i2c_read_mem(i2c, addr, reg, n):
    for _ in range(5):
        try:
            return i2c.readfrom_mem(addr, reg, n)
        except OSError:
            sleep_ms(5)
    raise OSError("I2C sin respuesta")

def i2c_write_mem(i2c, addr, reg, data):
    for _ in range(5):
        try:
            i2c.writeto_mem(addr, reg, data)
            return
        except OSError:
            sleep_ms(5)
    raise OSError("I2C sin respuesta")

# ---------------- OLED (framebuf) ----------------

INIT_CMDS = (0xAE, 0x20, 0x00, 0x40, 0xA1, 0xC8, 0x81, 0x7F,
             0xA6, 0xA8, 0x3F, 0xD3, 0x00, 0xD5, 0x80,
             0xD9, 0xF1, 0xDA, 0x12, 0xDB, 0x40, 0x8D, 0x14)

class OLED:
    def __init__(self, i2c, addr=OLED_ADDR):
        self.i2c = i2c
        self.addr = addr
        self.buf = bytearray(1024)
        self.fb = framebuf.FrameBuffer(self.buf, 128, 64, framebuf.MONO_VLSB)
        self.iniciar()

    def cmd(self, c):
        i2c_write(self.i2c, self.addr, bytes((0x00, c)))

    def iniciar(self):
        # Inicializacion completa y pantalla encendida
        for c in INIT_CMDS:
            self.cmd(c)
        self.cmd(0xAF)

    def power(self, on):
        if on:
            self.iniciar()      # reinicia por completo al encender
        else:
            self.cmd(0xAE)

    def lines(self, *texts):
        self.fb.fill(0)
        self.fb.rect(0, 0, 128, 64, 1)
        y = 5
        for t in texts:
            self.fb.text(str(t)[:14], 4, y, 1)
            y += 14
        self.show()

    def show(self):
        for page in range(8):
            i2c_write(self.i2c, self.addr,
                      bytes((0x00, 0x21, 0, 127, 0x22, page, page)))
            start = page * 128
            i2c_write(self.i2c, self.addr,
                      b'\x40' + bytes(self.buf[start:start + 128]))

# ---------------- RELOJ (RTC con respaldo interno) ----------------

class Reloj:
    def __init__(self, i2c):
        self.i2c = i2c
        self.rtc_ok = False
        self.soft_date = DEFAULT_DATE[:3]
        self.soft_hms = DEFAULT_DATE[3:]
        self.soft_start = ticks_ms()
        self._iniciar()

    def _leer_rtc(self):
        d = i2c_read_mem(self.i2c, RTC_ADDR, 0x00, 7)
        s = bcd_to_int(d[0] & 0x7F)
        mi = bcd_to_int(d[1] & 0x7F)
        h = bcd_to_int(d[2] & 0x3F)
        day = bcd_to_int(d[4] & 0x3F)
        mo = bcd_to_int(d[5] & 0x1F)
        y = 2000 + bcd_to_int(d[6])
        if not date_is_valid(y, mo, day):
            raise ValueError("fecha mala")
        return (y, mo, day, h, mi, s)

    def _escribir_rtc(self, y, m, d, h, mi, s):
        v = bytearray(7)
        v[0] = int_to_bcd(s)
        v[1] = int_to_bcd(mi)
        v[2] = int_to_bcd(h)
        v[3] = 1
        v[4] = int_to_bcd(d)
        v[5] = int_to_bcd(m)
        v[6] = int_to_bcd(y - 2000)
        i2c_write_mem(self.i2c, RTC_ADDR, 0x00, v)

    def _iniciar(self):
        try:
            self._leer_rtc()
            self.rtc_ok = True
        except Exception:
            try:
                self._escribir_rtc(*DEFAULT_DATE)
                self._leer_rtc()
                self.rtc_ok = True
            except Exception:
                self.rtc_ok = False

    def ahora(self):
        if self.rtc_ok:
            try:
                return self._leer_rtc()
            except Exception:
                self.rtc_ok = False
        secs = ticks_diff(ticks_ms(), self.soft_start) // 1000
        h, mi, s = self.soft_hms
        total = h * 3600 + mi * 60 + s + secs
        y, m, d = self.soft_date
        return (y, m, d, (total // 3600) % 24, (total // 60) % 60, total % 60)

# ---------------- SERVOS ----------------

class ServoRueda:
    def __init__(self, pin, positions):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(SERVO_FREQ)
        self.positions = positions
        self.angle = 0.0
        self.digit = 0
        self._write(0)

    def _write(self, angle):
        angle = max(0, min(180, angle))
        us = SERVO_MIN_US + (SERVO_MAX_US - SERVO_MIN_US) * angle / 180
        self.pwm.duty_u16(int(us * 65535 / 20000))

    def apagar(self):
        self.pwm.duty_u16(0)          # sin pulso: servo suelto

    def encender(self):
        self._write(self.angle)       # retoma la ultima posicion

    def mover(self, digit):
        if digit < 0 or digit >= self.positions:
            return
        target = digit * 180 / (self.positions - 1) if self.positions > 1 else 0
        while abs(target - self.angle) > SERVO_STEP_DEG:
            self.angle += SERVO_STEP_DEG if target > self.angle else -SERVO_STEP_DEG
            self._write(self.angle)
            sleep_ms(SERVO_STEP_DELAY_MS)
        self.angle = target
        self._write(target)
        self.digit = digit

def actualizar_servos(servos, y, m, d):
    objetivos = (d // 10, d % 10, m // 10, m % 10)
    for i in range(4):
        if servos[i].digit != objetivos[i]:
            servos[i].mover(objetivos[i])

# ---------------- BOTON (solo cuenta si antes estuvo suelto) ----------------

class Boton:
    def __init__(self, pin):
        self.pin = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.armado = False      # se arma al verlo suelto
        self.ultimo = 0

    def valor(self):
        return self.pin.value()

    def pulsado(self, now):
        v = self.pin.value()
        if v == 1:
            self.armado = True
            return False
        if self.armado and ticks_diff(now, self.ultimo) > 300:
            self.armado = False
            self.ultimo = now
            return True
        return False

# ---------------- PANTALLA ----------------

def dibujar(oled, dt, estado, b1, b2):
    y, m, d, h, mi, s = dt
    fb = oled.fb
    fb.fill(0)
    fb.rect(0, 0, 128, 64, 1)
    fb.text("CALENDARIO", 4, 4, 1)
    fb.text("%02d/%02d/%04d" % (d, m, y), 4, 16, 1)
    fb.text(weekday_name(y, m, d), 4, 28, 1)
    fb.text("%02d:%02d:%02d" % (h, mi, s), 4, 40, 1)
    fb.text("%s B%d%d" % (estado[:7], b1, b2), 4, 52, 1)
    oled.show()

# ---------------- PROGRAMA ----------------

def main():
    i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)
    devs = i2c.scan()

    oled = OLED(i2c)
    oled.lines("Iniciando...", "I2C:", ",".join(hex(x) for x in devs))
    sleep_ms(1500)

    reloj = Reloj(i2c)
    oled.lines("RTC OK" if reloj.rtc_ok else "Sin RTC",
               "" if reloj.rtc_ok else "(interno)")
    sleep_ms(1000)

    servos = [ServoRueda(p, n) for p, n in zip(SERVO_PINS, POSITIONS)]

    btn1 = Boton(BUTTON1_PIN)
    btn2 = Boton(BUTTON2_PIN)
    inicio = ticks_ms()

    oled_on = True
    dispositivo_on = True
    ultima_fecha = None
    ultimo_dibujo = 0
    forzar = True
    errores = 0

    while True:
        try:
            now = ticks_ms()

            # Los botones se ignoran durante el arranque
            if ticks_diff(now, inicio) < STARTUP_IGNORE_MS:
                btn1.pulsado(now)
                btn2.pulsado(now)
                p1 = p2 = False
            else:
                p1 = btn1.pulsado(now)
                p2 = btn2.pulsado(now)

            # B2: enciende/apaga el dispositivo
            if p2:
                dispositivo_on = not dispositivo_on
                if dispositivo_on:
                    for s in servos:
                        s.encender()
                    if oled_on:
                        oled.power(True)
                    ultima_fecha = None
                    forzar = True
                else:
                    for s in servos:
                        s.apagar()
                    oled.power(False)

            # B1: enciende/apaga la OLED (solo con el dispositivo encendido)
            if p1 and dispositivo_on:
                oled_on = not oled_on
                oled.power(oled_on)
                forzar = True

            if not dispositivo_on:
                sleep_ms(50)
                continue

            dt = reloj.ahora()
            fecha = dt[:3]
            estado = ("Listo" if reloj.rtc_ok else "SinRTC") if errores == 0 \
                else "Err:%d" % errores
            v1, v2 = btn1.valor(), btn2.valor()

            if fecha != ultima_fecha:
                if oled_on:
                    dibujar(oled, dt, "Mueve", v1, v2)
                actualizar_servos(servos, dt[0], dt[1], dt[2])
                ultima_fecha = fecha
                forzar = True

            if oled_on and (forzar or ticks_diff(ticks_ms(), ultimo_dibujo) >= 1000):
                dibujar(oled, dt, estado, v1, v2)
                ultimo_dibujo = ticks_ms()
                forzar = False
        except Exception:
            errores += 1
            sleep_ms(50)

        sleep_ms(20)

try:
    main()
except Exception as e:
    try:
        i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)
        o = OLED(i2c)
        msg = repr(e)
        o.fb.fill(0)
        o.fb.text("FALLO", 0, 0, 1)
        for i in range(3):
            o.fb.text(msg[i*16:(i+1)*16], 0, 14 + i*14, 1)
        o.show()
    except Exception:
        pass