import os
# from utils import bcolors

class Log:
    def Debug(logline):
        env_var = os.getenv('MYGIT_DEBUG', default=0)
        should_print = bool(int(env_var))
        if should_print:
            from utils import bcolors
            print(f"{bcolors.OKBLUE}d: {bcolors.ENDC}{logline}")