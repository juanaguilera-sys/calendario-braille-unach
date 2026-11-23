# Calendario Dual Braille / Visual Autónomo (DD/MM/AAAA)

Proyecto desarrollado para la asignatura de **Programación Orientada a Objetos** y financiado por el **proyecto VcM Ingeniería Accesible de la Universidad Adventista de Chile (UNACH)**.

## Descripción del Sistema
Prototipo de calendario autónomo de escritorio basado en **Raspberry Pi Pico (MicroPython POO)**. Permite a personas ciegas percibir la fecha actual mediante ruedas motorizadas impresas en 3D con caracteres Braille en relieve, mientras muestra simultáneamente la fecha, el día de la semana y las tareas asociadas en una pantalla OLED I2C para usuarios videntes.

## Arquitectura y Hardware
* **Microcontrolador:** Raspberry Pi Pico (RP2040) ejecutando `main.py` de forma autónoma.
* **Reloj en Tiempo Real:** Módulo RTC DS3231 vía I2C (`0x68`) con pila de respaldo CR2032.
* **Vista Vidente:** Pantalla OLED SSD1306 vía I2C.
* **Vista Braille:** 4 motores paso a paso 28BYJ-48 con drivers ULN2003 (Día y Mes) + 4 ruedas manuales (Año) + prefijo numeral (`#`).
* **Interacción y Energía:** Batería LiPo 3.7V + cargador TP4056 + switch físico de corte + 2 botones diferenciados por textura (liso para navegar/ajustar y rugoso para actualizar).

## Integrantes del Equipo
* **Benjamín Mora:** Diseño y modelado 3D.
* **Luis Pérez:** Circuito electrónico y hardware.
* **Gabriel Severino:** Presentación y apoyo técnico.
* **Joaquín Rivas:** Traducción y validación táctil Braille.
* **Juan Aguilera:** Documentación técnica.
