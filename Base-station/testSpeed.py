from collections import defaultdict
import gzip
import math
from multiprocessing import Process, Manager, Event
import time
from pytun import TunTapDevice
import scapy.all as scape
import argparse
import struct
from RF24 import RF24, RF24_PA_LOW, RF24_2MBPS,RF24_CRC_8


manager = Manager()
outgoing = manager.Queue()
test = manager.Queue()
rx_nrf = RF24(17, 0)
rx_nrf.begin()

tx_nrf = RF24(27, 10)
tx_nrf.begin()

rxEvent = Event()
txEvent = Event()

transmissionBytes =0
RecevivedBytes = 0
transmission_time = 0.0
receving_time = 0.0000001

def fragment(packet, fragmentSize):

    """ Fragments and returns a list of bytes. This is done by finding the number of fragments we want, and then splitting the bytes-like object into chunks of appropriate size. 
    The input parameter is an IP packet (or any bytes-like object) and the size the method should fragment these into.  
    """
    sizeExHeader = fragmentSize - 2
    frags = []
    dataRaw = bytes(packet)
    if len(dataRaw) <= sizeExHeader:
        data = appendIndex(dataRaw, 0)
        frags.append(data)
    else: 
        numSteps = math.ceil(len(dataRaw)/sizeExHeader)
        for i in range(1, numSteps + 1):
            data = appendIndex(dataRaw[0:sizeExHeader], i)
            frags.append(data)
            dataRaw = dataRaw[sizeExHeader:]

    frags[-1] = b'\x00\x00' + frags[-1][2:] # Set the last fragment to be the identifier of a finished packet. 
    return frags

def appendIndex(data, index):
    indexBytes = index.to_bytes(2, 'big')
    return indexBytes + data

def fragmentHelper(data, size) -> list:
    tempList = []
    steps = math.ceil(len(data) / size)
    for _ in range(steps):
        data = b'\xfe' + data[0:size]
        tempList.append(data)
        data = data[size:]
    return tempList


def tx(nrf: RF24, address, channel, size):
    global transmissionBytes
    global transmission_time
    nrf.openWritingPipe(address)
    nrf.stopListening()
    print("Init TX on channel {}".format(channel))
    nrf.printDetails()
    currentTime = time.monotonic()
    while (time.monotonic() - currentTime) < 1000:
        packet = outgoing.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.
        print("TX: {}".format(packet)) #TODO: DELETE. 
        start_timer=time.monotonic()
        fragments = fragment(packet, size)
        
        # Making sure we only check small packets for double speed-mode. 
        if len(fragments) == 1 and activateDouble(fragments[0]):
            #ttl = fragments[0][-2:]
            nrf.write(b'\xff\xff\xff')
            transmissionBytes+=3                
            doubleTX()
        else:
            
            for i in fragments:
            #print("Fragment in TX: {}".format(scape.bytes_hex(i)))
            #print(i)
                transmissionBytes+=len(i)
                nrf.writeFast(i)
            end_timer =  time.monotonic()  
            transmission_time += end_timer-start_timer
            print("TXThroughput: {}".format(transmissionBytes/transmission_time))

def activateDouble(bytes) -> bool:
    return bytes[4:7] == b'\xff\xff\xff'
        
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    global receving_time 
    global RecevivedBytes
    nrf.openReadingPipe(1, address)
    nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    incoming = b''
    currentTime = time.monotonic()
    while (time.monotonic() - currentTime) < 1000:
        hasData, _ = nrf.available_pipe()
        if hasData:
            start_timer=time.monotonic()
            packet = readFromNRF(nrf)
            print(packet)
            if activateDouble(packet):
                #ttl = packet[-2:]
                doubleRX()
            incoming += packet[2:]
            #print("Packet index: {}".format(packet[0:2]))
            
            if packet[0:2] == b'\x00\x00':
                #print("Packet complete. Packet: {info} \n Size: {len}".format(info = scape.bytes_hex(incoming), len = len(incoming)))
                tun.write(incoming)
                RecevivedBytes += len(incoming)
                incoming = b''
                end_timer= time.monotonic()
                receving_time += end_timer-start_timer
                print("RXThroughput: {}".format(RecevivedBytes/receving_time))


"""
            packet = readFromNRF(nrf)
            if activateDouble(packet):
                ttl = packet[-2:]
                doubleRX(ttl)
            fragments = packet[0:1]
            remainingPacket = packet[1:]

            if fragments == b'\x00':
                incoming += remainingPacket
                tun.write(incoming)
            elif fragments == b'\xfe':
                incoming += remainingPacket
            else:
                tun.write(packet)
            
            elif fragments == b'\xfd':
                incoming += remainingPacket
                tun.write(incoming)
                incoming = b''
            elif fragments == b'\xfc':
                incoming += remainingPacket
                dataUncomp = gzip.decompress([incoming[20:]])
                tun.write(incoming[0:20] + dataUncomp)
            else:
                tun.write(packet)
"""


def readFromNRF(nrf: RF24):
    size = nrf.getDynamicPayloadSize()
    tmp = nrf.read(size)
    return bytes(tmp)
            
def setupNRFModules(args):
    
    rx_nrf.setDataRate(RF24_2MBPS) 
    tx_nrf.setDataRate(RF24_2MBPS)

    rx_nrf.setAutoAck(True)
    tx_nrf.setAutoAck(True)

    rx_nrf.payloadSize = 32
    tx_nrf.payloadSize = 32

    rx_nrf.setCRCLength(RF24_CRC_8)
    tx_nrf.setCRCLength(RF24_CRC_8)

    #Low power because we are using them next to one another! 

    rx_nrf.setPALevel(RF24_PA_LOW) 
    tx_nrf.setPALevel(RF24_PA_LOW)
    return {
    'src': args.src if args.base else args.dst,
    'rx': args.rxchannel if args.base else args.txchannel,
    'dst':  args.dst if args.base else args.src,
    'tx': args.txchannel if args.base else args.rxchannel
}

