import math
from multiprocessing import Process, Manager, Lock
import os
import time
from pytun import TunTapDevice
import scapy.all as scape
import gzip
import argparse
from RF24 import RF24, RF24_PA_LOW, RF24_PA_MAX, RF24_2MBPS,RF24_CRC_8


manager = Manager()
outgoing = manager.Queue(maxsize=3)
rx_nrf = RF24(17, 0)
rx_nrf.begin()
rx_process = Process
tx_nrf = RF24(27, 10)
tx_nrf.begin()
tx_process = Process

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

    # Other than initial setup, set up so the RX-TX pair are listening on each other's channels. 
    return {
        'src': args.src if args.base else args.dst,
        'rx': args.rxchannel if args.base else args.txchannel,
        'dst':  args.dst if args.base else args.src,
        'tx': args.txchannel if args.base else args.rxchannel
    }

def fragment(packet, fragmentSize):
    """ Fragments and returns a list of bytes. This is done by finding the number of fragments we want, and then splitting the bytes-like object into chunks of appropriate size. 
    The input parameter is an IP packet (or any bytes-like object) and the size the method should fragment these into.  
    """
    sizeExHeader = fragmentSize - 1 # This is very likely to vary on implementation of fragmentation.
    frags = []
    dataRaw = bytes(packet)
    fragmented = False
    if len(dataRaw) <= sizeExHeader:
        frags.append(b'\xfd' + dataRaw)
    elif len(dataRaw) >= 1270: # Size selected due to compression efficiency, see the plot in the associated test-folder.
        # Compress the payload ONLY, not the IP header.  
        compressedPayload = gzip.compress(dataRaw[20:])
        frags = fragmentHelper(dataRaw[0:20] + compressedPayload, sizeExHeader)
        fragmented = True
    else:
        frags = fragmentHelper(dataRaw, sizeExHeader) 

    identifier = b'\xff' if not fragmented else b'\xfc'
    frags[-1] = identifier + frags[-1][1:] # Set the last fragment to be the identifier of a finished packet. 
    return frags


def fragmentHelper(data, size) -> list:
    tempList = []
    steps = math.ceil(len(data) / size)
    for _ in range(steps):
        data = b'\xfe' + data[0:size]
        tempList.append(data)
        data = data[size:]
    return tempList


def tx(nrf: RF24, address, channel, size):
    nrf.openWritingPipe(address)
    nrf.stopListening()
    print("Init TX on channel {}".format(channel))
    nrf.printDetails()
    while True:
            packet = outgoing.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.
            print("TX: {}".format(packet)) #TODO: DELETE. 
            fragments = fragment(packet, size)
            # Making sure we only check small packets for double speed-mode. 
            if len(fragments) == 1 and activateDouble(fragments[0]):
                ttl = int.from_bytes(fragments[0][-2:], 'big')                
                doubleTX(ttl)
            for i in fragments:
                #print("Fragment in TX: {}".format(scape.bytes_hex(i)))
                nrf.write(i)

def activateDouble(bytes) -> bool:
    return bytes[-7:-2] == b'\xff\xff\xff\xff\xff'

def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.openReadingPipe(1, address)
    nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    incoming = b''

    while True:
        hasData, _ = nrf.available_pipe() # Do not care about what pipe the data comes in at. 
        if hasData:
            packet = readFromNRF(nrf)
            # Here we need to check every packet for the required speed mode. This could slow down normal operations by a lot. Would need further testing. 
            if activateDouble(packet):
                ttl = int.from_bytes(packet[-2:], 'big')
                doubleRX(ttl)
            fragments = packet[0:1]
            remainingPacket = packet[1:]

            # Checks if the packet received is a fragment, is small enough to not be one, or is the last fragment. 
            if fragments == b'\xfe':
                # more  fragments
                incoming += remainingPacket
            elif fragments == b'\xff':
                # last fragment
                incoming += remainingPacket
                tun.write(incoming)
                incoming = b''
            elif fragments == b'\xfd':
                # size are less than 31 bytes
                tun.write(remainingPacket)
            elif fragments == b'\xfc':
                # Last fragment, compressed.
                incoming += remainingPacket
                dataRaw = gzip.decompress(incoming[20:])
                tun.write(incoming[0:20] + dataRaw)
            # An error occur if we do not account for packets not going through our fragment method. If so, just write it to the tun-interface. 
            else:
                tun.write(packet)

def readFromNRF(nrf: RF24):
    size = nrf.getDynamicPayloadSize()
    tmp = nrf.read(size)
    return bytes(tmp)
        

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

def doubleTX(timeToLive):
    print("Activating doubleTX for {} {}".format(timeToLive, "minute" if timeToLive == 1 else "minutes"))
    Process(target=doubleProcess, args=(timeToLive, rx_process)).start()
def doubleRX(timeToLive):
    print("Activating doubleRX for {} {}".format(timeToLive, "minute" if timeToLive == 1 else "minutes"))
    Process(target=doubleProcess, args=(timeToLive, tx_process)).start()


# The NRF process this takes in is the one to kill. 
lock = Lock()
def doubleProcess(timeToLive, nrf_process: Process):
    lock.acquire()
    # Ensure that no module is expecting ACKs.
    rx_nrf.setAutoAck(False)
    tx_nrf.setAutoAck(False)
    nrf_process.kill()
    print("Successfully shut down old operation. Starting new.".format(nrf_process))
     # Since we want the pairs to work together, we need to set the new tx to use the old RX values. 
    new_process = createDoubledProcess(nrf_process is tx_process)
    new_process.start()
    print("Letting this manager thread sleep for {} {}".format(timeToLive, "minute" if timeToLive == 1 else "minutes"))
    time.sleep(timeToLive * 600) # Supposed to be * 60. Is not currently for testing-purposes. 
 
    #new_process.kill()
    #new_process.join()
    print("Time expired, recreating old process.")
    old_process = createDoubledProcess(nrf_process is not tx_process)
    old_process.start()
    lock.release()

def createDoubledProcess(isTX):
    if not isTX:
        return Process(target=tx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'channel': vars['rx'], 'size':args.size})
    return Process(target=rx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'tun': tun, 'channel': vars['tx']})

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
   
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'tun': tun, 'channel': vars['rx']})
    rx_process.start()
    time.sleep(0.01)

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'channel': vars['tx'], 'size':args.size})
    tx_process.start()
    
    try:    
        while True:    
            packet = tun.read(tun.mtu)
            outgoing.put(packet, timeout=1)

    except KeyboardInterrupt:
        print("Main thread no longer listening on the TUN interface. ")

    tx_process.join()
    rx_process.join()
    # Setting the radios to stop listening seems to be best practice. 
    rx_nrf.stopListening()  
    tx_nrf.stopListening()
    tun.down()
    
    print("Threads ended, radios stopped listening, TUN interface down.")