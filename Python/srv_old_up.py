import paramiko
HOST="192.168.100.10"; USER="root"; PWD="rydhflsf.123"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=10)
def run(cmd, t=120):
    sin,sout,serr=c.exec_command(cmd, timeout=t)
    return (sout.read().decode(errors="replace").strip()+"\n"+serr.read().decode(errors="replace").strip()).strip()[:6000]
print(run("pct exec 100 -- bash -lc 'cd /opt/japanese-study && docker compose up -d 2>&1' | tail -10", t=120))
print(run("pct exec 100 -- bash -lc 'sleep 15; cd /opt/japanese-study && docker compose ps 2>&1' | head -12", t=120))
c.close()
