from multiprocessing import Process
import sys
import time
import struct
import board
import digitalio as dio
import busio
from pytun import TunTapDevice
import scapy.all as scape
import queue
import argparse
from RF24 import RF24

txRadio = RF24(17, 0)
rxRadio = RF24(27, 60)

# addresses needs to be in a buffer protocol object (bytearray)
address = [b"1Node", b"2Node"]


def fragment(data, fragmentSize):
    """ Fragments and returns a list of any IP packet. The input parameter has to be an IP packet, as this is done via Scapy. (for now) 
    """
    frags = scape.fragment(data, fragsize=fragmentSize)
    return frags

def defrag(dataList):
    """ Defragments and returns a packet. The input parameter has to be a fragmented IP packet as a list. (for now)
    """
    data = scape.defragment(dataList)
    return data
 
#processargs: kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'queue': incoming, 'channel': args.txchannel, 'size':args.size})
def tx(nrf, address, queue: queue, channel, size):
    nrf.stopListening()



    print("Init TX")
    while True:
        packet = queue.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.

        frags = fragment(packet, size)
        for f in frags:
            nrf.write(f)

        print("Do we get here? and if so, how often do we get here?")

#processargs: kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
def rx(nrf, address, tun: TunTapDevice, channel):
    incoming = []
    nrf.startListening()
    
    print("Init RX")
    while True:
        if nrf.available_pipe():
            size = nrf.getDynamicPayloadSize()
            incoming.append(nrf.read(size))

            print(incoming)
        finished = defrag(incoming)
        tun.write(finished)


def setupNRFModules(tx, rx, args):
    tx.begin()
    rx.begin()

    tx.setChannel(args.txchannel)
    rx.setChannel(args.rxchannel)

    tx.setDataRate(1)
    rx.setDataRate(1)

    tx.setCRCLength(1)
    rx.setCRCLength(1)

    tx.openWritingPipe(address[0])
    rx.openWritingPipe(1, address[1])


    
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
    return tun

def main():
    parser = argparse.ArgumentParser(description='NRF24L01+')
    parser.add_argument('--isBase', dest='base', type= bool, default=True, help='If this is a base-station, set it to True.') 
    parser.add_argument('--src', dest='src', type=str, default='me', help='NRF24L01+\'s source address')
    parser.add_argument('--dst', dest='dst', type=str, default='me', help='NRF24L01+\'s destination address')
    parser.add_argument('--count', dest='cnt', type=int, default=10, help='Number of transmissions')
    parser.add_argument('--size', dest='size', type=int, default=32, help='Packet size') 
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=76, help='Tx channel', choices=range(0,125)) 
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=81, help='Rx channel', choices=range(0,125))

    args = parser.parse_args()

    #With a data rate of 2 Mbps, we need to at least tell the user that the channels should be at least 2Mhz from each other to ensure no cross talk. 
    if abs(args.txchannel) - abs(args.rxchannel < 2):
        print("Do note that having tx and rx channels this close to each other can introduce cross-talk.")


    setupNRFModules(txRadio, rxRadio, args)

    #These might not be needed, but they seem useful considering their get() blocks until data is available.
    outgoing = queue.Queue()

    tun = setupIP(args.base)



    rx_process = Process(target=rx, kwargs={'nrf':rxRadio, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
    rx_process.start()
    time.sleep(1)

    tx_process = Process(target=tx, kwargs={'nrf':txRadio, 'address':bytes(args.dst, 'utf-8'), 'queue': outgoing, 'channel': args.txchannel, 'size':args.size})
    tx_process.start()

    ICMPPacket = scape.IP(dst="8.8.8.8")/scape.ICMP() # Merely for testing. Remove later. 

    try:
        while True:
            packet = tun.read(tun.mtu)
            outgoing.put(packet)


    except KeyboardInterrupt:
        #Can this interrupt a while true loop? Let's try.
        exit


    print("Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )


    tx_process.join()
    rx_process.join()
    tun.down()
    print("Threads ended successfully, please stand by.")