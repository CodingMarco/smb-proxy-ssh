import subprocess
import os
import yaml
import random
import string

def generate_random_port():
    return random.randint(49152, 65535)  # Port range for dynamic/private ports

def open_ssh_tunnel(hostname, username, password, remote_port):
    local_port = generate_random_port()
    subprocess.call(['ssh', '-L', f'{local_port}:localhost:{remote_port}', f'{username}@{hostname}'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return local_port

def mount_share(hostname, ssh_user, ssh_password, ssh_private_key_name, smbcredentials_file_path, share, mount_path):
    mount_dir = os.path.join(mount_path, hostname.replace(".", "_"), share.replace("/", "_"))
    os.makedirs(mount_dir, exist_ok=True)

    subprocess.call(['sshpass', '-p', ssh_password, 'ssh', '-o', 'StrictHostKeyChecking=no',
                     '-i', ssh_private_key_name, f'{ssh_user}@{hostname}', 'mkdir', '-p', smbcredentials_file_path])
    subprocess.call(['sshpass', '-p', ssh_password, 'scp', '-o', 'StrictHostKeyChecking=no',
                     '-i', ssh_private_key_name, smbcredentials_file_path,
                     f'{ssh_user}@{hostname}:{smbcredentials_file_path}'])

    subprocess.call(['sudo', 'mount', '-t', 'cifs', '-o', f'credentials={smbcredentials_file_path}',
                     f'//localhost/{share}', mount_dir])

    return mount_dir

def generate_smb_share_config(targets):
    config = "[global]\nworkgroup = WORKGROUP\n\n"
    for pc_name, pc_data in targets.items():
        for share_path in pc_data['shares']:
            share_name = f"{pc_name}_{share_path.replace('/', '_')}"
            config += f"[{share_name}]\n"
            config += f"path = {os.path.join('/mnt/shareproxy', pc_name.replace('.', '_'), share_path.replace('/', '_'))}\n"
            config += "read only = no\n\n"
    return config

def setup_smb_proxy(config_path):
    with open(config_path) as file:
        config = yaml.safe_load(file)

    proxy_username = config['proxy']['username']
    proxy_password = config['proxy']['password']
    targets = config['targets']

    smbcredentials_file_path = os.path.join('/etc/samba/smbcredentials', ''.join(random.choices(string.ascii_letters + string.digits, k=8)))
    os.makedirs(os.path.dirname(smbcredentials_file_path), exist_ok=True)

    subprocess.call(['sudo', 'mkdir', '-p', '/mnt/shareproxy'])

    smb_conf_path = '/etc/samba/smb.conf'
    smb_share_config = generate_smb_share_config(targets)
    with open(smb_conf_path, 'w') as file:
        file.write(smb_share_config)

    subprocess.call(['sudo', 'service', 'smbd', 'restart'])

    for pc_name, pc_data in targets.items():
        hostname = pc_data['hostname']
        ssh_user = pc_data['ssh_user']
        ssh_password = pc_data['ssh_password']
        ssh_private_key_name = pc_data['ssh_private_key_name']
        shares = pc_data['shares']

        local_port = open_ssh_tunnel(hostname, proxy_username, proxy_password, 445)

        for share in shares:
            mount_path = '/mnt/shareproxy'
            mount_share(hostname, ssh_user, ssh_password, ssh_private_key_name,
                        smbcredentials_file_path, share, mount_path)

    print("SMB-SSH-Proxy setup completed.")

# Usage:
setup_smb_proxy('config.yaml')
