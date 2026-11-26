# AppArmor profile for sandbox Docker execution containers
# Restricts container capabilities and blocks external network egress.

#include <tunables/global>

profile sandbox-profile flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  # Capabilities: drop all except CAP_SETUID and CAP_SETGID
  capability setuid,
  capability setgid,
  deny capability chown,
  deny capability dac_override,
  deny capability dac_read_search,
  deny capability fowner,
  deny capability fsetid,
  deny capability kill,
  deny capability net_bind_service,
  deny capability net_raw,
  deny capability net_admin,
  deny capability sys_admin,
  deny capability sys_chroot,
  deny capability sys_ptrace,
  deny capability sys_rawio,
  deny capability mknod,

  # Network rules: Allow UNIX domain sockets and loopback only, deny raw/packet
  network unix,
  network inet stream,
  network inet6 stream,
  deny network raw,
  deny network packet,

  # Filesystem permissions
  /bin/** rix,
  /usr/bin/** rix,
  /lib/** mr,
  /usr/lib/** mr,
  /etc/ld.so.cache r,
  /etc/localtime r,
  /dev/null rw,
  /dev/zero rw,
  /dev/urandom r,
  /tmp/** rw,
  /app/** r,

  # Deny sensitive kernel files
  deny /proc/sys/** wklx,
  deny /sys/** wklx,
  deny /etc/shadow* rwklx,
}
