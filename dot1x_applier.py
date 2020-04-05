#!/usr/local/bin/python3
'''
This script is to apply dot1x config to Catalyst switch stacks
'''

from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_command
from nornir.plugins.tasks.networking import netmiko_send_config
from nornir.plugins.tasks import text


# Get info from switches
def get_info(task):

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
    

# IBNS global config templates
def ibns_global(task, ibns_ver):
    global_cfg = task.run(
        task=text.template_file, 
        template=f"IBNS{ibns_ver}_global.j2", 
        path="templates/", 
        **task.host
    )

    return global_cfg.result


# IBNS interface config templates
def ibns_intf(task, ibns_ver):
    
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
        template=f"IBNS{ibns_ver}_access_intf.j2", 
        path="templates/", 
        **task.host
    )

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

    # choose template based on switch model
    if "3750" in task.host['sw_model']:
        # 3750's use IBNSv1
        ibns_ver = 'v1'
    else:
        # all else use IBNSv2
        ibns_ver = 'v2'

    # function to render global configs
    global_cfg = ibns_global(
        task,
        ibns_ver,
    )

    # function to run interface configs
    intf_cfg = ibns_intf(
        task,
        ibns_ver,
    )

    print(global_cfg + intf_cfg)

# apply switch configs
def apply_configs(task):
    _stuff = None


# main function
def main():
    # initialize The Norn
    nr = InitNornir()
    # filter The Norn
    nr = nr.filter(platform="cisco_ios")
    # run The Norn to get info
    nr.run(task=get_info)
    # run The Norn to apply dot1x config
    nr.run(task=render_configs)


if __name__ == "__main__":
    main()
