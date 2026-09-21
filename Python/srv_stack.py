import paramiko
HOST="192.168.100.10"; USER="root"; PWD="rydhflsf.123"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=10)
def run(cmd, t=60):
    sin,sout,serr=c.exec_command(cmd, timeout=t)
    return (sout.read().decode(errors="replace").strip()+"\n"+serr.read().decode(errors="replace").strip()).strip()[:7000]
print(run("pct exec 100 -- ls /opt 2>&1; pct exec 100 -- ls /opt/japanese-study-v2 2>&1 | head -30", t=30))
print(run("pct exec 100 -- docker ps --format '{{.Names}} {{.Image}} {{.Status}}' 2>&1 | head -20", t=30))
print(run("pct exec 100 -- bash -lc 'cd /opt/japanese-study-v2 && docker compose ps 2>&1' | head -20", t=60))
c.close()
