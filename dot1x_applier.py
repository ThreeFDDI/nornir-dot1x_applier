#!/usr/local/bin/python3
"""

This script uses the Nornir framework to apply dot1x config to Catalyst switches.

Site codes can be passed as an arguement to import specific inventory files
"_hosts.yaml" and "_groups.yaml" will be appended to the site code and those
files will be imported as inventory. If not site code is specified "hosts.yaml"
and "groups.yaml" will be used.

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

"""

import json
import site
import sys
from getpass import getpass
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_command
from nornir.plugins.tasks.networking import netmiko_send_config
from nornir.plugins.tasks.networking import netmiko_save_config
from nornir.plugins.tasks.networking import napalm_configure
from nornir.plugins.tasks import text
from ttp import ttp


# print formatting function
def c_print(printme):
    """
    Function to print centered text with newline before and after
    """
    print(f"\n" + printme.center(80, " ") + "\n")


# continue banner
def proceed():
    """
    Function to prompt to proceed or exit script
    """
    c_print("********** PROCEED? **********")
    # capture user input
    confirm = input(" " * 36 + "(y/n) ")
    # quit script if not confirmed
    if confirm.lower() != "y":
        c_print("******* EXITING SCRIPT *******")
        print("~" * 80)
        exit()
    else:
        c_print("********* PROCEEDING *********")


# test Nornir textfsm result
def test_norn_textfsm(task, result, cmd):
    """
    Test Nornir result expected to be a dict within a list
    """
    if type(result) != list or type(result[0]) != dict:
        c_print(f'*** {task.host}: ERROR running "{cmd}" ***')


# test Nornir result
def test_norn(task, result):
    """
    Test Nornir result expected to be a string
    """
    if type(result) != str:
        c_print(f"*** {task.host}: ERROR running Nornir task ***")


# set device credentials
def kickoff():
    """
    Nornir kickoff function to initialize inventory and set or confirm credentials
    """
    # check arguments for site code
    if len(sys.argv) < 2:
        # set no site code
        site = ""
        site_ = ""

    else:
        # set site code
        site = sys.argv[1]
        site_ = sys.argv[1] + "_"

    # print banner
    print()
    print("~" * 80)

    # initialize The Norn
    nr = InitNornir(
        logging={"file": f"logs/{site_}nornir_log.txt", "level": "debug"},
        inventory={
            "plugin": "nornir.plugins.inventory.simple.SimpleInventory",
            "options": {
                "host_file": f"inventory/{site_}hosts.yaml",
                "group_file": f"inventory/{site_}groups.yaml",
                "defaults_file": "inventory/defaults.yaml",
            },
        },
    )

    # filter The Norn
    nr = nr.filter(platform="ios")

    if len(nr.inventory.hosts) == 0:
        c_print("*** No matching hosts found in inventory ***")
        print("~" * 80)
        exit()

    else:
        c_print(
            "This script will apply IBNS dot1x configurations to Cisco Catalyst switches"
        )
        c_print(f"Inventory includes the following devices {site}:")
        for host in nr.inventory.hosts.keys():
            c_print(f"*** {host} ***")

    c_print("Checking inventory for credentials")
    # check for existing credentials in inventory

    if nr.inventory.defaults.username == None or nr.inventory.defaults.password == None:
        c_print("Please enter device credentials:")

        if nr.inventory.defaults.username == None:
            nr.inventory.defaults.username = input("Username: ")

        if nr.inventory.defaults.password == None:
            nr.inventory.defaults.password = getpass()
            print()

    print("~" * 80)
    return nr


# enable SCP
def scp_enable(task):
    """
    Nornir task to enable SCP as required for for NAPALM
    """
    cmd = "ip scp server enable"
    task.run(task=netmiko_send_config, config_commands=cmd)
    c_print(f"*** {task.host}: SCP has been enabled ***")


# disable SCP
def scp_disable(task):
    """
    Nornir task to disable SCP after running NAPALM tasks
    """
    cmd = "no ip scp server enable"
    task.run(task=netmiko_send_config, config_commands=cmd)
    task.run(task=netmiko_save_config)
    c_print(f"*** {task.host}: SCP has been disabled ***")


