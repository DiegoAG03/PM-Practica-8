import os
import machine
import network
import utime
import usocket
import _thread

# ## ##################################
# Globals
# ## ##################################
nic   = None  # Network interface controller
s_web = None  # Socket for web server

# ## ##################################
# Shared vars and mutexes
# ## ##################################
svNCID = 0  # Next call id
lkNCID = _thread.allocate_lock()

uart   = None  # Communication device with RP2040
lkUART = _thread.allocate_lock()

svRPCResponses = {}  # Dic with RPC responses received
lkRPCResponses = _thread.allocate_lock()


# ## ##################################
# Setup Functions
# ## ##################################
def setup():
    setupUART()
    setupWiFi()
    setupSockets()


def setupWiFi():
    global nic
    # Enable interface as WiFi access point
    nic = network.WLAN(network.AP_IF)
    nic.active(False)
    nic.config(
        ssid='ESP32 - DAG',
        security=network.AUTH_WPA2_PSK,
        key='12345678',
    )
    nic.active(True)
    nic.ifconfig(('192.168.1.1', '255.255.255.0', '192.168.1.1', '192.168.1.1'))
    network.hostname('ESP32 - DAG')


def setupSockets():
    global s_web
    while not nic.active():
        utime.sleep(0.25)
    print('AP initialized successfully')
    s_web = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
    s_web.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
    ip = nic.ifconfig()[0]
    s_web.bind((ip, 80))
    s_web.listen()
    print(f'Listening on {ip}:80')


def setupUART():
    global uart
    pin_tx = machine.Pin(17, machine.Pin.OUT)
    pin_rx = machine.Pin(16, machine.Pin.IN)
    uart = machine.UART(
        2,
        baudrate=115200,
        tx=17,
        rx=16,
        timeout=1,
        timeout_char=1,
    )


# ## ##################################
# Functions
# ## ##################################
@micropython.native
def calcPi(n, start, stop):
    psum = 0.0
    dx = 1.0 / n
    for i in range(start, stop):
        x = dx * i
        psum += 4.0 / (1.0 + x * x)
    return dx * psum


def distributedPiCalc(n):
    '''Estimates the value of Pi using n terms in distributed fashion'''
    t1 = n // 3
    t2 = (2 * n) // 3
    
    # 1. First we send the rpc requests
    reqid1 = rpcReqS('pi', n, 0, t1)
    reqid2 = rpcReqS('pi', n, t1, t2)

    # 2. Then we calculate pi locally in parallel in the ESP32
    pi = calcPi(n, t2, n)

    # 3. Now we wait for the remote results from the RP2040
    res1 = rpcResW(reqid1, timeout=60000)
    res2 = rpcResW(reqid2, timeout=60000)

    # 4. Finally we compute and return the whole answer
    try:
        res1 = float(res1)
        res2 = float(res2)
    except:
        return None
    pi += res1 + res2
    return pi


def fetchUriParams(sreq):
    print(f'fetchUriParams over {sreq}')
    up = {}
    qmpos = indexOf(sreq, '?')
    if qmpos == -1:
        print('up:', up)
        return up
    parts = sreq[qmpos + 1 :].split('&')
    for p in parts:
        pparts = p.split('=', 2)
        key = pparts[0]
        value = pparts[1] if len(pparts) > 1 else None
        up[key] = value
    print('up:', up)
    return up


def indexOf(s, c, offset=0):
    for i in range(offset, len(s)):
        if s[i] == c:
            return i
    return -1


def rpcReqS(func, *args):
    '''Sends a Request for RPC'''
    global lkNCID, svNCID
    print('rpcReqS args: ', args)
    # 1. Validate function signature
    if not isinstance(func, str):
        return None
    if args:
        sparams = ','.join([str(a) for a in args])
    else:
        sparams = ''

    # 2. Generate unique call Id (numeric autoincrement)
    with lkNCID:
        cid = svNCID
        svNCID += 1

    # 3. Send RPC call request
    reqid = f'{cid}:{func}'
    with lkUART:
        uart.write(f'{reqid}:{sparams}\n')
    print(f'UART <= {reqid}:{sparams}')
    return reqid


