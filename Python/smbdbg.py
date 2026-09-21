import paramiko, threading, time
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.100.10', username='root', key_filename=r'C:\Users\Babeh\.ssh\opencode_pve', timeout=8, allow_agent=False, look_for_keys=False)
def run(c, t=20):
    i,o,e=s.exec_command(c, timeout=t)
    rc=o.channel.recv_exit_status()
    print(o.read().decode('utf-8',errors='replace'))
    print(e.read().decode('utf-8',errors='replace'))
run('iptables -L INPUT -n --line-numbers | head -n 20; tail -n 30 /var/log/samba/log.smbd; smbstatus --shares 2>&1 | head -n 20')
run('netstat -tlnp | grep -E "445|139"')
s.close()
