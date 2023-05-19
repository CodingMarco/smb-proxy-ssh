import subprocess
import os
import yaml
import random
import time

def generate_random_port():
    return random.randint(49152, 65535)  # Port range for dynamic/private ports

def open_ssh_tunnel(hostname, ssh_user, ssh_password, ssh_private_key_path, remote_port):
    local_port = generate_random_port()
    ssh_command = ['ssh', '-nNT', '-L', f'{local_port}:localhost:{remote_port}', f'{ssh_user}@{hostname}']

    if ssh_private_key_path:
        ssh_command += ['-i', ssh_private_key_path]
    else:
        ssh_command = ['sshpass', '-p', ssh_password] + ssh_command

    process = subprocess.Popen(ssh_command, start_new_session=True)
    # Wait until the tunnel is open
    while True:
        try:
            subprocess.check_output(['nc', '-z', 'localhost', str(local_port)])
            break
        except subprocess.CalledProcessError:
            time.sleep(0.05)

    return local_port, process

def mount_share(smbcredentials_file_path, share, port, mount_dir):
    subprocess.call(['mount', '-t', 'cifs', '-o', f'credentials={smbcredentials_file_path},port={port}',
                     f'//localhost/{share}', mount_dir])

    return mount_dir

def get_single_share_config(share_name, share_path):
    config =  f"[{share_name}]\n"
    config += f"    path = {share_path}\n"
    config +=  "    read only = no\n"
    config +=  "    inherit permissions = yes\n"
    config +=  "\n"

    return config

def setup_smb_proxy(config_path):
    with open(config_path) as file:
        config = yaml.safe_load(file)

    proxy_username = config['proxy']['username']
    proxy_password = config['proxy']['password']
    targets = config['targets']

    smb_config =  "[global]\n"
    smb_config += "    server role = standalone server\n\n"
    ssh_processes = []
    mount_paths = []
    for target_name, target_config in targets.items():
        hostname = target_config['hostname']
        ssh_user = target_config['ssh_user']
        ssh_password = target_config.get('ssh_password')
        ssh_private_key_path = target_config.get('ssh_private_key_path')
        smbcredentials_file_path = os.path.join(os.getcwd(), target_config['smbcredentials_file_path'])
        shares = target_config['shares']

        local_port, process = open_ssh_tunnel(hostname, ssh_user, ssh_password, ssh_private_key_path, 445)
        if process.poll() is not None:
            raise Exception(f"Failed to open SSH tunnel to {hostname}")

        ssh_processes.append(process)

        for share in shares:
            share_path_as_name = share.strip('/').replace('/', '_')
            share_name = f"{target_name}_{share_path_as_name}"
            share_mount_path = os.path.join('/mnt/shareproxy', target_name, share_path_as_name)
            os.makedirs(share_mount_path, exist_ok=True)
            smb_config += get_single_share_config(share_name, share_mount_path)

            mount_share(smbcredentials_file_path, share, local_port, share_mount_path)
            print(f"Mounted {share} to {share_mount_path}")
            mount_paths.append(share_mount_path)

    smb_conf_path = 'smb.conf'
    with open(smb_conf_path, 'w') as file:
        file.write(smb_config)

    print("SMB-SSH-Proxy setup completed.")
    return ssh_processes, mount_paths


def cleanup(ssh_processes, mount_paths):
    for mount_path in mount_paths:
        subprocess.call(['umount', mount_path])

    for process in ssh_processes:
        process.kill()

    print("SMB-SSH-Proxy cleanup completed.")


if __name__ == '__main__':
    ssh_processes, mount_paths = setup_smb_proxy('test.yml')
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting on keyboard interrupt")
    except Exception as e:
        print(f"Exiting due to exception: {e}")
    finally:
        cleanup(ssh_processes, mount_paths)
