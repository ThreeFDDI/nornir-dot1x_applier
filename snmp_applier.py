#!/usr/local/bin/python3
"""

This script uses the Nornir framework to apply snmp config to Catalyst switches.

Site codes can be passed as an arguement to import specific inventory files
"_hosts.yaml" and "_groups.yaml" will be appended to the site code and those
files will be imported as inventory. If not site code is specified "hosts.yaml"
and "groups.yaml" will be used.

Additional required variables from Source of Truth (SimpleInventory):


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


# render switch configs
def render_configs(task):
    """
    Nornir task to render IBNS dot1x  configurations
    """
    # function to render global configs
    snmp_cfg = ibns_snmp(task)
    # function to run interface configs
    with open(f"configs/{task.host}_snmp.txt", "w+") as file:
        file.write(snmp_cfg)
    # print completed hosts
    c_print(f"*** {task.host}: SNMP configuration rendered ***")


# apply switch configs
def apply_configs(task):
    """
    Nornir task to apply IBNS dot1x configurations to devices
    """
    # apply config file for each host
    task.run(task=napalm_configure, filename=f"configs/{task.host}_snmp.txt")
    # print completed hosts
    c_print(f"*** {task.host}: SNMP configuration applied ***")


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
    c_print(f"Rendering IBNS snmp configurations")
    # run The Norn to render dot1x config
    nr.run(task=render_configs)
    # print failed hosts
    c_print(f"Failed hosts: {nr.data.failed_hosts}")
    print("~" * 80)

    # apply switch configs
    c_print(f"Applying IBNS snmp configuration files to all devices")
    # prompt to proceed
    proceed()
    # run The Norn to apply config files
    nr.run(task=apply_configs)
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


"""
ip access-list standard SNMP_ACCESS
remark {{snmp_src_remark}}
permit {{ snmp_src }}
{% for intf in access_interfaces %}
interface {{ intf.interface }}
 authentication event fail action next-method
 authentication event server dead action authorize vlan {{ intf.access_vlan }}
{% endfor %}
"""