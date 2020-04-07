# nornir_dot1x_applier

This script uses the Nornir framework to apply dot1x config to Catalyst switches.

Cisco IBNS version 1 or 2 templates will be applied based on switch model. 
Catalyst 3750 series switches will receive IBNS version 1 and all other 
switch models will receive IBNS version 2. 

Additional required variables from Source of Truth (SimpleInventory):

ise_key:            ISE RADIUS key

ise_vip_a_name:     ISE cluster A hostname

ise_vip_a_ip:       ISE cluster A VIP ip address

ise_vip_a_psn1:     ISE cluster A PSN1 ip address

ise_vip_a_psn2:     ISE cluster A PSN2 ip address

ise_vip_b_name:     ISE cluster B hostname

ise_vip_b_ip:       ISE cluster B VIP ip address

ise_vip_b_psn1:     ISE cluster B PSN1 ip address

ise_vip_b_psn2:     ISE cluster B PSN2 ip address

region:             east or west ISE region

vlans:              list of vlans dot1x will be applied to

uplinks:            list of ports that will recieve dot1x uplink config

excluded_intf:      list of ports that will be excluded from dot1x 
