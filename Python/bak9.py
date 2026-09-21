import paramiko
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('192.168.100.10', username='root', key_filename=r'C:\Users\Babeh\.ssh\opencode_pve', timeout=8, allow_agent=False, look_for_keys=False)
def run(c, t=120):
    i,o,e=s.exec_command(c, timeout=t)
    rc=o.channel.recv_exit_status()
    print("##",c,"rc=",rc)
    print(o.read().decode('utf-8',errors='replace')[:3000])
    print(e.read().decode('utf-8',errors='replace')[:1000])
run('mkdir -p /mnt/media/dump; cat > /etc/cron.d/pve-autobackup-media <<EOF\n# Autobackup semua VM/CT ke harddisk sdb (/mnt/media) setiap jam 02:00, simpan 7 backup terakhir\nPATH=/usr/sbin:/usr/bin:/sbin:/bin\n0 2 * * * root /usr/bin/vzdump --all 1 --storage media --mode snapshot --compress zstd --remove 1 --prune-backups keep-last=7 --quiet 1\nEOF\ncat /etc/cron.d/pve-autobackup-media')
run('pvesm set media --prune-backups keep-last=7 2>&1; cat /etc/pve/storage.cfg')
s.close()
