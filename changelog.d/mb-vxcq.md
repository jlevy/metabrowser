- `metab --host` now serves on an IPv6 address.
  `--host ::` and `--host ::1` used to exit with “No available port”, because the port
  search tried each port on an IPv4 socket whatever the host.
  An IPv6 host is now printed in the brackets a URL needs, `http://[::1]:8411/view/`,
  and admitted by the Host check in that form.
  `--host ::` accepts IPv4 connections as well as IPv6 and still prints `127.0.0.1`. A
  host this machine has no address for is refused as that, “Cannot listen on host”,
  where it used to be reported as a range of busy ports.
