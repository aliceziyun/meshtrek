import json
import os
import subprocess
from multiprocessing import Process
import argparse

'''
This script is used to set up remote nodes for a distributed system.
If you want to run this script, your ssh key shouldn't have a passphrase.
'''

kube_setup_script = "./init_kube_env.sh"

def scp_command(local_path, remote_path, node_ip, node_user):
    """
    Generate the scp command to copy a file to a remote node.
    """
    subprocess.run(
        ['ssh-keyscan', '-H', node_ip],
        stdout=open(os.path.expanduser('~/.ssh/known_hosts'), 'a'),
        check=True
    )

    command = [
        'scp', local_path,
        f'{node_user}@{node_ip}:{remote_path}'
    ]
    subprocess.run(command, check=True)

def copy_files_to_nodes(file, mode=0):
    """
    Copy files to remote nodes.
    """
    if os.path.exists(file):
        if os.name == "nt":
            # need to use dos2unix to convert the line endings
            subprocess.run(['dos2unix', file], check=True)
        for node in config["nodes"]:
            if mode == 1 and node == config["nodes"][0]:
                # skip main node if worker_mode is enabled
                continue
            if mode == 2 and node != config["nodes"][0]:
                # skip worker nodes if main_mode is enabled
                continue
            scp_command(file, config["nodes_home"], node, config["nodes_user"])
    else:
        print(f"File {file} does not exist.")
        exit(1)

def execute_script(node_number, node_ip, node_home, node_user, file):
    """
    Execute the script file on a remote node.
    """
    file = os.path.basename(file)
    chmod_command = [
        'ssh', f'{node_user}@{node_ip}',
        'chmod', '+x', os.path.join(node_home, file)
    ]
    subprocess.run(chmod_command, check=True)

    command = [
        'ssh', f'{node_user}@{node_ip}',
        '/bin/bash', os.path.join(node_home, file)
    ]
    subprocess.run(command, check=True)

def execute_parallel(file=None, mode=0):
    # check if the file exists and copy it to the nodes
    copy_files_to_nodes(file, mode)
    
    # execute the setup script on each node
    processes = []
    for i, node in enumerate(config["nodes"]):
        if mode == 1 and i == 0:
            # skip main node if worker_mode is enabled
            continue
        if mode == 2 and i != 0:
            # skip worker nodes if main_mode is enabled
            continue
        args = (i, node, config["nodes_home"], config["nodes_user"], file)
        p = Process(target=execute_script, args=args)
        processes.append(p)
        p.start()

    for p in processes:
        p.join()
    
if __name__ == "__main__":
    # open the config.json file
    with open("config.json", "r") as f:
        config = json.load(f)

    # parse the command line arguments
    parser = argparse.ArgumentParser(description="Setup script for remote nodes.")
    parser.add_argument(
        "-f",
        type=str,
        help="The file to copy and execute on the remote nodes."
    )
    parser.add_argument(
        "-m",
        type=int,
        choices=[0, 1, 2],
        help="0: all nodes, 1: execute on worker nodes only, 2: execute on main node only"
    )
    args = parser.parse_args()
    file = args.f
    mode = args.m

    if file is None:
        print("Please provide a file to copy and execute.")
        help_text = parser.format_help()
        print(help_text)
        exit(1)
    execute_parallel(file, mode)