# get info from switches
def get_info(task):
    """
    Nornir task to get software version; use TextFSM
    """
    cmd = "show version"
    sh_version = task.run(
        task=netmiko_send_command, command_string=cmd, use_textfsm=True
    )
    # test Nornir result
    test_norn_textfsm(task, sh_version.result, cmd)
    # save show version output to task.host
    task.host["sh_version"] = sh_version.result[0]
    # pull model from show version
    sw_model = task.host["sh_version"]["hardware"][0].split("-")
    # save model to task.host
    task.host["sw_model"] = sw_model[1]
    # get interfaces; use TextFSM
    cmd = "show interface switchport"
    interfaces = task.run(
        task=netmiko_send_command, command_string=cmd, use_textfsm=True
    )
    # test Nornir result
    test_norn_textfsm(task, interfaces.result, cmd)
    # save interfaces to task.host
    task.host["intfs"] = interfaces.result
    # convert vlans in inventory from int to str
    vlans = []
    for vlan in task.host["vlans"]:
        vlans.append(str(vlan))
    # save list of vlans strings back to task.host
    task.host["vlans"] = vlans
    # create vlan_list string
    task.host["vlan_list"] = ",".join(task.host["vlans"])

    # choose template based on switch model
    if "3750V2" in task.host["sw_model"]:
        # 3750V2's use IBNSv1
        task.host["ibns_ver"] = "v1"
        c_print(f"*** {task.host}: IBNS version 1 ***")

    elif "3750X" in task.host['sw_model']:
        # 3750X's use IBNSv2-modified
        task.host['ibns_ver'] = 'v2-alt'
        c_print(f"*** {task.host}: IBNS version 2 (modified) ***")

    else:
        # all else use IBNSv2
        task.host["ibns_ver"] = "v2"
        c_print(f"*** {task.host}: IBNS version 2 ***")

    # get ip interface brief; use TextFSM
    cmd = "show ip interface brief | e unas"
    ip_int_br = task.run(
        task=netmiko_send_command, command_string=cmd, use_textfsm=True
    )
    # test Nornir result
    test_norn_textfsm(task, ip_int_br.result, cmd)
    # save ip interfaces to task.host
    task.host["ip_int_br"] = ip_int_br.result


# render IBNS global config templates
def ibns_global(task):
    """
    Nornir task to render global IBNS dot1x  configurations
    """
    global_cfg = task.run(
        task=text.template_file,
        template=f"IBNS{task.host['ibns_ver']}_{task.host['region']}_global.j2",
        path="templates/",
        **task.host,
    )
    # return configuration
    return global_cfg.result


# render IBNS snmp config templates
def ibns_snmp(task):
    """
    Nornir task to render global IBNS dot1x  configurations
    """
    snmp_cfg = task.run(
        task=text.template_file,
        template=f"IBNS_snmp.j2",
        path="templates/",
        **task.host,
    )
    # return configuration
    return snmp_cfg.result


# IBNS interface config templates
def ibns_intf(task):
    """
    Nornir task to render interface IBNS dot1x  configurations
    """
    # init lists of interfaces
    access_interfaces = []
    uplink_interfaces = []
    # iterate over all interfaces
    for intf in task.host["intfs"]:

        # uplink interfaces
        if intf["interface"] in task.host["uplinks"]:
            uplink_interfaces.append(intf)

        # other non-excluded access ports
        elif intf["interface"] not in task.host["excluded_intf"]:
            if intf["access_vlan"] in task.host["vlans"]:
                access_interfaces.append(intf)

    # assign uplink interface list to task.host
    task.host["uplink_interfaces"] = uplink_interfaces
    # render uplink interface configs
    uplink_intf_cfg = task.run(
        task=text.template_file,
        template="IBNS_uplink_intf.j2",
        path="templates/",
        **task.host,
    )
    # assign access interface list to task.host
    task.host["access_interfaces"] = access_interfaces
    # render access interface configs
    access_intf_cfg = task.run(
        task=text.template_file,
        template=f"IBNS{task.host['ibns_ver']}_access_intf.j2",
        path="templates/",
        **task.host,
    )

    # init list of L3 vlan interfaces
    l3_vlan_int = ["Vlan777"]
    # list of vlan interfaces that will not relay
    no_relay_ints = ["1", "666", "667"]
    # iterate over active L3 interfaces
    for intf in task.host["ip_int_br"]:
        # accept only those that are active vlan interfaces
        if intf["intf"].startswith("Vlan") == True and intf["status"] == "up":
            # strip vlan id from interface name
            vlan_id = intf["intf"].strip("Vlan")
            # compare with list of no relay ints
            if vlan_id not in no_relay_ints:
                # add to list of interfaces for ISE DHPC relay
                l3_vlan_int.append(intf["intf"])

    # save L3 vlan interfaces to task.host
    task.host["l3_vlan_int"] = l3_vlan_int
    # render L3 vlan interface configs
    l3_vlan_int_cfg = task.run(
        task=text.template_file,
        template=f"IBNS_L3VLAN_intf.j2",
        path="templates/",
        **task.host,
    )

    # return configuration
    return uplink_intf_cfg.result + access_intf_cfg.result + l3_vlan_int_cfg.result


# render switch configs
def render_configs(task):
    """
    Nornir task to render IBNS dot1x  configurations
    """
    
    # run function to render global configs
    global_cfg = ibns_global(task)
    # write global config file for each host
    with open(f"configs/{task.host}_dot1x_global.txt", "w+") as file:
        file.write(global_cfg)
    # print completed hosts
    c_print(f"*** {task.host}: dot1x global configuration rendered ***")

    # run function to render snmp configs
    snmp_cfg = ibns_snmp(task)
    # function to run interface configs
    with open(f"configs/{task.host}_snmp.txt", "w+") as file:
        file.write(snmp_cfg)
    # print completed hosts
    c_print(f"*** {task.host}: SNMP configuration rendered ***")

    # run function to run interface configs
    intf_cfg = ibns_intf(task)
    # write interface config file for each host
    with open(f"configs/{task.host}_dot1x_intf.txt", "w+") as file:
        file.write(intf_cfg)
    # print completed hosts
    c_print(f"*** {task.host}: dot1x intf configurations rendered ***")


