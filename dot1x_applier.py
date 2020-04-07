#!/usr/local/bin/python3
'''

This script uses the Nornir framework to apply dot1x config to Catalyst switches.

Cisco IBNS version 1 or 2 templates will be applied based on switch model. 
Catalyst 3750 series switches will receive IBNS version 1 and all other 
switch models will receive IBNS version 2. 

Additional variables required from SimpleInventory:

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

'''

from getpass import getpass
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_command
from nornir.plugins.tasks.networking import netmiko_send_config
from nornir.plugins.tasks import text


# print formatting function
def c_print(printme):
    # Print centered text with newline before and after
    print(f"\n" + printme.center(80, ' ') + "\n")


# set device credentials
def nornir_set_creds(norn, username=None, password=None):
    # print banner
    print()
    print('~'*80)
    c_print('Check inventory for device credentials')

    for host_obj in norn.inventory.hosts.values():
        
        if not host_obj.username:
            c_print('Please enter device credentials:')
            username = input("Username: ")
            host_obj.username = username
            password = getpass()
            host_obj.password = password

    print('\n' + '~'*80)


# get info from switches
def get_info(task):
    # print banner
    c_print('Gathering device configurations')

    # get software version; use TextFSM
    sh_version = task.run(
        task=netmiko_send_command,
        command_string="show version",
        use_textfsm=True,
    )
    # save show version output to task.host
    task.host['sh_version'] = sh_version.result[0]
    # pull model from show version
    sw_model = task.host['sh_version']['hardware'][0].split("-")
    # save model to task.host
    task.host['sw_model'] = sw_model[1]

    # get interfaces; use TextFSM
    interfaces = task.run(
        task=netmiko_send_command,
        command_string="show interface switchport",
        use_textfsm=True,
    )
    # save interfaces to task.host
    task.host['intfs'] = interfaces.result

    # choose template based on switch model
    if "3750" in task.host['sw_model']:
        # 3750's use IBNSv1
        task.host['ibns_ver'] = 'v1'
        c_print('*** IBNS version 1 detected ***')
    else:
        # all else use IBNSv2
        task.host['ibns_ver'] = 'v2'
        c_print('*** IBNS version 1 detected ***')

    print('~'*80)    


# render IBNS global config templates
def ibns_global(task):
    # print banner
    c_print(f"Rendering IBNS{task.host['ibns_ver']} global configurations")
    # render global configurations
    global_cfg = task.run(
        task=text.template_file, 
        template=f"IBNS{task.host['ibns_ver']}_{task.host['region']}_global.j2",
        path="templates/", 
        **task.host
    )
    print('~'*80)    
    # return configuration
    return global_cfg.result


# IBNS interface config templates
def ibns_intf(task):
    # print banner
    c_print(f"Rendering IBNS{task.host['ibns_ver']} interface configurations")
    # init lists of interfaces
    access_interfaces = []
    uplink_interfaces = []
    # iterate over all interfaces 
    for intf in task.host['intfs']:

        # uplink interfaces
        if intf['interface'] in task.host['uplinks']:
            uplink_interfaces.append(intf)

        # other non-excluded access ports 
        elif intf['interface'] not in task.host['excluded_intf']:
            if intf['access_vlan'] in task.host['vlans']:
                access_interfaces.append(intf)

    # assign uplink interface list to task.host
    task.host['uplink_interfaces'] = uplink_interfaces
    # render uplink interface configs
    uplink_intf_cfg = task.run(
        task=text.template_file, 
        template="IBNS_uplink_intf.j2", 
        path="templates/", 
        **task.host
    )
    # assign access interface list to task.host
    task.host['access_interfaces'] = access_interfaces
    # render access interface configs
    access_intf_cfg = task.run(
        task=text.template_file, 
        template=f"IBNS{task.host['ibns_ver']}_access_intf.j2", 
        path="templates/", 
        **task.host
    )
    print('~'*80)    
    # return configuration
    return uplink_intf_cfg.result + access_intf_cfg.result


# render switch configs
def render_configs(task):
    # convert vlans in inventory from int to str
    vlans = []
    for vlan in task.host['vlans']:
        vlans.append(str(vlan))
    # save list of vlans strings back to task.host
    task.host['vlans'] = vlans
    # create vlan_list string
    task.host['vlan_list'] = ",".join(task.host['vlans'])
    # function to render global configs
    global_cfg = ibns_global(task)
    # function to run interface configs
    intf_cfg = ibns_intf(task)
    # save concatenated config to task.host
    task.host['cfg_out'] = global_cfg + "\n" + intf_cfg


# write switch configs
def write_configs(task):
    # print banner
    c_print(f"Writing IBNS{task.host['ibns_ver']} configuration files to disk")
    # write config file for each host
    with open(f"configs/{task.host}_dot1x.txt", "w+") as f:
        f.write(task.host['cfg_out'])
    print('~'*80)    


# apply switch configs
def apply_configs(task):
    # print banner
    c_print(f"Applying IBNS{task.host['ibns_ver']} configuration files to devices")
    # apply config file for each host
    task.run(
        task=netmiko_send_config, 
        config_file=f"configs/{task.host}_dot1x.txt"
    )
    print('~'*80)    


# main function
def main():
    # initialize The Norn
    nr = InitNornir()
    # filter The Norn
    nr = nr.filter(platform="cisco_ios")
    # check The Norn for credentials
    nornir_set_creds(nr)
    # run The Norn to get info
    nr.run(task=get_info)
    # run The Norn to render dot1x config
    nr.run(task=render_configs)
    # run The Norn to write config files
    nr.run(task=write_configs)
    # run The Norn to apply config files
    nr.run(task=apply_configs)


if __name__ == "__main__":
    main()