def sendPackages(tun):
    t = 0
    print("Inital sending packages")
    packet = scape.IP(src="20.0.0.1",dst = "20.0.0.2")/scape.UDP()/scape.Raw(load=struct.pack("!f", t))
    while t<10:
        
        start_timer =time.monotonic()
        #print(scape.raw(packet))
        tun.write(scape.raw(packet))
        print("Sending packages : {}".format(scape.raw(packet)))
        stop_timer =time.monotonic()
        t += stop_timer-start_timer

def setupIP(isBase):
    ipBase = '20.0.0.1'
    ipMobile = '20.0.0.2'
    tun = TunTapDevice()
    tun = TunTapDevice(name='longge')
    tun.addr = ipBase if isBase else ipMobile
    tun.dstaddr = ipMobile if isBase else ipBase
    tun.netmask = '255.255.255.252' # /30
    tun.mtu = 1500
    tun.up()
    print("TUN interface online, with values \n Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )
    return tun


def doubleTX():
    ttl = 1
    print("Activating doubleTX for {} {}".format(ttl, "minute" if ttl == 1 else "minutes"))
    rxEvent.set()
    test.put("T" + str(ttl))

def doubleRX():
    ttl = 1
    print("Activating doubleRX for {} {}".format(ttl, "minute" if ttl == 1 else "minutes"))
    txEvent.set()
    test.put("R" + str(ttl))

def init(vars, tun):
    rxEvent.clear()
    txEvent.clear()
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'tun': tun, 'channel': vars['rx']})
    rx_process.start()

    time.sleep(0.001)

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'channel': vars['tx'], 'size':args.size})
    tx_process.start()
    return rx_process, tx_process

def manageProcesses(vars, tun):
    rx_process, tx_process = init(vars, tun)
    while True:
        a = test.get()
        rx_nrf.setAutoAck(False)
        tx_nrf.setAutoAck(False)
        print("I'm up I'm up")
        #val = whichToDouble.value[0]
        #howLong = int.from_bytes(whichToDouble.value[1:], 'big')
        #print(a)
        val = a[0]
        print(val)
        #howLong = int.from_bytes(a[1:], 'big')
        if val == "T":
            print("Here?")
            rx_process.join()
            rxEvent.clear()
            txEvent.clear()
            tx2 = Process(target=tx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'channel': vars['rx'], 'size':args.size})
            tx2.start()
            print("Successful start of two TX-threads.")

            tx_process.join()
            print("Do we get here? we shouldn't.")
            """
            time.sleep(howLong)
            txEvent.set()
            print("Set the TX event flag, now the tx threads should fall in line.")
            tx2.join()
            print("At least one did.")
            tx_process.join()
            print("This one should not")
            print("???")
            """            
        elif val == "R":
            tx_process.join()
            rxEvent.clear()
            txEvent.clear()
            rx2 = Process(target=rx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'tun': tun, 'channel': vars['tx']})
            rx2.start()
            print("Successful start of two RX-threads.")
            rx_process.join()
            print("Do we get here? we shouldn't.")
            """
            time.sleep(howLong)
            rxEvent.set()
            rx2.join()
            txEvent.clear()
            rxEvent.clear()
            tx_process = threading.Thread(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'channel': vars['tx'], 'size':args.size})
            tx_process.start()
            """
        else:
            raise Exception("How did you get here? Unexpected wakeup, value not set.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NRF24L01+. Please note that you should use the same src/dst for the base and the mobile unit, put the isBase to False and let the program handle the RX/TX pair.')
    parser.add_argument('--base', dest='base', default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument('--src', dest='src', type=str, default='1Node', help='NRF24L01+\'s source address (Base)')
    parser.add_argument('--dst', dest='dst', type=str, default='2Node', help='NRF24L01+\'s destination address (Base)')
    parser.add_argument('--size', dest='size', type=int, default=32, help='Packet size') 
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=101, help='Tx channel', choices=range(0,125)) 
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=103, help='Rx channel', choices=range(0,125))
    
    args = parser.parse_args()
    #With a data rate of 2 Mbps, we need to at least tell the user that the channels should be at least 2Mhz from each other to ensure no cross talk. 
    if abs(args.txchannel - args.rxchannel) < 2:
        print("Do note that having tx and rx channels this close to each other can introduce cross-talk.")

    # Setup of NRF modules, channels, and the Tun interface. 
    vars = setupNRFModules(args)
    tun = setupIP(args.base)
    processHandler = Process(target=manageProcesses, args=(vars, tun))
    processHandler.start()
    #rx_process.start()
    #time.sleep(0.01)
    speedProcess = Process(target = sendPackages, kwargs={'tun':tun})
    speedProcess.start()

    freq = defaultdict(int)
    try:    
        while True:
            packet = tun.read(tun.mtu)
            freq[packet] += 1
            outgoing.put(packet)
            #print("In main thread, size of the queue is: {}".format(outgoing.qsize()))


    except KeyboardInterrupt:
        print("Main thread no longer listening on the TUN interface. ")

    processHandler.join()
    # Setting the radios to stop listening seems to be best practice. 
    rx_nrf.stopListening()  
    tx_nrf.stopListening()
    print(sorted(freq.items(), key = lambda x: x[1], reverse=True))
    tun.down()
    print("Threads ended, radios stopped listening, TUN interface down.")