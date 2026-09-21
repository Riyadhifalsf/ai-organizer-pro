import paramiko, time
HOST="192.168.100.10"; USER="root"; PWD="rydhflsf.123"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=10)
def run(cmd, t=60):
    sin,sout,serr=c.exec_command(cmd, timeout=t)
    return (sout.read().decode(errors="replace").strip()+"\n"+serr.read().decode(errors="replace").strip()).strip()[:6000]
print(run("pct config 100 2>&1"))
print(run("pct status 100 2>&1"))
print(">>> START 100 ...")
print(run("pct start 100 2>&1", t=90))
time.sleep(8)
print(run("pct status 100 2>&1"))
print(run("pct exec 100 -- ip -4 addr show 2>&1 | grep inet", t=30))
c.close()
