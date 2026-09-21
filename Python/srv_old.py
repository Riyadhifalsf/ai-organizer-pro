import paramiko
HOST="192.168.100.10"; USER="root"; PWD="rydhflsf.123"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=10)
def run(cmd, t=60):
    sin,sout,serr=c.exec_command(cmd, timeout=t)
    return (sout.read().decode(errors="replace").strip()+"\n"+serr.read().decode(errors="replace").strip()).strip()[:6000]
print(run("pct exec 100 -- bash -lc 'cd /opt/japanese-study && docker compose ps -a 2>&1' | head -15", t=60))
print(run("pct exec 100 -- bash -lc 'cd /opt/japanese-study && docker compose logs --tail=15 api 2>&1' | head -40", t=60))
print(run("pct exec 100 -- grep -E 'ports|8081' /opt/japanese-study/docker-compose.yml 2>&1 | head", t=30))
c.close()
