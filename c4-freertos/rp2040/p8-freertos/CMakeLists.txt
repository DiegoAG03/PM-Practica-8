cmake_minimum_required(VERSION 3.13)

# Importar el SDK desde la tarjeta
include(../picoSDK_import.cmake)

# Importar el Kernel de FreeRTOS
include(FreeRTOS_Kernel_import.cmake)

project(p8-freertos C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(p8-freertos main.c aux.c)

# Incluir el directorio actual para que el compilador detecte FreeRTOSConfig.h
target_include_directories(p8-freertos PRIVATE ${CMAKE_CURRENT_LIST_DIR})

# Ligar librerías base, periféricos (ADC/UART) y FreeRTOS
target_link_libraries(p8-freertos
    pico_stdlib
    hardware_adc
    hardware_uart
    FreeRTOS-Kernel
    FreeRTOS-Kernel-Heap4
)

# Salida estándar por USB; UART0 libre para RPC con el ESP32
pico_enable_stdio_usb(p8-freertos 1)
pico_enable_stdio_uart(p8-freertos 0)

# Generar el archivo .uf2
pico_add_extra_outputs(p8-freertos)
