from colorama import Fore, Back, Style
import colorama

colorama.init()

# print formatting function
def c_print(printme):
    """
    Function to print centered text with newline before and after
    """
    print(Fore.GREEN + Style.BRIGHT  + f"\n" + printme.center(80, " ") + "\n")

c_print("*** STUFF ***")

#print(Fore.RED + Style.BRIGHT + "STUFF")
#print(colorama.ansi.clear_screen())