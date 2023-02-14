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
from circuitpython_nrf24l01.rf24 import RF24
import spidev

SPI_BUS0 = spidev.SpiDev()
SPI_BUS1 = spidev.SpiDev()
SPI0 = {
    'MOSI':10,#dio.DigitalInOut(board.D10),
    'MISO':9,#dio.DigitalInOut(board.D9),
    'clock':11,#dio.DigitalInOut(board.D11),
    'ce_pin':dio.DigitalInOut(board.D17),
    'csn':dio.DigitalInOut(board.D8),
    }
SPI1 = {    
    'MOSI':dio.DigitalInOut(board.D20), #20, D10
    'MISO':dio.DigitalInOut(board.D19), #19, D9
    'clock':dio.DigitalInOut(board.D21), #21, D11
    'ce_pin':dio.DigitalInOut(board.D27),
    'csn':dio.DigitalInOut(board.D18),
    }

def fragment(data, fragmentSize):
    """ Fragments and returns a list of any IP packet. The input parameter has to be an IP packet, as this is done via Scapy. (for now) 
    """
    frags = scape.fragment(data, fragsize=fragmentSize)
    return frags

def defrag(dataList):
    """ Defragments and returns a packet. The input parameter has to be a fragmented IP packet as a list. (for now)
    """
    data = b""

    for d in dataList:
        data += scape.raw(d)
    #data = scape.defrag(dataList)
    
    return data
 
#processargs: kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'queue': incoming, 'channel': args.txchannel, 'size':args.size})
def tx(nrf: RF24, address, queue: queue, channel, size):
    nrf.open_tx_pipe(address)
    nrf.listen = False
    nrf.channel = channel


    print("Init TX")
    while True:
        packet = queue.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.

        frags = fragment(packet, size)
        for f in frags:
            nrf.send(f)

        print("Do we get here? and if so, how often do we get here?")

#processargs: kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
def rx(nrf, address, tun: TunTapDevice, channel):
    incoming = []
    nrf.open_rx_pipe(1, address) # Use pipe 1.
    nrf.listen = True
    nrf.channel = channel
    
    print("Init RX")
    while True:
        if nrf.available():
            size = nrf.any()
            packet = incoming.append(nrf.read(size))
            tun.write(packet)
            print(incoming)
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
    # Look into what channels are the least populated. 
   # rx.channel = ??
   # tx.channel = ??
   
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


    # initialize the nRF24L01 on the spi bus object
  
    #rx_nrf = RF24(SPI0['spi'], SPI0['csn'], SPI0['ce_pin'])
    #tx_nrf = RF24(SPI1['spi'], SPI1['csn'], SPI1['ce_pin'])
    #setupNRFModules(rx_nrf, tx_nrf)
    nrf = RF24(SPI_BUS0, SPI0['csn'], SPI0['ce_pin'])

    setupSingle(nrf)
    #These might not be needed, but they seem useful considering their get() blocks until data is available.
    outgoing = queue.Queue()

    tun = setupIP(args.base)

    nrf_process = Process(target=rx, kwargs={'nrf':nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
    nrf_process.start()
    #rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
    #rx_process.start()
    time.sleep(1)

    #tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'queue': outgoing, 'channel': args.txchannel, 'size':args.size})
    #tx_process.start()

    ICMPPacket = scape.IP(dst="8.8.8.8")/scape.ICMP() # Merely for testing. Remove later. 

    try:
        while True:
            packet = tun.read(tun.mtu)
            outgoing.put(packet)


    except KeyboardInterrupt:
        #Can this interrupt a while true loop? Let's try.
        exit


    print("Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )


    #tx_process.join()
    #rx_process.join()
    tun.down()
    print("Threads ended successfully, please stand by.")