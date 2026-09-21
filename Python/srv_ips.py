import paramiko
HOST="192.168.100.10"; USER="root"; PWD="rydhflsf.123"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=10)
def run(cmd, t=25):
    sin,sout,serr=c.exec_command(cmd, timeout=t)
    return (sout.read().decode(errors="replace").strip()+"\n"+serr.read().decode(errors="replace").strip()).strip()[:4000]
for i in [100,101,102,103,104,105]:
    print(f"===== CT{i} config =====")
    print(run(f"pct config {i} 2>&1 | grep -Ei 'hostname|net0|ip|memory|cores'"))
for i in [101,102,103,104,105]:
    print(f"===== CT{i} ip =====")
    print(run(f"pct exec {i} -- ip -4 addr show 2>&1 | grep -E 'inet '"))
c.close()
