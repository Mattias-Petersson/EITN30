import math
from multiprocessing import Process, Queue
import time
from pytun import TunTapDevice
import scapy.all as scape
import argparse
from RF24 import RF24, RF24_PA_LOW, RF24_2MBPS,RF24_CRC_8

global outgoing; outgoing = Queue() 

def fragment(packet, fragmentSize):

    """ Fragments and returns a list of bytes. This is done by finding the number of fragments we want, and then splitting the bytes-like object into chunks of appropriate size. 
    The input parameter is an IP packet (or any bytes-like object) and the size the method should fragment these into.  
    """
    frags = []
    dataRaw = bytes(packet)
    if len(dataRaw) <= fragmentSize:
        frags.append(dataRaw)
    else: 
        numSteps = math.ceil(len(dataRaw)/fragmentSize)
        for _ in range(numSteps):
            frags.append(dataRaw[0:32])
            dataRaw = dataRaw[32:]

    return frags

def defragment(data):
    """ Defragments and returns a packet. The input parameter has to be a fragmented IP packet as a list. (for now)
    """
    # First, find out how big the incoming packet is. 
    sizeOfPacket = int.from_bytes(data[2:4], "big")
    if(sizeOfPacket < 32):
        print("Small packet")
        return data
    else:
        #Do other stuff
        print("No causing errors here today.")
    #data = b""
    #return data
 
def tx(nrf: RF24, address, channel, size):
    nrf.openWritingPipe(address)
    nrf.stopListening()
    print("Init TX on channel {}".format(channel))
    nrf.printDetails()
    while True:
            print("Size of the queue? {}".format(outgoing.qsize()))
            packet = outgoing.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.
            #print("TX: {}".format(packet)) #TODO: DELETE. 
            fragments = fragment(packet, size)
            
            for i in fragments:
                print("Fragment in TX: {}".format(i))
                nrf.write(i)
        
            
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.openReadingPipe(1, address)
    nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    # For packets longer than 32 bytes, the following variables keep track of how big they are and when the packet is considered complete.  
    incoming = b''
    finished = True
    sizeRemaining = 0
    start = time.monotonic()
    while True:
        hasData, whatPipe = nrf.available_pipe()
        if hasData and finished:
            packet, size = readFromNRF(nrf)
            sizeRemaining = int.from_bytes(packet[2:4], "big")
            print("Fragment received on RX: {}, packet-size: {}".format(scape.hex_bytes(packet), sizeRemaining))
            if sizeRemaining > size:
                incoming += packet
                sizeRemaining -= size
                start = time.monotonic()
                print("Big packet, size expected: {}, size remaining: ".format(size, sizeRemaining))
                finished = False
            else:
                tun.write(packet)
        while(time.monotonic() - start) < 1000 or not sizeRemaining == 0: # Give a packet a total of one second to arrive, otherwise consider it discarded.
            if hasData:
                packet, size = readFromNRF(nrf)
                incoming += packet
                sizeRemaining -= size
                print("The incoming packet is now {} bytes big. The total length remaining is: {}".format(len(incoming), sizeRemaining))
        if sizeRemaining == 0:
            tun.write(incoming)
        # Discards the incoming packet by resetting the variables.
        incoming = b''
        sizeRemaining = 0
        finished = True
        

def readFromNRF(nrf: RF24):
    size = nrf.getDynamicPayloadSize()
    tmp = nrf.read(size)
    return bytes(tmp), size
            
           #packet = incoming.append(nrf.read(size))
            #tun.write(test)
            #print(incoming)
#        finished = defrag(incoming)
#        tun.write(finished)

def setupNRFModules(rx: RF24, tx: RF24, args):
    
    rx.setDataRate(RF24_2MBPS) 
    tx.setDataRate(RF24_2MBPS)

    rx.setAutoAck(True)
    tx.setAutoAck(True)

    rx.payloadSize = 32
    tx.payloadSize = 32

    rx.setCRCLength(RF24_CRC_8)
    tx.setCRCLength(RF24_CRC_8)

    #Low power because we are using them next to one another! 

    rx.setPALevel(RF24_PA_LOW) 
    tx.setPALevel(RF24_PA_LOW)
    # Setting up the NRF modules in this method as well. 
"""
    if(args.base):
        return args.txchannel, args.rxchannel, args.src, args.dst
    
    return args.rxchannel, args.txchannel, args.dst, args.src
"""
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




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NRF24L01+. Please note that you should use the same src/dst for the base and the mobile unit, put the isBase to False and let the program handle the RX/TX pair.')
    
    parser.add_argument('--base', dest='base', default=True, action=argparse.BooleanOptionalAction)
    #parser.add_argument('--isBase', dest='base', type= bool, default=True, help='If this is a base-station, set it to True.') 
    parser.add_argument('--src', dest='src', type=str, default='1Node', help='NRF24L01+\'s source address (Base)')
    parser.add_argument('--dst', dest='dst', type=str, default='2Node', help='NRF24L01+\'s destination address (Base)')
    parser.add_argument('--size', dest='size', type=int, default=32, help='Packet size') 
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=76, help='Tx channel', choices=range(0,125)) 
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

    txchannel = args.txchannel if args.base else args.rxchannel
    rxchannel = args.rxchannel if args.base else args.txchannel
    src = args.src if args.base else args.dst
    dst = args.dst if args.base else args.src
    tun = setupIP(args.base)
   
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(src, 'utf-8'), 'tun': tun, 'channel': rx})
    rx_process.start()
    time.sleep(0.01)

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(dst, 'utf-8'), 'channel': tx, 'size':args.size})
    tx_process.start()

    ICMPPacket = scape.IP(dst="8.8.8.8")/scape.ICMP() # Merely for testing. Remove later. 
    
    try:    
        while True:
            packet = tun.read(tun.mtu)
            outgoing.put(packet)
            #print("In main thread, size of the queue is: {}".format(outgoing.qsize()))


    except KeyboardInterrupt:
        print("Main thread no longer listening on the TUN interface. ")

    tx_process.join()
    rx_process.join()
    # Setting the radios to stop listening seems to be best practice. 
    rx_nrf.stopListening()  
    tx_nrf.stopListening()

    tun.down()
    print("Threads ended, radios stopped listening, TUN interface down.")