def rpcResW(reqid, timeout=2000):
    '''Awaits for the response of an RPC request'''
    elapsed = 0
    while elapsed < timeout:
        with lkRPCResponses:
            if reqid in svRPCResponses:
                r = svRPCResponses[reqid]
                del svRPCResponses[reqid]
                return r

        utime.sleep_ms(10)
        elapsed += 10
    print(f'rpcResW: {reqid} not in {svRPCResponses}')
    return None


def rpc(func, *args):
    '''Performs a blocking RPC call'''
    reqid = rpcReqS(func, *args)
    return rpcResW(reqid)


def serveLed(sreq):
    up = fetchUriParams(sreq)
    if 'on' in up:
        status = rpc('led', up['on'])
    else:
        status = rpc('led')
    if status is None:
        return 'HTTP500: Internal server error\n'
    return status


def servePi(sreq):
    up = fetchUriParams(sreq)
    try:
        if 'n' not in up:
            return 'HTTP400: Bad request\n'
        up['n'] = int(up['n'])
    except:
        return 'HTTP400: Bad request\n'

    time_start = utime.ticks_ms()
    pi = distributedPiCalc(up['n'])
    elapsed_ms = utime.ticks_diff(utime.ticks_ms(), time_start)

    pi = distributedPiCalc(up['n'])
    if pi is None:
        return 'Timeout'
    return f'{pi:0.8} in {elapsed_ms} ms'


def serveTemp(sreq):
    temp = rpc('temp')
    if temp is None:
        return ''
    return f'{float(temp):.1f}'


def serveWeb():
    cnn, addr = s_web.accept()
    print(f'Client connected from {str(addr)}')
    request = cnn.recv(1024)
    sreq = request.decode('utf-8')
    print(f'Request: {sreq[:indexOf(sreq, "\n")]}')

    if not sreq.startswith('GET '):
        cnn.send('HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\nBad request\n')
        cnn.close()
        return

    sreq = sreq[4 : indexOf(sreq, ' ', 5)]

    if sreq.startswith('/?') or sreq.startswith('/index.htm'):
        payload = webpage()
    elif sreq.startswith('/led'):
        payload = serveLed(sreq)
    elif sreq.startswith('/pi'):
        payload = servePi(sreq)
    elif sreq.startswith('/temp'):
        payload = serveTemp(sreq)
    elif sreq == '/':
        payload = webpage()
    else:
        payload = 'HTTP404: Not found\n'

    print(f'Response: {payload.strip()[:200]}')
    header = 'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n'
    cnn.send(header + payload)
    cnn.close()


def webpage():
    try:
        with open('index.html', 'r') as f:
            payload = f.read()
    except:
        payload = None

    if not payload:
        return 'HTTP404: Page not found\n'

    temp = rpc('temp')
    led = rpc('led')
    payload = payload.replace('<!--led-->', str(led) if led is not None else 'Error', 1)
    payload = payload.replace('<!--temp-->', str(temp) if temp is not None else 'Error', 1)
    return payload


def rpcTask(arg):
    while True:  # Forever
        utime.sleep_ms(10)

        # 1. Read a line from the serial port
        with lkUART:
            if not uart.any():
                continue
            line = uart.readline()
        if not line:
            continue
        line = line.decode('utf-8')
        line = line.strip()
        if not line or len(line) < 3:
            continue
        print(f'RP2040: {line}')

        # 2. Validate data
        scpos1 = indexOf(line, ':', 0)
        if scpos1 == -1:
            continue
        scpos2 = indexOf(line, ':', scpos1 + 1)
        if scpos2 == -1:
            continue

        # 3. Extract valid data: reqid and result
        reqid = line[:scpos2]
        result = line[scpos2 + 1 :]

        # 4. Add data to the dictionary
        with lkRPCResponses:
            svRPCResponses[reqid] = result
            print(svRPCResponses)


# ## ##################################
# Main
# ## ##################################
def main():
    setup()

    # Start RPC listener task
    _thread.start_new_thread(rpcTask, [None])
    # Main thread will serve web requests forever
    while True:
        serveWeb()


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
