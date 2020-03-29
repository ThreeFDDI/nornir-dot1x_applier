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


# Get interfaces
def get_interfaces(task):

    # get interfaces; use TextFSM
    interfaces = task.run(
        task=netmiko_send_command,
        command_string="show interface switchport",
        use_textfsm=True,
    )

    print(interfaces.result)

#    print(f'{task.host}: checking dot1x status.')
#    # run "show dot1x all" on each host
#    sh_dot1x = task.run(
#        task=netmiko_send_command,
#        command_string="show dot1x all",
#    )
#
#    # TTP template for dot1x status
#    dot1x_ttp_template = "Sysauthcontrol              {{ status }}"
#
#    # magic TTP parsing
#    parser = ttp(data=sh_dot1x.result, template=dot1x_ttp_template)
#    parser.parse()
#    dot1x_status = json.loads(parser.result(format='json')[0])
#
#    print(f"{task.host}: {dot1x_status[0]['status']}")
#    return dot1x_status[0]['status']


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
    nr.run(task=get_interfaces)
    # run The Norn to apply global dot1x config
    nr.run(task=apply_global_dot1x)
    # run The Norn to apply interface dot1x config
    nr.run(task=apply_int_dot1x)


if __name__ == "__main__":
    main()
