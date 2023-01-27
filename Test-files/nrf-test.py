from circuitpython_nrf24l01.rf24 import RF24
import board
import busio
import digitalio as dio
import argparse

SPI0 = {
    'MOSI':dio.DigitalInOut(board.D10),
    'MISO':dio.DigitalInOut(board.D9),
    'clock':dio.DigitalInOut(board.D11),
    'ce_pin':dio.DigitalInOut(board.D17),
    'csn':dio.DigitalInOut(board.D8),
    }
SPI1 = {
    'MOSI':DigitalInOut(board.D10),
    'MISO':dio.DigitalInOut(board.D9),
    'clock':dio.DigitalInOut(board.D11),
    'ce_pin':dio.DigitalInOut(board.D27),
    'csn':dio.DigitalInOut(board.D18),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NRF24L01+ test')
    parser.add_argument('--src', dest='src', type=str, default='me', help='NRF24L01+\'s source address')
    parser.add_argument('--dst', dest='dst', type=str, default='me', help='NRF24L01+\'s destination address')
    parser.add_argument('--count', dest='cnt', type=int, default=10, help='Number of transmissions')
    parser.add_argument('--size', dest='size', type=int, default=32, help='Packet size')
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=76, help='Tx channel', choices=range(0,125))
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=76, help='Rx channel', choices=range(0,125))

    args = parser.parse_args()

    SPI0['spi'] = busio.SPI(**{x: SPI0[x] for x in ['clock', 'MOSI', 'MISO']})
    SPI1['spi'] = busio.SPI(**{x: SPI1[x] for x in ['clock', 'MOSI', 'MISO']})

    # initialize the nRF24L01 on the spi bus object
    rx_nrf = RF24(**{x: SPI0[x] for x in ['spi', 'csn', 'ce_pin']})
    tx_nrf = RF24(**{x: SPI1[x] for x in ['spi', 'csn', 'ce_pin']})

    print('nRF24L01+ found on SPI0: {}, SPI1: {}'.format(rx_nrf, tx_nrf))