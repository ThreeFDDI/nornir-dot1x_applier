from colorama import Fore, Style

# print formatting function
def c_print(printme):
    """
    Function to print centered text with newline before and after
    """
    print(Fore.BLUE + Style.BRIGHT + f"\n" + printme.center(80, " ") + "\n")

c_print("*** STUFF ***")

#print(Fore.RED + Style.BRIGHT + "STUFF")