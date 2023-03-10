from collections import defaultdict
import gzip
import math
from multiprocessing import Process, Manager, Event, current_process
#import multiprocessing as mp
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

startTime = time.monotonic()
timeout = 20
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

def init(vars, tun):
    rxEvent.clear()
    txEvent.clear()
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'tun': tun, 'channel': vars['rx']})
    rx_process.start()

    time.sleep(0.001)

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'channel': vars['tx'], 'size':args.size})
    tx_process.start()
    return rx_process, tx_process

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
    smallPacket = bytes(scape.IP(src="20.0.0.2", dst="20.0.0.1")/scape.UDP()/(b'A'*1000))
    count = 0
    while (time.monotonic() - startTime) <= timeout:
        if txEvent.is_set():
            print("Thread interrupting: {}".format(current_process()))
            break
        packet = smallPacket #This method blocks until available. True is to ensure that happens if default ever changes.
        
        #print("TX: {}".format(packet)) #TODO: DELETE. 
        if len(packet) <= 70 and packet[-4:-1] == b'\xff\xff\xff':
            ttl = packet[-1:]
            count += len(5)
            nrf.writeFast(b'\x00\xff\xff\xff\x01')
            doubleTX(ttl)
        fragments = fragment(packet, size)
        for i in fragments:
            count += len(i)
            nrf.write(i)

        
    print("TX count: {} bps".format((count * 8) / (time.monotonic() - startTime)))


    
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.openReadingPipe(1, address)
    nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    incoming = b''
    countRX = 0
    while (time.monotonic() - startTime) <= timeout:
        if rxEvent.is_set():
            print("Thread interrupting: {}".format(current_process()))
            break
        hasData, _ = nrf.available_pipe()
        if hasData:
            packet = readFromNRF(nrf)
            countRX += len(packet)
            #print(countRX)
            #print("RX: {}".format(packet))
            if packet[0:4] == b'\x00\xff\xff\xff':
                ttl = packet[4:5]
                doubleRX(ttl)
            else: 
                incoming += packet[1:]                
                if packet[0:1] == b'\x00':
                    #print("Packet complete. Packet: {info} \n Size: {len}".format(info = scape.bytes_hex(incoming), len = len(incoming)))
                    tun.write(incoming)
                    incoming = b''
                elif packet[0:1] == b'\x01':
                    decompressedData = incoming[0:20] + gzip.decompress(incoming[20:])
                    tun.write(decompressedData)
                    incoming = b''
    print("RX count: {} bps".format((countRX * 8) / (time.monotonic() - startTime)))


def readFromNRF(nrf: RF24):
    size = nrf.getDynamicPayloadSize()
    tmp = nrf.read(size)
    return bytes(tmp)
            

def activateDouble(bytes) -> bool:
    return bytes[-4:-1] == b'\xff\xff\xff'
    
def doubleTX(ttl):
    duration = int.from_bytes(ttl, 'big')
    print("Activating doubleTX for {} {}".format(duration, "minute" if duration == 1 else "minutes"))
    rxEvent.set()
    test.put(["T", duration])

def doubleRX(ttl):
    duration = int.from_bytes(ttl, 'big')
    print("Activating doubleRX for {} {}".format(duration, "minute" if duration == 1 else "minutes"))
    txEvent.set()
    test.put(["R", duration])


def manageProcesses(vars, tun):
    rx_process, tx_process = init(vars, tun)
    while (time.monotonic() - startTime) <= timeout:
        values = test.get()
        rx_nrf.setAutoAck(False)
        tx_nrf.setAutoAck(False)
        if values[0] == "T":
            rx_process.join()
            rxEvent.clear()
            txEvent.clear()
            tx2 = Process(target=tx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'channel': vars['rx'], 'size':args.size})
            tx2.start()
            print("Successful start of two TX-threads.")

            time.sleep(values[1] * 60)
            txEvent.set()
            outgoing.put(b'\x00')
            print("Set the TX event flag, now the tx threads should fall in line.")
            tx2.join()
            txEvent.clear()
            rx_process, tx_process = init(vars, tun)
            print("Back to normal configuration of RX/TX pair.")
                       
        elif values[0] == "R":
            outgoing.put(b'\x00')
            tx_process.join()
            rxEvent.clear()
            txEvent.clear()

            rx2 = Process(target=rx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'tun': tun, 'channel': vars['tx']})
            rx2.start()
            print("Successful start of two RX-threads.")
            
            time.sleep(values[1] * 60)
            rxEvent.set()
            print("Set the RX event flag, now the rx threads should fall in line.")
            rx2.join()
            rxEvent.clear()
            rx_process, tx_process = init(vars, tun)
            print("Back to normal configuration of RX/TX pair.")
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

  #  try:    
  #      while (time.monotonic() - startTime) <= timeout:

            #packet = tun.read(tun.mtu)
            #outgoing.put(packet)


   # except KeyboardInterrupt:
   #     print("Main thread no longer listening on the TUN interface. ")

    processHandler.join()
    # Setting the radios to stop listening seems to be best practice. 
    rx_nrf.stopListening()  
    tx_nrf.stopListening()
    tun.down()
    print("Threads ended, radios stopped listening, TUN interface down.")