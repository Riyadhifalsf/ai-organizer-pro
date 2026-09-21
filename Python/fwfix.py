import paramiko
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.100.10', username='root', key_filename=r'C:\Users\Babeh\.ssh\opencode_pve', timeout=8, allow_agent=False, look_for_keys=False)
def run(c):
    i,o,e=s.exec_command(c, timeout=30)
    rc=o.channel.recv_exit_status()
    print("##",c,"rc=",rc)
    print(o.read().decode('utf-8',errors='replace')[:4000])
    print(e.read().decode('utf-8',errors='replace')[:1000])
run('cp /etc/iptables/rules.v4 /etc/iptables/rules.v4.bak; sed -i "/dport 3128/a -A INPUT -s 192.168.100.0/24 -p tcp -m tcp --dport 445 -j ACCEPT\\n-A INPUT -s 192.168.100.0/24 -p tcp -m tcp --dport 139 -j ACCEPT\\n-A INPUT -s 192.168.100.0/24 -p udp -m udp --dport 137:138 -j ACCEPT" /etc/iptables/rules.v4; grep -E "445|139|137" /etc/iptables/rules.v4; /usr/sbin/iptables-restore /etc/iptables/rules.v4; iptables -S | grep -E "445|139|137"; echo OK')
s.close()
