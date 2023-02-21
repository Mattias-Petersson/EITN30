import math
from multiprocessing import Process, Queue
import sys
import time
import struct
import board
import digitalio as dio
import busio
from pytun import TunTapDevice
import scapy.all as scape
import argparse
from circuitpython_nrf24l01.rf24 import RF24
import spidev

SPI_BUS0 = spidev.SpiDev()
SPI_BUS1 = spidev.SpiDev()
global outgoing; outgoing = Queue()
SPI0 = {
    'MOSI':10,#dio.DigitalInOut(board.D10),
    'MISO':9,#dio.DigitalInOut(board.D9),
    'clock':11,#dio.DigitalInOut(board.D11),
    'ce_pin':dio.DigitalInOut(board.D17),
    'csn':dio.DigitalInOut(board.D8),
    }
SPI1 = {
    'MOSI':20,#dio.DigitalInOut(board.D10),
    'MISO':19,#dio.DigitalInOut(board.D9),
    'clock':21,#dio.DigitalInOut(board.D11),
    'ce_pin':dio.DigitalInOut(board.D27),
    'csn':dio.DigitalInOut(board.D18), #Not allowed to be on the same PIN as SPI0! No other configuration of this works. 
    }

def fragment(packet, fragmentSize):

    """ Fragments and returns a list of bytes. This is done by finding the number of fragments we want, and then splitting the bytes-like object into chunks of appropriate size. 
    The input parameter is an IP packet (or any bytes-like object) and the size the method should fragment these into.  
    """
    frags = []
    dataRaw = scape.raw(packet)
    numSteps = math.ceil(len(dataRaw)/fragmentSize)
    print(numSteps)
    for _ in range(numSteps):
        frags.append(dataRaw[0:32])
        dataRaw = dataRaw[32:]

    return frags

def defragment(dataList):
    """ Defragments and returns a packet. The input parameter has to be a fragmented IP packet as a list. (for now)
    """
    data = b""
    return data
 
#processargs: kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'queue': incoming, 'channel': args.txchannel, 'size':args.size})
def tx(nrf: RF24, address, channel, size):
    nrf.open_tx_pipe(address)
    nrf.listen = False
    nrf.channel = channel
    print("Init TX on channel {}".format(channel))

    while True:
            print("Size of the queue? {}".format(outgoing.qsize()))
            packet = outgoing.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.
            print("This should not.")
            print("TX: {}".format(packet)) #TODO: DELETE. 
            fragments = fragment(packet, size)
            for _ in fragments:
                nrf.send(fragments)
        
            

#processargs: kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.open_rx_pipe(1, address) # Use pipe 1.
    nrf.listen = True
    nrf.channel = channel 
    print("Init RX on channel {}".format(channel))
    incoming = []
    while True:
        if nrf.available():
            size = nrf.any()
            print(size)
            test = nrf.read(size)
            print(test)
            print(type(test))
            packet = bytes(test)
            print("Before null check: {}".format(test)) #TODO, DELETE THIS.
            if packet is not None:
                print("After null check: {}".format(test)) #TODO: Delete this.
                tun.write(packet)
            #packet = incoming.append(nrf.read(size))
            #tun.write(test)
            #print(incoming)
#        finished = defrag(incoming)
#        tun.write(finished)

# Troubleshooting tool. Since I am getting radio hardware not found, it is useful to break the program into smaller chunks. 
def setupSingle(nrf):
    nrf.data_rate = 2
    nrf.ack = True
    nrf.payload_length = 32
    nrf.crc = 1

def setupNRFModules(rx, tx):
    
    
    # From the API, 1 sets freq to 1Mbps, 2 sets freq to 2Mbps, 250 to 250kbps.
    rx.data_rate = 2 
    tx.data_rate = 2
    
    #TODO: Look into what channels are the least populated. 


   
    rx.ack = True
    tx.ack = True

    rx.payload_length = 32
    tx.payload_length = 32

    # From the API, 1 enables CRC using 1 byte (weak), 2 enables CRC using 2 bytes (stronger), 0 disables. 
    rx.crc = 1
    tx.crc = 1
    
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




address = [b"1Node", b"2Node"]
def main():
    parser = argparse.ArgumentParser(description='NRF24L01+')
    parser.add_argument('--isBase', dest='base', type= bool, default=True, help='If this is a base-station, set it to True.') 
    parser.add_argument('--src', dest='src', type=str, default='Node1', help='NRF24L01+\'s source address')
    parser.add_argument('--dst', dest='dst', type=str, default='Node2', help='NRF24L01+\'s destination address')
    parser.add_argument('--count', dest='cnt', type=int, default=10, help='Number of transmissions')
    parser.add_argument('--size', dest='size', type=int, default=32, help='Packet size') 
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=76, help='Tx channel', choices=range(0,125)) 
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=81, help='Rx channel', choices=range(0,125))

    args = parser.parse_args()

    #With a data rate of 2 Mbps, we need to at least tell the user that the channels should be at least 2Mhz from each other to ensure no cross talk. 
    if abs(args.txchannel - args.rxchannel) < 2:
        print("Do note that having tx and rx channels this close to each other can introduce cross-talk.")


    # initialize the nRF24L01 on the spi bus object
  
    #rx_nrf = RF24(SPI_BUS0, SPI0['csn'], SPI0['ce_pin'])
    #tx_nrf = RF24(SPI_BUS1, SPI1['csn'], SPI1['ce_pin'])
    #setupNRFModules(rx_nrf, tx_nrf)
    
    nrf = RF24(SPI_BUS1, SPI0['csn'], SPI1['ce_pin'])
    #These might not be needed, but they seem useful considering their get() blocks until data is available.
    setupSingle(nrf)
    tun = setupIP(args.base)
    #nrf_process = Process(target=rx, kwargs={'nrf':nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
    nrf_process = Process(target=tx, kwargs={'nrf':nrf, 'address':bytes(args.dst, 'utf-8'), 'channel': args.txchannel, 'size':args.size})
    nrf_process.start()
    
    
    



    """
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
    rx_process.start()
    time.sleep(1)

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'queue': outgoing, 'channel': args.txchannel, 'size':args.size})
    tx_process.start()

    ICMPPacket = scape.IP(dst="8.8.8.8")/scape.ICMP() # Merely for testing. Remove later. 
    """
    try:    
        while True:
            packet = tun.read(tun.mtu)
            print("From TUN: {}".format(packet))
            outgoing.put(packet)
            print("In main thread, size of the queue is: {}".format(outgoing.qsize()))


    except KeyboardInterrupt:
        #Can this interrupt a while true loop? Let's try.
        print("Hey, do we get here?")
        exit


    print("Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )

    """
    tx_process.join()
    rx_process.join()
    """
    nrf_process.join()
    tun.down()
    print("Threads ended successfully, please stand by.")