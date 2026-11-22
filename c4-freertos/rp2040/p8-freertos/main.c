/*----------------------------------------------------------------
 * FreeRTOS en sistema distribuido
 * Autor: Diego Ambrosio González
 *----------------------------------------------------------------
*/

// Librerias del Kernel
#include <FreeRTOS.h>
#include <task.h>
#include <semphr.h>
#include <queue.h>

// Librerias de hardware
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <pico/stdlib.h>

#include <hardware/gpio.h>
#include <hardware/adc.h>
#include <hardware/uart.h>

// Macros para periféricos
#define LED_PIN        25
#define ADC_TEMP       4
#define UART_ID        uart0
#define BAUD_RATE      115200
#define UART_TX_PIN    0
#define UART_RX_PIN    1

// Macros para RPC
#define RPC_MSG_LEN   64
#define RPC_QUEUE_LEN 10

// Handles de FreeRTOS y estado del LED
static QueueHandle_t     rpcQueue    = NULL;
static SemaphoreHandle_t xUartMutex  = NULL;
static SemaphoreHandle_t xAdcMutex   = NULL;
static SemaphoreHandle_t xLedMutex   = NULL;
static bool              svLedStatus = false;

// Configuración de hardware
static void setup     ();
static void setupLED  ();
static void setupADC  ();
static void setupUART ();

// Prototipos de las funciones
static double calcPi  (long n, long start, long stop);
static void servePi   (const char *id, const char *func, const char *params);
static void serveLed  (const char *id, const char *func, const char *params);
static float readTemp (void);
static void serveTemp (const char *id, const char *func);
static void returnRPC (const char *id, const char *func, const char *retval);
static void serveRPC  (char *msg);

// Prototipos de las tareas
static void vUartRxTask    ( void *param );
static void vRpcWorkerTask ( void *param );

// Función principal
void main( void ){
	setup();

	// Primitivas de comunicación y sincronización (Cola RPC y Mutexes) 
	rpcQueue   = xQueueCreate(RPC_QUEUE_LEN, RPC_MSG_LEN);
    xUartMutex = xSemaphoreCreateMutex();
    xAdcMutex  = xSemaphoreCreateMutex();
    xLedMutex  = xSemaphoreCreateMutex();

	// Tarea para leer el buffer circular y meter RPCs a la cola
	xTaskCreate( vUartRxTask,               // Función que implementa la tarea.
				 "UART_RX",                 // Nombre asignado a la tarea.
				 1024,                      // Tamaño asignado en el stack para la tarea.
				 NULL,                      // Parámetro asignado a la tarea.
				 2,                         // Prioridad asignada a la tarea.
				 NULL );                    // Identificador de la tarea.

	// Workers que FreeRTOS SMP distribuye en ambos núcleos 
	xTaskCreate( vRpcWorkerTask,            // Función que implementa la tarea.
				 "Worker0",                 // Nombre asignado a la tarea.
				 1024,                      // Tamaño asignado en el stack para la tarea.
				 NULL,                      // Parámetro asignado a la tarea.
				 1,                         // Prioridad asignada a la tarea.
				 NULL );                    // Identificador de la tarea.

	xTaskCreate( vRpcWorkerTask,            // Función que implementa la tarea.
				 "Worker1",                 // Nombre asignado a la tarea.
				 1024,                      // Tamaño asignado en el stack para la tarea.
				 NULL,                      // Parámetro asignado a la tarea.
				 1,                         // Prioridad asignada a la tarea.
				 NULL );                    // Identificador de la tarea.

	vTaskStartScheduler();
	for( ;; );
}

// Configuración del GPIO del LED
static void setupLED(){
	gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    gpio_put(LED_PIN, 0);
}

// Configuración del ADC
static void setupADC(){
	adc_init();
    adc_set_temp_sensor_enabled(true);
    adc_select_input(ADC_TEMP);
}

// Configuración del UART
static void setupUART(){
	uart_init(UART_ID, BAUD_RATE);
    gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART_RX_PIN, GPIO_FUNC_UART);
}

// Configuración del hardware
static void setup(){
	stdio_init_all();

	// Inicialización de perifericos
	setupLED();
	setupADC();
	setupUART();
}

