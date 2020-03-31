#!/usr/local/bin/python3
'''
This script is to apply dot1x config to Catalyst switch stacks
'''

from nornir import InitNornir
from nornir.core.filter import F
from nornir.plugins.functions.text import print_result
from nornir.plugins.tasks.networking import netmiko_send_command
from pprint import pprint as pp
from ttp import ttp


# Get info from switches
def get_info(task):

    # run "show version" on each host
    sh_version = task.run(
        task=netmiko_send_command,
        command_string="show version",
        use_textfsm=True,
    )

    # save show version output to task.host
    task.host['sh_version'] = sh_version.result[0]

    # pull model from show version
    sw_model = task.host['sh_version']['hardware'][0].split("-")
    task.host['sw_model'] = sw_model[1]

    # get interfaces; use TextFSM
    interfaces = task.run(
        task=netmiko_send_command,
        command_string="show interface switchport",
        use_textfsm=True,
    )

    task.host['interfaces'] = interfaces.result


# Apply global dot1x config template
def apply_global_dot1x(task):
    _stuff = None


# Apply interface dot1x config templates
def apply_int_dot1x(task):
    _stuff = None


def main():
    # initialize The Norn
    nr = InitNornir()
    # filter The Norn
    nr = nr.filter(platform="cisco_ios")
    # run The Norn to get interfaces
    nr.run(task=get_info)
    # run The Norn to apply global dot1x config
    nr.run(task=apply_global_dot1x)
    # run The Norn to apply interface dot1x config
    nr.run(task=apply_int_dot1x)


if __name__ == "__main__":
    main()
