import paramiko
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.100.10', username='root', key_filename=r'C:\Users\Babeh\.ssh\opencode_pve', timeout=8, allow_agent=False, look_for_keys=False)
def run(c):
    i,o,e=s.exec_command(c, timeout=30)
    rc=o.channel.recv_exit_status()
    print("##",c,"rc=",rc)
    print(o.read().decode('utf-8',errors='replace')[:6000])
    print(e.read().decode('utf-8',errors='replace')[:2000])
run('pvesh create /cluster/backup --help 2>&1 | head -n 100')
s.close()
