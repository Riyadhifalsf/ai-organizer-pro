import paramiko
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.100.10', username='root', key_filename=r'C:\Users\Babeh\.ssh\opencode_pve', timeout=8, allow_agent=False, look_for_keys=False)
def run(c, t=600):
    i,o,e=s.exec_command(c, timeout=t)
    rc=o.channel.recv_exit_status()
    print(o.read().decode('utf-8',errors='replace')[:3000])
    print(e.read().decode('utf-8',errors='replace')[:1000])
    print("rc=",rc)
run('vzdump 104 --storage media --mode snapshot --compress zstd --remove 1 --prune-backups keep-last=7', t=900)
run('ls -lh /mnt/media/dump/; df -h /mnt/media')
s.close()
