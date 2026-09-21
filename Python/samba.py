import paramiko
key_path=r"C:\Users\Babeh\.ssh\opencode_pve"
s=paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect("192.168.100.10", username="root", key_filename=key_path, timeout=8, allow_agent=False, look_for_keys=False)
def run(cmd, timeout=120):
    stdin, stdout, stderr = s.exec_command(cmd, timeout=timeout)
    rc=stdout.channel.recv_exit_status()
    out=stdout.read().decode("utf-8", errors="replace")
    err=stderr.read().decode("utf-8", errors="replace")
    print(f"$ {cmd} [rc={rc}]\n{out}\n{err}\n")
    return rc
run("apt-get update && apt-get install -y samba", timeout=300)
run("id mediauser 2>&1 || useradd -M -s /usr/sbin/nologin mediauser; echo 'mediauser:media123' | chpasswd; chown -R mediauser:mediauser /mnt/media/foto /mnt/media/video; chmod -R 775 /mnt/media")
run("(echo media123; echo media123) | smbpasswd -a mediauser; smbpasswd -e mediauser")
run(r"""cat > /etc/samba/smb.conf <<'EOF'
[global]
  workgroup = WORKGROUP
  server string = PVE Media
  map to guest = never
[media]
  path = /mnt/media
  browseable = yes
  writable = yes
  guest ok = no
  valid users = mediauser root
  create mask = 0664
  directory mask = 0775
EOF
testparm -s; systemctl restart smbd nmbd; systemctl enable smbd nmbd; systemctl is-active smbd""")
s.close()
