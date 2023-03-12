# EITN30
A project done for the course "EITN30 - Internet inside", taken winter 2023 at LTH. The project description was to implement "longge". The project involved setting up two Raspberry Pis equipped with two NRF24L01 modules each, one as a base station to route IP traffic onto the internet, and one as a mobile unit that utilizes this base-station. Our group also had the personal goal to maximize throughput.  

___

To install:
clone down the repo and install dependencies:  
```
git clone https://github.com/Mattias-Petersson/EITN30
chmod + x getDependencies.sh
sudo ./getDependencies.sh
```
___


Before running, one might need to change the CE-pins and the bus- and device number in the init of rx_nrf and tx_nrf in the program.  
To run, simply type `sudo python3 longge.py` on the unit acting as the base-station, and `sudo python3 longge.py --no-base` on the mobile unit. The program allows for arguments to set the channels the Pis communicate on, the max bit-size of the NRF, and the source and destination address of the NRF addresses. These arguments are all optional and the program should run fine as-is. To verify this works, type `ifconfig` in another terminal to ensure that the TUN interface is created with the proper IP address, or `ping -I longge 8.8.8.8` to show that pinging across the internet works through the program.

The program supports the units enabling double TX or RX, making it faster to send data, important to note that it is not possible to send TCP messages, as the recipient will not be able to send back ACKs for the duration of this mode. To enable this, send a IP packet of length <70 ending in the bytes *b'\xff\xff\xff\x**XX**'* where **XX** is the hexadecimal representation of the number of minutes you want to activate this mode for (max 1 byte, 255 minutes). A simple script to do so is included in the repository. To do so, run the `testTurboTX()` method in Test-files/testPings.py. The argument for the function is an integer for the number of minutes. The sender enables double TX, and the receiver enables double RX for the specified number of minutes, and then revert back to TX/RX pairs. 

