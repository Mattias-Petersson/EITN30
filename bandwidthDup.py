import argparse
import math
import os
import time
from multiprocessing import Event, Manager, Process, current_process
import scapy.all as scape
from pytun import TunTapDevice
from RF24 import RF24, RF24_2MBPS, RF24_CRC_8, RF24_PA_LOW

manager = Manager()
outgoing = manager.Queue()
doubleRXTXQueue = manager.Queue()
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

    rx_nrf.setAutoAck(False)
    tx_nrf.setAutoAck(False)

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
    ipBase = '10.0.0.1'
    ipMobile = '10.0.0.2'
    tun = TunTapDevice()
    tun = TunTapDevice(name='longge')
    tun.addr = ipBase if isBase else ipMobile
    tun.dstaddr = ipMobile if isBase else ipBase
    tun.netmask = '255.255.255.252' # /30
    tun.mtu = 1500
    tun.up()
    if isBase:
        os.system('''
        sudo iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE
        sudo iptables -A FORWARD -i wlan0 -o longge -m state --state RELATED,ESTABLISHED -j ACCEPT
        sudo iptables -A FORWARD -i longge -o wlan0 -j ACCEPT
        ''')
    else:
        os.system('sudo ip route add default via {} dev longge'.format(ipBase))
    print("TUN interface online, with values \n Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )
    return tun

def init(vars, tun, base):
    rxEvent.clear()
    txEvent.clear()
    if(base):
        rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'tun': tun, 'channel': vars['tx']}) 
        tx_process = Process(target=rx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'tun': tun, 'channel': vars['rx']})
    else: 
        rx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'channel': vars['tx'], 'size':args.size})
        tx_process = Process(target=tx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'channel': vars['rx'], 'size':args.size})

    rx_process.start()
    time.sleep(0.1)
    tx_process.start()

    global startTime; startTime = time.monotonic() # Reset the timer, the bandwidth should not depend on the time required to set up the interfaces. 
    return rx_process, tx_process

#Fragments and returns a list of bytes. The packet of a size > 1270 bytes is assumed to be an IP packet with a minimal header (20b header, 1250b payload).
# This method also adds one byte of overhead to determine if a packet was fragmented or not. 
def fragment(packet, fragmentSize):
    sizeExHeader = fragmentSize - 1
    frags = []

    numSteps = math.ceil(len(packet) / sizeExHeader)
    for _ in range(numSteps):
        frag = b'\x02' + packet[0:sizeExHeader]
        frags.append(frag)
        packet = packet[sizeExHeader:]
    frags[-1] = b'\x00' + frags[-1][1:]
    return frags
    """ Did not get compression of payloads to work properly, due to how the TUN and the NRF behave. Comments in the report.  
        dataCompressed = packet[0:20] + gzip.compress(packet[20:])
        numSteps = math.ceil(len(dataCompressed) / sizeExHeader)
        for _ in range(numSteps):
            frag = b'\x02' + packet[0:sizeExHeader]
            frags.append(frag)
            packet = packet[sizeExHeader:]
        frags[-1] = b'\x01' + frags[-1][1:]
    return frags
    """

def tx(nrf: RF24, address, channel, size):
    nrf.openWritingPipe(address)
    nrf.stopListening()
    print("Init TX on channel {}".format(channel))
    nrf.printDetails()
    countTX = 0
    smallPacket = bytes(scape.IP(src="10.0.0.2", dst="10.0.0.1")/scape.UDP()/(b'A'))
    while (time.monotonic() - startTime) <= timeout:
        if txEvent.is_set():
            print("Interrupting process {}".format(current_process()))
            break
        packet = smallPacket
        #packet = outgoing.get(True) # Blocks until a packet is available. 
        if len(packet) <= 70 and packet[-4:-1] == b'\xff\xff\xff':
            ttl = packet[-1:]
            nrf.writeFast(b'\x00\xff\xff\xff' + ttl)
            doubleTX(ttl)
        else:
            fragments = fragment(packet, size)
            for i in fragments:
                if nrf.writeFast(i): # Write and check so that the writing was a success before appending it to the count of TX-output. 
                    countTX += len(i)
    toMegabits = round(countTX * 8 / (10**6), 2)
    print("TX count: {} Mbps".format(toMegabits / (time.monotonic() - startTime)))

    
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.openReadingPipe(1, address)
    nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    incoming = b''
    countRX = 0
    while (time.monotonic() - startTime) <= timeout:
        if rxEvent.is_set():
            print("Interrupting process {}".format(current_process()))
            break
        hasData, _ = nrf.available_pipe() # BLocks until available.
        if hasData:
            packet = readFromNRF(nrf) 
            countRX += len(packet)
            if packet[0:4] == b'\x00\xff\xff\xff':
                ttl = packet[4:5]
                doubleRX(ttl)
            else: 
                incoming += packet[1:]                
                if packet[0:1] == b'\x00':
                    tun.write(incoming)
                    incoming = b''
                """   No packets will be compressed in the final version sadly. 
                elif packet[0:1] == b'\x01':
                    decompressedData = incoming[0:20] + gzip.decompress(incoming[20:])
                    tun.write(decompressedData)
                    incoming = b''
                """
    toMegabits = round(countRX * 8 / (10**6), 2)
    print("RX count: {} Mbps".format(toMegabits / (time.monotonic() - startTime)))


def readFromNRF(nrf: RF24):
    size = nrf.getDynamicPayloadSize()
    tmp = nrf.read(size)
    return bytes(tmp)
            
def doubleTX(ttl):
    duration = int.from_bytes(ttl, 'big')
    print("Activating doubleTX for {} {}".format(duration, "minute" if duration == 1 else "minutes"))
    rxEvent.set()
    doubleRXTXQueue.put(["T", duration])

def doubleRX(ttl):
    duration = int.from_bytes(ttl, 'big')
    print("Activating doubleRX for {} {}".format(duration, "minute" if duration == 1 else "minutes"))
    txEvent.set()
    doubleRXTXQueue.put(["R", duration])


def manageProcesses(vars, tun, base):
    rx_process, tx_process = init(vars, tun, base)
    while (time.monotonic() - startTime) <= timeout:
        values = doubleRXTXQueue.get()
        rx_nrf.setAutoAck(False)
        tx_nrf.setAutoAck(False)
        if values[0] == "T":
            print("Hey")
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
        print("Do note that having tx and rx channels this c, 'pipe': 3lose to each other can introduce cross-talk when using the maximum speed of 2Mbps.")

    # Setup of NRF modules, channels, and the Tun interface. 
    vars = setupNRFModules(args)
    tun = setupIP(args.base)
    processHandler = Process(target=manageProcesses, args=(vars, tun, args.base))
    processHandler.start()
    """
    try:    
        while True:
            packet = tun.read(tun.mtu)
            outgoing.put(packet)


    except KeyboardInterrupt:
        print("Main thread no longer listening on the TUN interface. ")
    """
    processHandler.join()
    # Setting the radios to stop listening is considered best practice. 
    rx_nrf.stopListening()  
    tx_nrf.stopListening()
    tun.down()
    print("Threads ended, radios stopped listening, TUN interface down.")