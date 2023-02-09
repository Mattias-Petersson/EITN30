#!/bin/bash  

# For a wired connection on eth0, uncomment the following 3 lines. Otherwise it tries to route via the wireless interface. 
#iptables -t nat -A POSTROUTING -o longge -j MASQUERADE
#iptables -A FORWARD -i eth0 -o longge -m state --state RELATED,ESTABLISHED -j ACCEPT
#iptables -A FORWARD -i longge -o eth0 -j ACCEPT

iptables -t nat -A POSTROUTING -o longge -j MASQUERADE
iptables -A FORWARD -i wlan0 -o longge -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i longge -o wlan0 -j ACCEPT
