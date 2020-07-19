#!/usr/local/bin/python3

"""
This script uses the Nornir framework to collect discovery information from 
Cisco network devices and save the output to file. Devices and parameters are 
provided by the SimpleInventory plugin for Nornir using YAML files. 
"""

import sys
import difflib
from getpass import getpass
from nornir import InitNornir
from nornir.plugins.tasks.networking import netmiko_send_command


# print formatting function
def c_print(printme):
    # Print centered text with newline before and after
    print(f"\n" + printme.center(80, " ") + "\n")


# Nornir kickoff
def kickoff():
    # print banner
    print()
    print("~" * 80)
    c_print("This script will diff startup / running configs on Cisco devices")

    if len(sys.argv) < 2:
        site = ""

    else:
        site = sys.argv[1] + "_"

    # initialize The Norn
    nr = InitNornir(
        inventory={
            "plugin": "nornir.plugins.inventory.simple.SimpleInventory",
            "options": {
                "host_file": f"inventory/{site}hosts.yaml",
                "group_file": f"inventory/{site}groups.yaml",
                "defaults_file": "inventory/defaults.yaml",
            },
        }
    )

    # filter The Norn
    nr = nr.filter(platform="ios")

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


def cfg_differ(task):
    """
    This function grabs the startup and running configs then diffs them
    """
    c_print(f"*** Diffing configs from {task.host} ***")

    # send commands to device
    run_cfg = task.run(task=netmiko_send_command, command_string="show run")
    start_cfg = task.run(task=netmiko_send_command, command_string="show start")

    # extract result and split lines
    run_cfg = run_cfg.result.splitlines(1)
    start_cfg = start_cfg.result.splitlines(1)

    # run diff on each line
    for line in difflib.unified_diff(start_cfg, run_cfg, n=5):
        print(line, end=" ")


def main():
    # kickoff The Norn
    nr = kickoff()
    # run The Norn
    nr.run(task=cfg_differ, num_workers=1)
    c_print(f"Failed hosts: {nr.data.failed_hosts}")
    print("~" * 80)


if __name__ == "__main__":
    main()
