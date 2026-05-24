from Simulation import Simulation
import argparse
import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) # add parent folder to paths
from Server.Node import Node

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-ns", "--no-show",
        action="store_false",
        dest="show",
        help="Disable rendering window"
    )

    parser.add_argument(
        "-nm", "--no-sim",
        action="store_false",
        dest="sim",
        help="Disable simulation mode"
    )

    # Defaults (True unless turned off)
    parser.set_defaults(show=True, sim=True)

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    node = Node("navigation")
    
    # node subscriptions go here 
    
    simulation = Simulation(args,node)
    simulation.run()