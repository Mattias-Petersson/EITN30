from collections import defaultdict
import gzip
import math
from multiprocessing import Process, Manager, Event
import time
from pytun import TunTapDevice
import scapy.all as scape
import argparse
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

#Fragments and returns a list of bytes. The packet of a size > 1270 bytes is assumed to be an IP packet with a minimal header (20b header, 1250b payload).
# This method also adds one byte of overhead to determine if a packet was fragmented or not. 
def fragment(packet, fragmentSize):
    sizeExHeader = fragmentSize - 1
    frags = []
    if len(packet) <= 1270:
        numSteps = math.ceil(len(packet) / sizeExHeader)
        for _ in range(numSteps):
            frag = b'\x02' + packet[0:sizeExHeader]
            frags.append(frag)
            packet = packet[sizeExHeader:]
        frags[-1] = b'\x00' + frags[-1][1:]
    else:
        dataCompressed = packet[0:20] + gzip.compress(packet[20:])
        numSteps = math.ceil(len(dataCompressed) / sizeExHeader)
        for _ in range(numSteps):
            frag = b'\x02' + packet[0:sizeExHeader]
            frags.append(frag)
            packet = packet[sizeExHeader:]
        frags[-1] = b'\x01' + frags[-1][1:]
    return frags


def tx(nrf: RF24, address, channel, size):
    nrf.openWritingPipe(address)
    nrf.stopListening()
    print("Init TX on channel {}".format(channel))
    nrf.printDetails()
    while True:
        packet = outgoing.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.
        print("TX: {} \n Len: {}".format(packet, len(packet))) #TODO: DELETE. 
        if len(packet) <= 70:
            if packet[-4:-1] == b'\xff\xff\xff':
                ttl = packet[-1:]
                doubleTX(ttl)
            nrf.write(packet)
        else:
            fragments = fragment(packet, size)
            for i in fragments:
                nrf.write(i)

    
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.openReadingPipe(1, address)
    nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    incoming = b''
    #currentTime = time.monotonic()
    #while (time.monotonic() - currentTime) < 1000:
    while True:
        hasData, _ = nrf.available_pipe()
        if hasData:
            packet = readFromNRF(nrf)
            print("RX: {}".format(packet))
            if packet[2:5] == b'\xff\xff\xff':
                ttl = packet[5:6]
                doubleRX(ttl)
            incoming += packet[1:]
            #print("Packet index: {}".format(packet[0:2]))
            
            if packet[0:1] == b'\x00':
                #print("Packet complete. Packet: {info} \n Size: {len}".format(info = scape.bytes_hex(incoming), len = len(incoming)))
                tun.write(incoming)
                incoming = b''
            elif packet[0:1] == b'\x01':
                decompressedData = incoming[0:20] + gzip.decompress(incoming[20:])
                tun.write(decompressedData)
                incoming = b''
            #else: 
            #    tun.write(incoming)

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
            

def activateDouble(bytes) -> bool:
    return bytes[-4:-1] == b'\xff\xff\xff'
    
def doubleTX(ttl):
    print("Activating doubleTX for {} {}".format(ttl, "minute" if ttl == b'\x01' else "minutes"))
    rxEvent.set()
    test.put(b'T' + ttl)

def doubleRX(ttl):
    print("Activating doubleRX for {} {}".format(ttl, "minute" if ttl == b'\x01' else "minutes"))
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
        if val == b'T':
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
        elif val == b'R':
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