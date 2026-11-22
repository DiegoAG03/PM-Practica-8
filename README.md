# Práctica 8: Cómputo distribuido entre los microcontroladores RP2040 y ESP32

**Autor:** Diego Ambrosio González

**Asignatura:** Procesadores Multinúcleo

Repositorio creado para la Práctica 8 de Procesadores Multinúcleo, el cual contiene la implementación de un sistema disbuido bajo el modelo cliente-servidor (RPC sobre UART) sobre la tarjeta **UNIT DualMCU (RP2040 + ESP32)** El objetivo principal es alojar un servidor web y coordinar la distribución de carga computacional en el ESP32, mientras que en el RP2040 se lleve a cabo el control de periféricos y la ejecución paralela de algoritmos numéricos. Asímismo, se realiza la ejecución tanto en un entorno **MicroPython** intepretado, como sobre un sistema operativo en tiempo real **FreeRTOS**.

## Estructura del repositorio

El repositorio contiene los siguientes experimentos:

- `c1-sys/`: Experimento 1 — Sistema base (lectura de temperatura, control de LED centinela y aproximación de $\pi$ con 1,000 términos).
- `c2-pi/`: Experimentos 2 y 4 — Aproximación de $\pi$ con $10^6$ términos en los dos núcleos del RP2040 con medición de tiempo en milisegundos.
- `c3-pi-multicore/`: Experimentos 3 y 4 — Cálculo distribuido en partes iguales entre los dos núcleos del RP2040 y el ESP32, con medición de tiempo.
- `c4-freertos/`: Experimento 5 — Migración del nodo RP2040 a C/C++ sobre FreeRTOS SMP, manteniendo el coordinador web en el ESP32 con MicroPython.

## Requisitos de Hardware y Software (Completar)

### Hardware
* Tarjeta **UNIT DualMCU** (RP2040 + ESP32).
* Cable USB-C de datos.
* Computadora o dispositivo móvil con Wi-Fi para acceder a la interfaz web.

### Software
* Sistema operativo Ubuntu Linux.
* **MicroPython:**
  * Firmware oficial para RP2040 (`.uf2`).
  * Firmware oficial para ESP32 (`.bin`).
  * IDE **Thonny** (para carga de scripts) y `esptool` (para flasheo inicial del ESP32).
* **FreeRTOS (C/C++):**
  * Toolchain de compilación: `cmake`, `make`, `gcc-arm-none-eabi`, `git`.
  * Raspberry Pi Pico SDK y FreeRTOS Kernel (descargados automáticamente por CMake).
* Navegador web para interactuar con el servidor del ESP32.

## Instrucciones de Ejecución (MicroPython)

### 1. Preparación del firmware (solo la primera vez)
* **RP2040:** Colocar el interruptor `SW2` en posición **A** (RP2040), conectar la placa manteniendo presionado el botón **BOOT** y arrastrar el archivo `.uf2` de MicroPython a la unidad montada.
* **ESP32:** Colocar `SW2` en posición **B** (ESP32) y cargar el firmware de MicroPython mediante `esptool` o desde *Thonny*.

### 2. Carga de scripts y ejecución
1. **RP2040:** Con `SW2` en **A**, abrir *Thonny* y guardar el archivo `rp2040.py` del experimento deseado (`c1-sys`, `c2-pi` o `c3-pi-multicore`) como `main.py` en la memoria del RP2040.
2. **ESP32:** Cambiar `SW2` a **B**, abrir *Thonny* y subir los archivos `index.html` y `esp32.py` (guardado como `main.py`) a la memoria del ESP32.
3. **Interconexión UART:** Colocar el interruptor `SW3` en **ON** para habilitar la comunicación serial (115,200 baudios) entre ambos microcontroladores.
4. **Interfaz Web:** Conectarse a la red Wi-Fi generada por el ESP32 y abrir `http://192.168.1.1` en el navegador.

## Instrucciones de Compilación y Flasheo (FreeRTOS)

### 1. Compilación del código (RP2040)
Abrir una terminal dentro de `c4-freertos/rp2040/` y ejecutar los siguientes comandos para descargar las dependencias y compilar el binario:

```bash
mkdir -p build
cd build
cmake .. -DPICO_SDK_FETCH_FROM_GIT=1 -DFREERTOS_FETCH_FROM_GIT=1
make -j$(nproc)
