import paramiko
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.100.10', username='root', key_filename=r'C:\Users\Babeh\.ssh\opencode_pve', timeout=8, allow_agent=False, look_for_keys=False)
def run(c):
    i,o,e=s.exec_command(c, timeout=30)
    rc=o.channel.recv_exit_status()
    print("CMD:",c,"rc=",rc)
    print(o.read().decode('utf-8',errors='replace'))
    print(e.read().decode('utf-8',errors='replace'))
run('iptables -I INPUT 1 -s 192.168.100.0/24 -p tcp --dport 445 -j ACCEPT; iptables -I INPUT 1 -s 192.168.100.0/24 -p tcp --dport 139 -j ACCEPT; iptables -I INPUT 1 -s 192.168.100.0/24 -p udp --dport 137:138 -j ACCEPT; iptables -L INPUT -n --line-numbers | head -n 20')
run('apt-get install -y iptables-persistent; netfilter-persistent save; echo saved')
run('smbclient -U mediauser //localhost/media -c "ls" <<EOF\nmedia123\nEOF')
s.close()
