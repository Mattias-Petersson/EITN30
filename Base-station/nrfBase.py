import math
from multiprocessing import Process, Queue
import time
from pytun import TunTapDevice
import scapy.all as scapy
import scapy.all as scapy
import argparse
from RF24 import RF24, RF24_PA_LOW, RF24_2MBPS,RF24_CRC_8
from RF24 import RF24, RF24_PA_LOW, RF24_2MBPS,RF24_CRC_8

global outgoing; outgoing = Queue()
global rx_process 
global tx_process
global rx_nrf
global tx_nrf


def fragment(packet, fragmentSize):

    """ Fragments and returns a list of bytes. This is done by finding the number of fragments we want, and then splitting the bytes-like object into chunks of appropriate size. 
    The input parameter is an IP packet (or any bytes-like object) and the size the method should fragment these into.  
    """
    # fragmentSize == 30
    frags = []
    dataRaw = scapy.raw(packet)
    moreFrag = b'\x01'
    endFrag =b'\x00'
    # hexTotalPacketLength = scapy.bytes_hex(packet)[4:8] # We know that an IP header has the total length of the packet in its 16th-31th bit. Get this in a readable format.
    
    #prefix = int.to_bytes(1, "big") # unsure about the big or little endian convert into 1 byte
    print("Begin fragment:{} ".format(packet))
    
    if len(dataRaw) <= fragmentSize+1:
        #size less than 31 bytes add 1byte geader to package
        print("Do not need to fragment")
        frags.append(endFrag+dataRaw)
    else: 
        numSteps = math.ceil(len(dataRaw)/fragmentSize)
        for i in range(numSteps):
            temp = moreFrag+dataRaw[0:fragmentSize]
            print("In fragmentation loop {}, the fragment is: {}".format(i,temp))
            frags.append(temp)
            dataRaw = dataRaw[fragmentSize:]
            numSteps-=1
            if(numSteps ==1):break       
        last = endFrag +dataRaw
        print("The last fragment length: {}".format(len(dataRaw)))
        frags.append(last)
        print("End of frag")
    return frags

def defragment(byteList):
    """ Defragments and returns a packet. The input parameter has to be a fragmented IP packet as a list. (for now)
    """
    header = byteList[0:1]
    if(header == b'\x01'):
        return True, byteList[1:]
    return False, byteList[1:]

def readFromNRF(nrf: RF24):
    size = nrf.getDynamicPayloadSize()
    temp = nrf.read(size)
    print("Read from NRF {}".format(temp))
    return bytes(temp)


def readFromNRF(nrf: RF24):
    size = nrf.getDynamicPayloadSize()
    temp = nrf.read(size)
    print("Read from NRF {}".format(temp))
    return bytes(temp)

#processargs: kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'queue': incoming, 'channel': args.txchannel, 'size':args.size})
def tx(nrf: RF24, address, channel, size):
    nrf.openWritingPipe(address)
    nrf.stopListening()
    print("Init TX on channel {}".format(channel))
    while True:
            packet = outgoing.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.
            #if scapy.packet.haslayer(IP)==1
            print("TX: {}".format(packet)) #TODO: DELETE. 
            fragments = fragment(packet, size-2) #prefix 1 byte to fragment 
            for idx, x in enumerate(fragments):  
                print("fragment index: {},  ".format(idx),x)
                nrf.write(x)
     

#processargs: kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.openReadingPipe(1, address)
    nrf.startListening()
    print("Init RX on channel {} with details:".format(channel))
    defragmentedPacket = b""

    while True:
        hasData, whatPipe = nrf.available_pipe()
        moreFrag = False
        if hasData:
            size = nrf.getDynamicPayloadSize()
            tmp = nrf.read(size)
            packet = bytes(tmp)
            print("Fragment received on RX: {}".format(packet))
            moreFrag, fragment = defragment(packet)
            if(moreFrag == True):
                print("Waiting for more fragments")
                defragmentedPacket +=fragment
            else:
                defragmentedPacket +=fragment
                tun.write(defragmentedPacket)
                defragmentedPacket = b"" #clear memory



