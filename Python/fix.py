import paramiko
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.100.10', username='root', key_filename=r'C:\Users\Babeh\.ssh\opencode_pve', timeout=8, allow_agent=False, look_for_keys=False)
def run(c):
    i,o,e=s.exec_command(c, timeout=120)
    rc=o.channel.recv_exit_status()
    print(o.read().decode('utf-8',errors='replace'))
    print(e.read().decode('utf-8',errors='replace'))
run('apt-get install -y acl; setfacl -R -m u:mediauser:rwx -m u:100000:rwx /mnt/media/foto /mnt/media/video; setfacl -R -d -m u:mediauser:rwx -m u:100000:rwx /mnt/media/foto /mnt/media/video; getfacl /mnt/media/foto | head -n 20')
run('pct reboot 102')
s.close()
