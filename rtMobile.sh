#!/bin/bash  

ip route add default via 20.0.0.1 dev longge

# Save the config. Log back to the current user.
sudo -i <<'EOF'
iptables-save > /../etc/iptables/rules.v4
EOF
logout