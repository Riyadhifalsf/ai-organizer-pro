import paramiko, sys
HOST="192.168.100.10"; USER="root"; PWD="rydhflsf.123"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    c.connect(HOST, username=USER, password=PWD, timeout=10, banner_timeout=10, auth_timeout=10)
    print("SSH_OK")
    for cmd in ["hostname; uptime","pct list 2>&1 | head -30","qm list 2>&1 | head -30","ping -c2 -W2 192.168.100.230 2>&1","ip neigh show 2>&1 | head -20"]:
        print(f"===== $ {cmd} =====")
        sin,sout,serr=c.exec_command(cmd, timeout=20)
        out=sout.read().decode(errors="replace"); err=serr.read().decode(errors="replace")
        print(out.strip()[:3000])
        if err.strip(): print("STDERR:", err.strip()[:1000])
    c.close()
except Exception as e:
    print("SSH_FAIL:", repr(e)[:500])
    sys.exit(1)
