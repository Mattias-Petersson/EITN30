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
from RF24 import RF24, RF24_PA_LOW, RF24_PA_MIN, RF24_2MBPS, RF24_CRC_8
import spidev

global outgoing; outgoing = Queue()
"""
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
    'MOSI':20,#dio.DigitalInOut(board.D10),
    'MISO':19,#dio.DigitalInOut(board.D9),
    'clock':21,#dio.DigitalInOut(board.D11),
    'ce_pin':dio.DigitalInOut(board.D27),
    'csn':dio.DigitalInOut(board.D18), #Not allowed to be on the same PIN as SPI0! No other configuration of this works. 
    }
"""
 
#processargs: kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'queue': incoming, 'channel': args.txchannel, 'size':args.size})
def tx(nrf: RF24, address, channel, size):
    nrf.openWritingPipe(address)
    nrf.setAutoAck(false)
    nrf.stopListening()
    nrf.payloadSize = 32
    print("Init TX on channel {}".format(channel))
    nrf.printDetails()
    count = 0
    delayList =[]
    while count<2000:
        payload = bytearray(32)    
        start_timer = time.monotonic_ns()  # start timer
        payload[0:3] =start_timer
        result = nrf.write(payload)
        end_timer = time.monotonic_ns()
        delayList.append(end_timer-start_timer) 
        count+=1
        
            

#processargs: kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.openReadingPipe(1, address)
    nrf.setAutoAck(false)
    rx_nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    incoming = 0
    totalTime = 0
    count = 0
    while count<2000:
        hasData, whatPipe = nrf.available_pipe()
        start_timer = time.monotonic_ns()
        if hasData:
            start_timer = time.monotonic_ns()
            #size = nrf.getDynamicPayLoadSize()
            size = nrf.payloadSize #32
            incoming+=size
            test = nrf.read(size)
            packet = bytes(test)
        end_timer = time.monotonic_ns()
        totalTime = end_timer-start_timer
    print("Time elapse in ms : {} ".format(totalTime))
    print("Incoming bytes: {} ".format(incoming))
    print("Throughput: "+ incoming/totalTime*1000)

# Troubleshooting tool. Since I am getting radio hardware not found, it is useful to break the program into smaller chunks. 
def setupSingle(nrf):
    nrf.setDataRate(RF24_2MBPS) #(1) represents 2 Mbps
    nrf.setAutoAck(False)# for all pipe or nrf.setAutoAck(0,True)
    nrf.payloadSize = 32 
    nrf.setCRCLength(RF24_CRC_8) #RF24_CRC_8 or RF24_CRC_16
    nrf.setPALevel(RF24_PA_LOW )

def setupNRFModules(rx, tx):
    
    
    # From the API, 1 sets freq to 1Mbps, 2 sets freq to 2Mbps, 250 to 250kbps.
    rx.setDataRate(RF24_2MBPS)  
    tx.setDataRate(RF24_2MBPS)
    
    #TODO: Look into what channels are the least populated. 


   
    rx.setAutoAck(True) # enable autoAck for pipeline 0 This number should be in range [0, 5]
    tx.setAutoAck(True) 

    rx.payloadSize = 32
    tx.payloadSize = 32

    # From the API, 1 enables CRC using 1 byte (weak), 2 enables CRC using 2 bytes (stronger), 0 disables. 
    rx.setCRCLength(RF24_CRC_8)
    tx.setCRCLength(RF24_CRC_8)
    
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
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=100, help='Tx channel', choices=range(0,125)) #2500Mhz and 2490Mhz
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=90, help='Rx channel', choices=range(0,125))##WiFi and blutooth channel only up to 80 so channel after 80 could be used

    args = parser.parse_args()

    #With a data rate of 2 Mbps, we need to at least tell the user that the channels should be at least 2Mhz from each other to ensure no cross talk. 
    if abs(args.txchannel - args.rxchannel) < 2:
        print("Do note that having tx and rx channels this close to each other can introduce cross-talk.")


    # initialize the nRF24L01 on the spi bus object
  
    rx_nrf = RF24(17, 0)
    rx_nrf.begin() # startListening() 
    
    tx_nrf = RF24(27, 10)
    tx_nrf.begin() # stopListening()
    
    #setupNRFModules(rx_nrf, tx_nrf)
    
    #nrf = RF24(SPI_BUS1, SPI0['csn'], SPI1['ce_pin'])
    #These might not be needed, but they seem useful considering their get() blocks until data is available.
    #setupSingle(nrf)
    tun = setupIP(args.base)
    #nrf_process = Process(target=rx, kwargs={'nrf':nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
    #nrf_process = Process(target=tx, kwargs={'nrf':nrf, 'address':bytes(args.dst, 'utf-8'), 'channel': args.txchannel, 'size':args.size})
    #nrf_process.start()
    
    
    
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
    rx_process.start()
    

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'channel': args.txchannel, 'size':args.size})
    tx_process.start()

    ICMPPacket = scape.IP(dst="8.8.8.8")/scape.ICMP() # Merely for testing. Remove later. 
    
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

    
    tx_process.join()
    rx_process.join()
    
    #nrf_process.join()
    tun.down()
    print("Threads ended successfully, please stand by.")