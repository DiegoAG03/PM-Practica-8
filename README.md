# Práctica 8: Cómputo distribuido entre RP2040 y ESP32

Implementación de un sistema distribuido heterogéneo cliente-servidor (RPC sobre UART) en la tarjeta **UNIT DualMCU (RP2040 + ESP32)** para la materia de Procesadores Multinúcleo.

## Estructura del repositorio
- `c1-sys/`: Experimento 1 — Sistema base (lectura de temperatura, control de LED centinela y aproximación de π con 1,000 términos).
- `c2-pi/`: Experimentos 2 y 4 — Aproximación de π con 10⁶ términos en los dos núcleos del RP2040 con medición de tiempo en milisegundos.
- `c3-pi-multicore/`: Experimentos 3 y 4 — Cálculo distribuido en partes iguales entre los dos núcleos del RP2040 y el ESP32, con medición de tiempo.
- `c4-freertos/`: Experimento 5 — Migración del nodo RP2040 a C/C++ sobre FreeRTOS (en desarrollo).
