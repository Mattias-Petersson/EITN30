#!/bin/bash  

ip route add default via 20.0.0.1 dev longge

# Save the config. Log back to the current user.
sudo -i
apt-get install iptables-persistent
iptables-save > /../etc/iptables/rules.v4
logout