def fullUpLink(isBase:bool,channel:int):
    print("Enter full-uplink mode")
    rx_process.join()
    rx_process = Process(target=tx, kwargs={'nrf':rx_nrf, 'address':bytes(src, 'utf-8'), 'tun': tun, 'channel': channel})
    rx_process.start()

def fullDuplex(isBase:bool,channel:int):
    print("Enter full-duplex mode")

def fullDownLink(isBase:bool,channel:int):
    print("Enter full-downlink mode")  


# Troubleshooting tool. Since I am getting radio hardware not found, it is useful to break the program into smaller chunks. 
def setupSingle(nrf):
    nrf.setDataRate(RF24_2MBPS) 
    nrf.setAutoAck(True)
    nrf.payloadSize = 32
    nrf.setCRCLength(RF24_CRC_8)
    nrf.setPALevel(RF24_PA_LOW)



def setupNRFModules(rx: RF24, tx: RF24):
    
    rx.setDataRate(RF24_2MBPS) 
    rx.setDataRate(RF24_2MBPS) 
    tx.setDataRate(RF24_2MBPS)

    rx.setAutoAck(True)
    tx.setAutoAck(True)

    rx.setAutoAck(True)
    tx.setAutoAck(True)

    rx.payloadSize = 32
    tx.payloadSize = 32

    rx.setCRCLength(RF24_CRC_8)
    tx.setCRCLength(RF24_CRC_8)

    #Low power because we are using them next to one another! 

    rx.setPALevel(RF24_PA_LOW) 
    tx.setPALevel(RF24_PA_LOW)

    

    #Low power because we are using them next to one another! 

    rx.setPALevel(RF24_PA_LOW) 
    tx.setPALevel(RF24_PA_LOW)

    
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
    print("TUN interface online, with values \n Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )
    return tun




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NRF24L01+')
    parser.add_argument('--isBase', dest='base', type= bool, default=True, help='If this is a base-station, set it to True.') 
    parser.add_argument('--src', dest='src', type=str, default='1Node', help='NRF24L01+\'s source address')
    parser.add_argument('--dst', dest='dst', type=str, default='2Node', help='NRF24L01+\'s destination address')
    parser.add_argument('--src', dest='src', type=str, default='1Node', help='NRF24L01+\'s source address')
    parser.add_argument('--dst', dest='dst', type=str, default='2Node', help='NRF24L01+\'s destination address')
    parser.add_argument('--count', dest='cnt', type=int, default=10, help='Number of transmissions')
    parser.add_argument('--size', dest='size', type=int, default=32, help='Packet size') 
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=76, help='Tx channel', choices=range(0,125)) 
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=81, help='Rx channel', choices=range(0,125))
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=81, help='Rx channel', choices=range(0,125))

    args = parser.parse_args()

    #With a data rate of 2 Mbps, we need to at least tell the user that the channels should be at least 2Mhz from each other to ensure no cross talk. 
    if abs(args.txchannel - args.rxchannel) < 2:
        print("Do note that having tx and rx channels this close to each other can introduce cross-talk.")


    # initialize the nRF24L01 on the spi bus object
    rx_nrf = RF24(17, 0)
    rx_nrf.begin()
    tx_nrf = RF24(27, 10)
    tx_nrf.begin()
    setupNRFModules(rx_nrf, tx_nrf)
    txchannel = args.txchannel if args.base else args.rxchannel
    rxchannel = args.rxchannel if args.base else args.txchannel
    src = args.src if args.base else args.dst
    dst = args.dst if args.base else args.src
    tun = setupIP(args.base)
   
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(src, 'utf-8'), 'tun': tun, 'channel': rxchannel})
    rx_process.start()
    time.sleep(0.01)

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(dst, 'utf-8'), 'channel': txchannel, 'size':args.size})
    tx_process.start()
    
    try:    
        while True:
            packet = tun.read(tun.mtu)
            outgoing.put(packet)
            #print("In main thread, size of the queue is: {}".format(outgoing.qsize()))


    except KeyboardInterrupt:
        #Can this interrupt a while true loop? Let's try.
        exit

    tx_process.join()
    rx_process.join()
    tun.down()
    print("Threads ended successfully, please stand by.")