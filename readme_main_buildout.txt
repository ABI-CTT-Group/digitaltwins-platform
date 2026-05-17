This has been moving fast, so possibly talk to Matt before
you expect the docs to be totally up to date with the code.

Current (May 18 '26) state:

Need the DNS changed for:

130.216.254.174   test.digitaltwins.auckland.ac.nz
130.216.254.174   abidigitaltwins.auckland.ac.nz

130.216.254.212   dev.digitaltwins.auckland.ac.nz
130.216.254.212   dev.abidigitaltwins.auckland.ac.nz


The current app is installed on both those addresses, but
will only answer to test.digitaltwins.auckland.ac.nz so you
have to put those IP address entries in your /etc/hosts
file to trick your client into thinking those are the addresses.

Portal (130.216.254.174) currently has a remote compute of
drai_compute configured against it, as well as the box under Chinchien's desk.
This latter one doesn't have the logging yet sorted out, so I'm
not yet gettings its logs into the MINIO system and therefore
visible in the airflow UI.

Instructions to install the platform are in buildout/dev/readme_overall.txt

Instructions to install the compute are in buildout/dev/compute/compute_node_readme.txt
