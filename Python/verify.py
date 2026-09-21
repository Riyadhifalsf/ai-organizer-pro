import paramiko, time
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.100.10', username='root', key_filename=r'C:\Users\Babeh\.ssh\opencode_pve', timeout=8, allow_agent=False, look_for_keys=False)
def run(c):
    i,o,e=s.exec_command(c, timeout=60)
    rc=o.channel.recv_exit_status()
    print(o.read().decode('utf-8',errors='replace'))
    print(e.read().decode('utf-8',errors='replace'))
time.sleep(10)
run('pct status 102; pct exec 102 -- df -h /mnt/foto /mnt/video')
s.close()
