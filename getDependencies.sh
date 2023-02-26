#!/bin/bash  

#python3 -m pip install circuitpython-nrf24l01
#python3 -m pip install python-pytun
#pip3 install circuitpython-nrf24l01
echo "Installing Pytun and Scapy for IP-tunnels and packet-creation. "
pip3 install python-pytun
pip3 install --pre scapy[basic]

echo "Installing RF24 module."
git clone https://github.com/tmrh20/RF24.git RF24
cd RF24
./configure --driver=SPIDEV # install.sh sets this if you choose to use SpiDev, this way we can enforce the policy to use SpiDev. Less customizability but more predictable. 
cd pyRF24
python3 setup.py build
python3 setup.py install
cd ../../../ # Go back to the main-folder to not confuse the user. 

echo "Installation complete. :)"