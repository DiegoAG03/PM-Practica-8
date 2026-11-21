import os
import machine
import utime
import _thread
import ucollections

# ## ##################################
# Globals
# ## ##################################
led     = None # Centinel LED

# ## ##################################
# Shared vars and mutexes
# ## ##################################
uart    = None # Communication device with ESP32
lkUART  = _thread.allocate_lock()

adc     = None # ADC for reading temperature
lkADC   = _thread.allocate_lock()

rpcQ    = None   # Queue for received function calls
lkRPCQ  = _thread.allocate_lock()

svLedOn = False  # Is the centinnel LED on?
lkLedOn = _thread.allocate_lock()


# ## ##################################
# Setup Functions
# ## ##################################
def setup():
	global led, rpcQ
	setupADC()
	setupUART()
	led  = machine.Pin(25, machine.Pin.OUT)
	rpcQ = ucollections.deque((), 10)
# end def


def setupADC():
	global adc
	adc = machine.ADC(4)
	adc.read_u16()
# end def


def setupUART():
	global uart
	pin_tx = machine.Pin(0, machine.Pin.OUT)
	pin_rx = machine.Pin(1, machine.Pin.IN)
	uart   = machine.UART(0, baudrate=115200,
		tx=pin_tx, rx=pin_rx,
		timeout=1,
		timeout_char=1)
# end def


# ## ##################################
# Functions
# ## ##################################
def calcPi(n, start, stop):
	psum = 0.0
	dx = 1.0/n

	for i in range(start, stop):
		x = dx * i
		psum+= 4.0/(1.0 + x ** 2)
	return dx * psum
# end def


def fetchRequests():
	s = None

	with lkUART:
		if not uart.any(): return
		try:
			s = uart.readline()
		except:
			return

	try:
		if s is None: return
		s = s.decode('utf-8')
		s = s.strip()
		if s is None or len(s) < 3: return
	except:
		return

	with lkRPCQ:
		rpcQ.append(s)
	print('ESP32: ', s, len(s), 'bytes')
# end def


def readTemp():
	K   = -0.029259019

	# Read temperature from ADC
	x = adc.read_u16()
	temp = x * K + 437.23
	print(f'Temp: {temp} °C')
	return temp
# end def


def returnRPC(i, f, retval):
	with lkUART:
		uart.write(f'{i}:{f}:{retval}\n')
	print(f'UART <= {i}:{f}:{retval}')
# end def


def serveLed(i, f, p):
	global svLedOn
	try:
		if len(p) > 0:
			ledStat = int(p[0])
		else:
			ledStat = None
	except:
		ledStat = None

	with lkLedOn:
		if ledStat is not None:
			svLedOn = bool(ledStat)
			if svLedOn:
				led.on()
			else:
				led.off()
		else:
			ledStat = svLedOn

	returnRPC(i, f, int(ledStat))
#end def


def serveNot(s):
	with lkUART:
		uart.write(f'{s}:-1\n')
#end def


def servePi(i, f, p):
	if len(p) != 3:
		returnRPC(i, f, -1)
		return

	try:
		n     = int(float(p[0]))
		start = int(float(p[1]))
		stop  = int(float(p[2]))
	except:
		returnRPC(i, f, -1)
		return

	res = calcPi(n, start, stop)
	returnRPC(i, f, res)
#end def


def serveTemp(i, f, p):
	temp = readTemp()
	returnRPC(i, f, temp)
# end def


def serveRPC(s):
	i, f, p = splitRPC(s)

	if f == 'temp':
		serveTemp(i, f, p)
	elif f == 'led':
		serveLed(i, f, p)
	elif f == 'pi':
		servePi(i, f, p)
	else:
		serveNot(s)
#end def


def splitRPC(s):
	parts = s.split(':', 3)
	if len(parts) < 2:
		return None, None, None
	elif len(parts) < 3:
		parts.append('')
	i = parts[0]
	f = parts[1]
	p = parts[2].split(',')
	return i, f, p
# end def


def core1Task(arg):
	print('Core1 task: Running')
	while True:
		# 1. Retrieve requests from UART
		fetchRequests()

		# 2. Lock Q. If there is a request,
		# dequeue it and serve it.
		s = None
		with lkRPCQ:
			if len(rpcQ) > 0:
				s = rpcQ.popleft()
		if s is not None:
			print(f'Core1: Dispatch: «{s}»')
			serveRPC(s)
		# If there are no requests,
		# go idle for 1ms
		# utime.sleep(0.001)
#end def


# ## ##################################
# Main
# ## ##################################
def main():
	setup()

	# Start Core1 task:
	_thread.start_new_thread(core1Task, [None] )

	# Main thread (Core0) will serve RPC requests forever
	while True:
		# 1. Retrieve requests from UART
		fetchRequests()

		# 2. Lock Q. If there is a request,
		# dequeue it and serve it.
		s = None
		with lkRPCQ:
			if len(rpcQ) > 0:
				s = rpcQ.popleft()
		if s is not None:
			print(f'Core0: Dispatch «{s}»')
			serveRPC(s)

		# s = input('?: ')
		# with lkRPCQ:
		# 	rpcQ.append(s)
# end def


# ## ##################################
# Anchor
# ## ##################################
if __name__ == '__main__':
	try:
		main()
	except Exception as e:
		print('--- Caught Exception ---')
		import sys
		sys.print_exception(e)
		print('----------------------------')