# 3750X specific AAA changes
def aaa_3750x(task):
    """
    Function to deal with 3750X AAA madness
    """
    # check current authentication display config-mode
    cmd = "authentication display config-mode"
    aaa_mode = task.run(
        task=netmiko_send_command,
        command_string=cmd
    )
    # strip result for printing
    aaa_mode = aaa_mode.result.strip('\n')
    # print current authentication display config-mode
    c_print(f"*** {task.host}: {aaa_mode} ***")

    # run special AAA if in legacy mode
    if "legacy" in aaa_mode:
        # enable new-style AAA commands
        cmd = "authentication display new-style"
        task.run(
            task=netmiko_send_command,
            command_string=cmd
        )
        
        # force conversion to new-style using manual Netmiko connection
        net_connect = task.host.get_connection("netmiko", task.nornir.config)
        # command to force conversion
        cmd = "aaa accounting identity default start-stop group ISE"
        output = net_connect.config_mode()
        # look for confirmation prompt
        output += net_connect.send_command(
            cmd, 
            expect_string=r"yes", 
            strip_prompt=False, 
            strip_command=False
        )
        # confirm conversion
        output += net_connect.send_command(
            "yes", 
            expect_string=r"#",
            strip_prompt=False, 
            strip_command=False
        )
        output += net_connect.exit_config_mode()
        # conversion complete
        c_print(f"*** {task.host}: authentication display new-style enabled ***")


# apply switch configs
def apply_configs(task):
    """
    Nornir task to apply IBNS dot1x configurations to devices
    """

    if "3750X" in task.host['sw_model']:
        # run 3750X function
        aaa_3750x(task)

    # apply global config file for each host
    task.run(task=napalm_configure, filename=f"configs/{task.host}_dot1x_global.txt")
    # print completed hosts
    c_print(f"*** {task.host}: dot1x global configuration applied ***")
    # apply snmp config file for each host
    task.run(task=napalm_configure, filename=f"configs/{task.host}_snmp.txt")
    # print completed hosts
    c_print(f"*** {task.host}: SNMP configuration applied ***")
    # apply interface config file for each host
    task.run(task=napalm_configure, filename=f"configs/{task.host}_dot1x_intf.txt")
    # print completed hosts
    c_print(f"*** {task.host}: dot1x interface configuration applied ***")


# verify dot1x
def verify_dot1x(task):
    """
    Nornir task to verify dot1x has been enabled
    """
    # run "show dot1x all" on each host
    sh_dot1x = task.run(task=netmiko_send_command, command_string="show dot1x all")
    # TTP template for dot1x status
    dot1x_ttp_template = "Sysauthcontrol              {{ status }}"
    # magic TTP parsing
    parser = ttp(data=sh_dot1x.result, template=dot1x_ttp_template)
    parser.parse()
    dot1x_status = json.loads(parser.result(format="json")[0])

    # write dot1x verification report for each host
    with open(f"output/{task.host}_dot1x_verified.txt", "w+") as file:
        file.write(sh_dot1x.result)

    # print dot1x status
    c_print(f"*** {task.host} dot1x status: {dot1x_status[0]['status']} ***")


# main function
def main():
    """
    Main function and script logic
    """
    # kickoff The Norn
    nr = kickoff()

    # enable SCP
    c_print(f"Enabling SCP for NAPALM on all devices")
    # run The Norn to enable SCP
    nr.run(task=scp_enable)
    c_print(f"Failed hosts: {nr.data.failed_hosts}")
    print("~" * 80)

    # gather switch info
    c_print("Gathering device configurations")
    # run The Norn to get info
    nr.run(task=get_info)
    # print failed hosts
    c_print(f"Failed hosts: {nr.data.failed_hosts}")
    print("~" * 80)

    # render switch configs
    c_print(f"Rendering IBNS dot1x configurations")
    # run The Norn to render dot1x config
    nr.run(task=render_configs)
    # print failed hosts
    c_print(f"Failed hosts: {nr.data.failed_hosts}")
    print("~" * 80)

    # apply switch configs
    c_print(f"Applying IBNS dot1x configuration files to all devices")
    # prompt to proceed
    proceed()
    # run The Norn to apply config files
    nr.run(task=apply_configs)
    # print failed hosts
    c_print(f"Failed hosts: {nr.data.failed_hosts}")
    print("~" * 80)

    # verify dot1x configs
    c_print(f"Verifying IBNS dot1x configuration of all devices")
    # run The Norn to verify dot1x config
    nr.run(task=verify_dot1x, num_workers=1)
    # print failed hosts
    c_print(f"Failed hosts: {nr.data.failed_hosts}")
    print("~" * 80)

    # disable SCP
    c_print(f"Disabling SCP server on all devices")
    # prompt to proceed
    proceed()
    # run The Norn to disable SCP and save configs
    nr.run(task=scp_disable)
    c_print(f"Failed hosts: {nr.data.failed_hosts}")
    print("~" * 80)


if __name__ == "__main__":
    main()
