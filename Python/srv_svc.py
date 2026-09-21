import paramiko
HOST="192.168.100.10"; USER="root"; PWD="rydhflsf.123"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=10)
def run(cmd, t=30):
    sin,sout,serr=c.exec_command(cmd, timeout=t)
    return (sout.read().decode(errors="replace").strip()+"\n"+serr.read().decode(errors="replace").strip()).strip()[:5000]
cmds=[
 "for i in 101 102 103 104 105; do echo \"=== CT$i ls /opt ===\"; pct exec $i -- ls /opt 2>&1; done",
 "for i in 101 102 103; do echo \"=== CT$i listening ===\"; pct exec $i -- ss -tlnp 2>&1 | head -20; done",
 "echo '=== jp-db pg ==='; pct exec 103 -- ps aux 2>&1 | grep -Ei 'postgres|pg' | grep -v grep | head; pct exec 103 -- ls /var/lib/postgresql 2>&1; pct exec 103 -- env 2>&1 | grep -i -E 'postgres|password' | sed 's/=.*PASSWORD.*/=<redacted>/' | head",
 "echo '=== jp-app ==='; pct exec 102 -- ps aux 2>&1 | head -20; pct exec 102 -- ls /opt 2>&1; pct exec 102 -- cat /opt/japanese-study-v2/.env 2>&1 | sed 's/=.*/=<set>/' | head -30",
 "echo '=== jp-proxy ==='; pct exec 101 -- cat /etc/nginx/nginx.conf 2>&1 | head -50; pct exec 101 -- ss -tlnp 2>&1 | head",
]
for cmd in cmds:
    print(run(cmd, t=40)); print()
c.close()