// Funciones de control de perifericos
static double calcPi(long n, long start, long stop) {
    double psum = 0.0;
    double dx   = 1.0 / (double)n;

    for (long i = start; i < stop; i++) {
        double x = dx * (double)i;
        psum += 4.0 / (1.0 + x * x);
    }
    return dx * psum;
}

static void servePi(const char *id, const char *func, const char *params) {
    long n = 0, start = 0, stop = 0;
    if (params == NULL || sscanf(params, "%ld,%ld,%ld", &n, &start, &stop) != 3 || n <= 0) {
        returnRPC(id, func, "-1");
        return;
    }
    double res = calcPi(n, start, stop);
    char buf[32];
    snprintf(buf, sizeof(buf), "%.10f", res);
    returnRPC(id, func, buf);
}

static void serveLed(const char *id, const char *func, const char *params) {
	bool status = false;
    if (xSemaphoreTake(xLedMutex, portMAX_DELAY) == pdTRUE) {
        if (params != NULL && params[0] != '\0') {
            svLedStatus = (atoi(params) != 0);
            gpio_put(LED_PIN, svLedStatus ? 1 : 0);
        }
        status = svLedStatus;
        xSemaphoreGive(xLedMutex);
    }
    returnRPC(id, func, status ? "1" : "0");
}

static float readTemp(void) {
    float temp = 0.0f;
    if (xSemaphoreTake(xAdcMutex, portMAX_DELAY) == pdTRUE) {
        uint16_t raw = adc_read();
        float voltage = raw * 3.3f / (1 << 12);
        temp = 27.0f - (voltage - 0.706f) / 0.001721f;
        xSemaphoreGive(xAdcMutex);
    }
    return temp;
}

static void serveTemp(const char *id, const char *func) {
    float temp = readTemp();
    char  buf[24];
    snprintf(buf, sizeof(buf), "%.4f", temp);
    returnRPC(id, func, buf);
}

// Funciones del protocolo de comunicación y despacho RPC
static void returnRPC(const char *id, const char *func, const char *retval) {
    char out[RPC_MSG_LEN];
    snprintf(out, sizeof(out), "%s:%s:%s\n", id, func, retval);

    if (xSemaphoreTake(xUartMutex, portMAX_DELAY) == pdTRUE) {
        uart_puts(UART_ID, out);
        xSemaphoreGive(xUartMutex);
    }
}

static void serveRPC(char *msg) {
    char *sep1 = strchr(msg, ':');
    if (!sep1) return;
    *sep1 = '\0';

    char *id     = msg;
    char *func   = sep1 + 1;
    char *params = "";

    char *sep2 = strchr(func, ':');
    if (sep2) {
        *sep2 = '\0';
        params = sep2 + 1;
    }

    if (strcmp(func, "temp") == 0) {
        serveTemp(id, func);
    } else if (strcmp(func, "led") == 0) {
        serveLed(id, func, params);
    } else if (strcmp(func, "pi") == 0) {
        servePi(id, func, params);
    } else {
        returnRPC(id, func, "-1");
    }
}

// Tareas de FreeRTOS (recepción UART y despacho concurrente)
static void vUartRxTask(void *param ) {
    char   buf[RPC_MSG_LEN];
    size_t idx = 0;

    for (;;) {
        while (uart_is_readable(UART_ID)) {
            char c = uart_getc(UART_ID);
            if (c == '\r') continue; // Ignorar retorno de carro

            if (c == '\n') {
                if (idx >= 3) {
                    buf[idx] = '\0'; // Cerrar cadena en C
                    xQueueSend(rpcQueue, buf, portMAX_DELAY);
                }
                idx = 0; // Reiniciar buffer para la siguiente trama
            } else if (idx < RPC_MSG_LEN - 1) {
                buf[idx++] = c;
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1)); // Cede el CPU 1 ms si no hay datos
    }
}

static void vRpcWorkerTask(void *param ) {
    char msg[RPC_MSG_LEN];

    for (;;) {
        // Espera bloqueada hasta que haya una petición en la cola
        if (xQueueReceive(rpcQueue, msg, portMAX_DELAY) == pdTRUE) {
            serveRPC(msg);
        }
    }
}