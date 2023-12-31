# Validator SOP Part 1: Hardware, Software, & Deposit Setup

## Table of Contents

- [Step 0 Purchase Equipment + Assemble NUC](#step-0-purchase-equipment--assemble-nuc)
- [Step 1 Generate Staking Data](#step-1-generate-staking-data)
- [Step 2 Install Linux Server](#step-2-install-linux-server)
- [Step 3 Secure the Server](#step-3-secure-the-server)
  - [Modify the Default SSH Port](#modify-the-default-ssh-port)
  - [Configure the Firewall](#configure-the-firewall)
  - [Configure Fail2Ban](#configure-fail2ban)
  - [Disable Root Access](#disable-root-access)
- [Step 4 Configure Port Forwarding](#step-4-configure-port-forwarding)
- [Step 5 Configure Timekeeping](#step-5-configure-timekeeping)
- [Step 6 Generate Client Auth Secret](#step-6-generate-client-auth-secret)
- [Step 7 Configure Geth](#step-7-configure-geth)
- [Step 8 Install Prysm](#step-8-install-prysm)
- [Step 9 Configure the Beacon Node Service](#step-9-configure-the-beacon-node-service)
- [Step 10 Configure the Validator Service](#step-10-configure-the-validator-service)
- [Step 11 Import Validator Keys](#step-11-import-validator-keys)
  - [Import the Validator Keystore Files into Prysm](#import-the-validator-keystore-files-into-prysm)
  - [Create a Wallet Password File](#create-a-wallet-password-file)
- [Step 12 Fund the Validators](#step-12-fund-the-validators)
  - [Check the Status of Your Validator Deposits](#check-the-status-of-your-validator-deposits)

![DaVinciNode](.imgs/DaVinci-Node.jpeg)

### Step 0 Purchase Equipment + Assemble NUC

First, you'll need hardware to run the validator software on. [Requirements can be found here](https://www.quicknode.com/guides/infrastructure/node-setup/ethereum-full-node-vs-archive-node/), suggested hardware (slight overkill) are as follows:

- Intel NUC 11+ (tall) - bare-bones model with 6+ core CPU
- 16GB RAM (**32GB** preferred) - 'laptop' RAM (not full size)
- M.2 SSD 2TB (**4TB** preferred)
- Ethernet connection with 300 Mbps symmetrical
- USB drive (used to install Linux) 4GB+
- HDMI (or USB) cord and connectable monitor for initial set up
- USB keyboard and mouse (mouse is only required if using Ubuntu desktop to generate new validator keys)

While not a hard requirement, it's also recommended to purchase a 1000+VA sine wave UPS to act as a battery backup in the case of a power failure. Note that in order for this to be effective, you should plug the validator **and** internet infrastructure into the UPS. The goal is to guard against both unclean shutdowns as well as downtime.

Once equipment has been obtained, simply install the RAM and SSD in the NUC. Because some of the below processes require using an air-gapped machine, **do not connect the device to the internet**.

Note: You will also need a small screwdriver to handle installation.

An example hardware list can be found [here](.imgs/validator_hardware.xlsx).

### Step 1 Generate Staking Data

**Only if setting up a new validator:**

If setting up a new validator (and haven't already generated deposit data and validator key(s)), you'll need to run the deposit tool CLI, and should do so from an **air-gapped machine**.

**If you are not generating new keys, skip to step 2.**

In order to have a machine ready to go, we will need to install an OS on your new validator hardware built in step 0.  We'll be using Ubuntu Desktop. On your laptop, navigate to [ubuntu.com](https://ubuntu.com/download/desktop), download the latest LTS copy of Ubuntu Desktop (as of 12.15.23, *22.04.3 LTS*). In addition, download and install the [Etcher tool](https://www.balena.io/etcher) which will allow you to flash the operating system onto the USB drive. Lastly, download the latest version of the [deposit CLI tool](https://github.com/ethereum/staking-deposit-cli/releases) - you want the **AMD64** version (as of 12.15.23, *2.7.0*), and unzip the executable file.

With all the software and data assembled, run the Etcher tool to flash the USB drive with Ubuntu Desktop using your laptop. Insert the USB into your air gapped machine (built in step 0), connect the machine to a monitor via HDMI (or USB), keyboard, and mouse, and go through the installation process (which should occur automatically). Make sure to choose the minimum settings allowed so things go quickly.

Once the installation is complete, remove the USB drive, and reformat the disk to exFAT so you can move the deposit CLI tool onto the USB drive. You may also want to drop a text file into the USB drive with your withdrawal address to make the next step easier.

Finally, re-insert the USB drive into the NUC and move the deposit CLI tool to your desktop.

Now, run the binary file in a terminal window on your Linux desktop by using the below command (easier if you have your withdrawal address handy for a copy/paste!)

```console
sudo ./deposit new-mnemonic --num_validators {#_Validators} --chain mainnet --eth1_withdrawal_address {YourWithdrawalAddress}
```

Replace {#_Validators} with the number of validators you want to run (32ETH per), and {YourWithdrawalAddress} with an Ethereum address you control.

*NOTE: Once set, the withdrawal address **CANNOT** be changed, so be ABSOLUTELY SURE that it is an address you control the private keys for (or it's a multisig and you control the private keys to the underlying wallets) and correctly specified. For example: --eth1_withdrawal_address 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045*

**DO NOT** set the withdrawal address to a central exchange wallet or account. This MUST be an EOA or smart contract wallet, as ETH is not "transferred" but rather "generated" in the wallet via a state change, and that doesn't play nicely with Coinbase/Kraken/etc.

Once you execute the above steps, confirm your withdrawal address within the generated files, and provide your language preferences. You will then be asked to create the validator keystore password. Note this password on the variables document. You will need this later to import the validator(s) into the Consensus Client.

Next, a seed phrase (mnemonic) will be generated. Back it up somewhere safe. This is **CRITICAL**. You will need this to add additional validators or to regenerate keys if lost. IF YOU LOSE THIS MNEMONIC, YOU MAY LOSE ACCESS TO THE VALIDATOR! *Not your keys, not your coins.*

Once you have confirmed your mnemonic your validator(s) will be created. The following files will be generated and placed on your desktop.

- The deposit_data-[timestamp].json file contains the public key(s) for the validator(s) and information about the staking deposit. This file will be used to complete the ETH staking deposit process later in this guide. **This is where you can triple check the withdrawal address**
- The keystore-[..].json files contain the encrypted validator signing key. There is one keystore file per validator that you are funding. These will be imported into the Consensus Client for use during validation operations.
- If you lose or accidentally delete the files it is possible to regenerate them using the Staking Deposit CLI tool and your mnemonic via the existing-mnemonic command (see [here](https://github.com/ethereum/staking-deposit-cli#commands)).

Now that you have generated the deposit data, keystore file(s), validator password, and the mnemonic, we can begin setting up the node. You should now copy the generated deposit and keystore files back onto your USB drive. We'll need them later on.

Note: there are no other steps in this process that require you to enter or view your mnemonic phrase, so the air-gapped portion of this process is completed. You can now plug in the Ethernet cord.

### Step 2 Install Linux Server

Navigate to [ubuntu.com](https://ubuntu.com/download/server), download the latest LTS copy of Ubuntu Server (as of 12.15.23, *22.04.3 LTS*). In addition, download and install the [Etcher tool](https://www.balena.io/etcher) which will allow you to flash the operating system onto the USB drive. Then, run the Etcher tool to flash the USB drive with Ubuntu Server.

Once that's complete, pop the USB drive into your NUC, and restart it - also connect it to Ethernet if you haven't already. Upon restart, hold fn+F10 in order to boot from USB. Follow the installation instructions, making sure to select the following settings:

- When setting up hard drive settings, uncheck the LVM box else the full HD cannot be used
- You should make sure no software is downloaded or installed aside from OpenSSH
- **Do not** select "minimum" when installing the software, you will need the items downloaded and installed in the normal process
- Name your device whatever you like - and note this on your variable document
- Create a user when prompted to do so, and set a password for that user that's sufficiently complex - note this on your variable document

Once this process is complete, you should be presented with a terminal window on screen. Likely, you will need to enter your password to gain access to the server.

Next, update the server by running the following commands:

```console
sudo apt -y update && sudo apt -y upgrade && sudo apt dist-upgrade && sudo apt autoremove
sudo reboot
```

After rebooting:

```console
df -h
```

That last command is used to ensure that the expected amount of free space on your SSD is available. If this value is less than 75% of the full size of the drive, something went wrong (likely the LVM checkbox during Linux installation), and you'll need to start this step over.

### Step 3 Secure the Server

After the updates and restart complete, it's time to change some security settings.

#### Modify the Default SSH Port

Port 22 is the default SSH port and a common attack vector. Change the SSH port to avoid this.

Choose a port number between 1024–49151 and run the following command to check is not already in use:

```console
sudo ss -tulpn | grep ':{YourSSHPortNumber}'
```

A blank response indicates not in use, a red text response indicates it is in use: try a different port.

If confirmed available, modify the default SSH port number by updating your server’s SSH config. Open the config file with the following command:

```console
sudo nano /etc/ssh/sshd_config
```

Find the line Port 22 in the file. Remove the # and change the value to your chosen port. Note this port number on the variables document as you'll need it for LAN access (we're almost ready to do the rest from your laptop!)

Press CTRL + X then Y then ENTER to save and exit.

Restart the SSH service to reflect the changes.

```console
sudo systemctl restart ssh
```

#### Configure the Firewall

Install UFW:

```console
sudo apt install ufw
```

Next, apply UFW defaults:

```console
sudo ufw default deny incoming && sudo ufw default allow outgoing
```

Next, we'll need to create some custom rules to allow the requisite network activity/connections

Allow Custom SSH Port:

```console
sudo ufw allow {YourSSHPortNumber}/tcp
```

Deny Default SSH Port:

```console
sudo ufw deny 22/tcp
```

Allow Execution Client Port 30303:

```console
sudo ufw allow 30303
```

*Note that if the --port and --discovery.port flags are used in the Geth configuration file in step 7, you will need to ensure the ports used are allowed as described above.*

Allow Prysm:

```console
sudo ufw allow 13000/tcp && sudo ufw allow 12000/udp
```

With settings imported, enable the firewall by running:

```console
sudo ufw enable
```

Then run the following command to see a list of ports enabled/disabled:

```console
sudo ufw status numbered
```

Finally, run the following command to get your local IP:

```console
hostname -I
```

Note this on your variables document.

**WITHOUT** disconnecting from the Node, head over to your laptop (or whichever LAN device you plan on accessing the Node from), and attempt to connect. Open a terminal window and input the following command to edit your hosts file so you can refer to the Node by the name you set it as in addition to its IP:

```console
sudo nano /etc/hosts
```

When prompted, enter your password. Now, above the final `::1 localhost line`, create a new line, and add the local IP of your node *(see: variables)*, then a few spaces so you're aligned with the localhost text, and then enter the name of the Node you used above *(see: variables)*.

Now, lets test to see if you can SSH into your Node. Simply open a new terminal window, and enter the following command, subbing in the name of the Node, user, and the SSH port *(see: variables)*.

```console
ssh {yourusername}@{node_name OR node_IP} -p {YourSSHPortNumber}
```

Enter your password when prompted. If you are able to log in and see {user}@{node_name}, you're set! Once you see this, you can disconnect the Node from the monitor and keyboard, and can preform the remainder of tasks from any laptop or computer on the same LAN using the command above to SSH in. The Node **only** needs to remain connected to power and ethernet (powered via UPS if possible).

#### Configure Fail2Ban

Fail2Ban is an intrusion-prevention program that scans log files and and bans IPs that show malicious activity. If a certain number of failed logins are detected from a specific IP address (within a specified amount of time), that IP address is blocked. This service provides basic protection against brute-force attacks, and can be configured to ignore local IPs.

Install fail2ban, and enable and start the service:

```console
sudo apt install -y fail2ban && sudo systemctl enable fail2ban
```

Create the configuration file for the service:

```console
sudo nano /etc/fail2ban/jail.local
```

Then, paste the following configuration into the file:

```console
[sshd]
enabled = true
port = {your SSH port}
filter = sshd
logpath = /var/log/auth.log
maxretry = 4
# whitelisted IP addresses
ignoreip = 192.168.1.0/24 127.0.0.1/8
```

NOTE: The inclusion of ignoreip = 192.168.1.0/24 127.0.0.1/8 is to allow local IPs to connect (and potentially get passwords wrong) without being blocked.

Press CTRL + X then Y then ENTER to save and exit.

Reload systemd to reflect the changes and start the service. Check the status to make sure it’s running correctly:

```console
sudo systemctl daemon-reload
sudo systemctl start fail2ban
sudo systemctl status fail2ban
```

If it says "active (running)" in green text, you've done it! Press Q to quit (this will not effect the fail2ban service)

#### Disable Root Access

It is best practice to not log in as root in order to maintain security and follow the principle of least-privilege.

First, check to ensure another user besides root can run the sudo command (if you've gotten this far, this is just a double check step). Let's first check sudo access:

```console
sudo -l
```

If you see the text "User {your-username} may run the following commands on {device-name}: (ALL:ALL) ALL" you have sudo privileges with your current user.

Now, lock the root account:

```console
sudo passwd -l root
```

You should see the text "passwd: password expiry information changed."

If for any reason you need to unlock the root account:

```console
sudo passwd -u root
```

### Step 4 Configure Port Forwarding

From your laptop (or whichever device on the local network you plan on accessing the Node from), log into your router to edit the port forwarding settings. While access is different for each network set up and router, usually you can access your router at 192.168.1.1 or a similar local IP address. Occasionally, instructions can be found on the router itself.

Once you've logged in to your router, edit the port forwarding settings for your Node such that port 30303 is forwarded to port 30303 for both UDP and TCP protocols.

This is the same port we allowed above in the *Secure the Server* step - port forwarding 30303 will make it easier for the execution client (Geth) to find suitable peers. Failure to do some may result in sub optimal syncing.

If the --port and --discovery.port flags are used in the Geth configuration file in step 7, you will need to ensure the ports used are forwarded as described above.

### Step 5 Configure Timekeeping

Running validators against a blockchain requires accurate timekeeping in order to ensure proper synchronization with the network. Ubuntu has time synchronization built in and activated by default using timedatectl.

Verify this system is running:

```console
timedatectl
```

In the returning dialogue, it should show `NTP service: active`. If for some reason it is not, run the following command:

```console
sudo timedatectl set-ntp on
```

### Step 6 Generate Client Auth Secret

On the server, communication between the Execution and Consensus clients is secured using a JSON Web Token (JWT) authentication scheme. The JWT is represented by a file that contains a randomly generated 32-byte hex string. The Execution and Consensus clients each make use of the file for message authentication.

First, create a directory to store this file:

```console
sudo mkdir -p /var/lib/jwtsecret
```

Then, generate the JWT file using openssl:

```console
openssl rand -hex 32 | sudo tee /var/lib/jwtsecret/jwt.hex > /dev/null
```

Finally, check that the file was created as expected:

```console
sudo nano /var/lib/jwtsecret/jwt.hex
```

Press CTRL+X to exit

### Step 7 Configure Geth

Time to install Geth! All commands provided below are based on the 1.13.8 version of Geth (current as of 12.22.23), but should be adjusted based on whatever the latest version of Geth is [here](https://geth.ethereum.org/downloads) - simply right click and copy the URL on the 'FOR LINUX' box. Note that MANY commands below will need to update if this version is updated.

Curl the Geth build from the above link:

```console
cd ~
curl -LO https://gethstore.blob.core.windows.net/builds/geth-linux-amd64-1.13.8-b20b4a71.tar.gz
```

Extract the files from the archive and copy to the /usr/local/bin directory. The Geth service will run it from there. Modify the file name to match the downloaded version:

```console
tar xvf geth-linux-amd64-1.13.8-b20b4a71.tar.gz
cd geth-linux-amd64-1.13.8-b20b4a71
sudo cp geth /usr/local/bin
```

Clean up the files. Modify the file name to match the downloaded version:

```console
cd ~
rm geth-linux-amd64-1.13.8-b20b4a71.tar.gz
rm -r geth-linux-amd64-1.13.8-b20b4a71
```

Geth will be configured to run as a background service. Create an account for the service to run under. This type of account can’t log into the server:

```console
sudo useradd --no-create-home --shell /bin/false geth
```

Create the data directory. This is required for storing the Ethereum blockchain data:

```console
sudo mkdir -p /var/lib/geth
```

Set directory permissions. The Geth user account needs permission to modify the data directory:

```console
sudo chown -R geth:geth /var/lib/geth
```

Create a systemd service config file to configure the service:

```console
sudo nano /etc/systemd/system/geth.service
```

Then, paste the following configuration into the file:

```console
[Unit]
Description=geth Execution Client (Mainnet)
After=network.target
Wants=network.target
[Service]
User=geth
Group=geth
Type=simple
Restart=always
RestartSec=5
TimeoutStopSec=600
ExecStart=/usr/local/bin/geth \
  --mainnet \
  --datadir /var/lib/geth \
  --authrpc.jwtsecret /var/lib/jwtsecret/jwt.hex \
  --db.engine pebble
[Install]
WantedBy=default.target
```

NOTE: The inclusion of TimeoutStopSec=600 is to allow the Geth service sufficient time to write cached data to disk on ***clean*** shutdown.

Press CTRL + X then Y then ENTER to save and exit.

Reload systemd to reflect the changes and start the service. Check the status to make sure it’s running correctly:

```console
sudo systemctl daemon-reload
sudo systemctl start geth
sudo systemctl status geth
```

If it says "active (running)" in green text, you've done it! Press Q to quit (this will not effect the Geth service)

The sync will begin immediately. Use the journal output to follow the progress or check for errors by running the following command.

```console
sudo journalctl -fu geth
```

Press CTRL+ C to exit (will not affect the Geth service).

Next, enable the Geth service to automatically start on reboot:

```console
sudo systemctl enable geth
```

Finally, stop and start geth so it's using all the latest config information:

```console
sudo systemctl stop geth
sudo systemctl start geth
```

Now that Geth is all set up, you can run the Geth attach command, and check things like sync status as well as connected peers.

First, attach the Geth console:

```console
sudo geth attach /var/lib/geth/geth.ipc
```

Now, you can check the sync status, **but this won't be working until after we install Prysm** (see steps 7-9):

```console
eth.syncing
```

You can also check the count of connected peers by running:

```console
net.peerCount
```

After running Geth for ~10 or so minutes, check the peer count to ensure it's greater than 0.

### Step 8 Install Prysm

The Prysm Consensus Client is made up of two binaries that provide the functionality of the beacon node and validator, respectively. This step will download and prepare the Prysm binaries.

Time to install Prysm! All commands provided below are based on the 4.1.1 version of Prysm (current as of 12.15.23), but should be adjusted based on whatever the latest version of Prysm is [here](https://github.com/prysmaticlabs/prysm/releases). Note that many commands below will need to update if this version is updated.

In the Assets section (expand if necessary) copy the download links to the beacon-chain-v…-linux-amd64 file and the validator-v…-linux-amd64 file. Be sure to copy the correct links.
Download the binaries using the commands below. Modify the URL to match the copied download links:

```console
cd ~
curl -LO https://github.com/prysmaticlabs/prysm/releases/download/v4.1.1/beacon-chain-v4.1.1-linux-amd64
curl -LO https://github.com/prysmaticlabs/prysm/releases/download/v4.1.1/validator-v4.1.1-linux-amd64
```

Now, let's rename the files and make them executable and copy them to the /usr/local/bin directory. The Prysm services will run them from there. Modify the file names to match the downloaded version:

```console
mv beacon-chain-v4.1.1-linux-amd64 beacon-chain
mv validator-v4.1.1-linux-amd64 validator
```

```console
chmod +x beacon-chain
chmod +x validator
```

```console
sudo cp beacon-chain /usr/local/bin
sudo cp validator /usr/local/bin
```

Finally, clean up the files

```console
rm beacon-chain && rm validator
```

### Step 9 Configure the Beacon Node Service

Set up an account for the services to run under (note: this type of account cannot log into the server):

```console
sudo useradd --no-create-home --shell /bin/false prysmbeacon
```

Next, set up the directories and permissions for prysmbeacon:

```console
sudo mkdir -p /var/lib/prysm/beacon
sudo chown -R prysmbeacon:prysmbeacon /var/lib/prysm/beacon
```

Next, create and configure the service file:

```console
sudo nano /etc/systemd/system/prysmbeacon.service
```

And then paste the following data into the file:

```console
[Unit]
Description=Prysm Consensus Client BN (Mainnet)
Wants=network-online.target
After=network-online.target
[Service]
User=prysmbeacon
Group=prysmbeacon
Type=simple
Restart=always
RestartSec=5
ExecStart=/usr/local/bin/beacon-chain \
  --mainnet \
  --datadir=/var/lib/prysm/beacon \
  --execution-endpoint=http://127.0.0.1:8551 \
  --jwt-secret=/var/lib/jwtsecret/jwt.hex \
  --suggested-fee-recipient={FeeRecipientAddress} \
  --checkpoint-sync-url={CheckpointSyncURL} \
  --genesis-beacon-api-url={CheckpointSyncURL} \
  --accept-terms-of-use
Environment=USE_PRYSM_MODERN=true
[Install]
WantedBy=multi-user.target
```

**Make sure** to replace {FeeRecipientAddress} with the address you'd like to receive the validator tip fees.

**Make sure** to replace {CheckpointSyncURL} *(x2)* with a valid checkpoint sync URL [see here for more information](https://eth-clients.github.io/checkpoint-sync-endpoints/) - be sure to select a Mainnet endpoint.

Press CTRL + X then Y then ENTER to save and exit.

Reload systemd to reflect the changes and start the service. Check the status to make sure it’s running correctly:

```console
sudo systemctl daemon-reload
sudo systemctl start prysmbeacon
sudo systemctl status prysmbeacon
```

If it says "active (running)" in green text, you've done it! Press Q to quit (this will not effect the PrysmBeacon service) - the sync has already begun.

Use the journal output to follow the progress or check for errors by running the following command:

```console
sudo journalctl -fu prysmbeacon
```

Finally, enable the service to automatically start on reboot:

```console
sudo systemctl enable prysmbeacon
```

### Step 10 Configure the Validator Service

Set up an account for the services to run under (note: this type of account cannot log into the server):

```console
sudo useradd --no-create-home --shell /bin/false prysmvalidator
```

Create a directory to store the validator data:

```console
sudo mkdir -p /var/lib/prysm/validator
```

Next, set up the directories and permissions for prysmbeacon:

```console
sudo chown -R prysmvalidator:prysmvalidator /var/lib/prysm/validator
```

Next, create and configure the service file by running:

```console
sudo nano /etc/systemd/system/prysmvalidator.service
```

And then paste the following data into the file:

```console
[Unit]
Description=Prysm Consensus Client VC (Mainnet)
Wants=network-online.target
After=network-online.target
[Service]
User=prysmvalidator
Group=prysmvalidator
Type=simple
Restart=always
RestartSec=5
ExecStart=/usr/local/bin/validator \
  --datadir=/var/lib/prysm/validator \
  --wallet-dir=/var/lib/prysm/validator \
  --wallet-password-file=/var/lib/prysm/validator/password.txt \
  --suggested-fee-recipient={FeeRecipientAddress} \
  --graffiti="{yourgraffiti}" \
  --accept-terms-of-use
[Install]
WantedBy=multi-user.target
```

**Make sure** to replace {FeeRecipientAddress} with the address you'd like to receive the validator tip fees.

**Make sure** to replace {yourgraffiti} with your own graffiti string (max 32 bytes). (e.g. --graffiti="Endaoment.org")

Press CTRL + X then Y then ENTER to save and exit.

Note that you can check the byte count by running a simple python command from terminal on your laptop:

```console
python3
>> len("{yourgraffiti}".encode())
```

If the result is 32 or less, you're in the clear.

Reload systemd to reflect the changes and start the service. Check the status to make sure it’s running correctly:

```console
sudo systemctl daemon-reload
sudo systemctl start prysmvalidator
sudo systemctl status prysmvalidator
```

If it says "active (running)" in green text, you've done it! Press Q to quit (this will not effect the PrysmValidator service) - the sync has already begun.

Use the journal output to follow the progress or check for errors by running the following command:

```console
sudo journalctl -fu prysmvalidator
```

Finally, enable the service to automatically start on reboot:

```console
sudo systemctl enable prysmvalidator
```

Now that the beacon-chain, validator, and execution client software is all set up, you should run the following Geth attach commands to check sync status:

First, attach the Geth console:

```console
sudo geth attach /var/lib/geth/geth.ipc
```

Now, you can check the sync status (it will work now!):

```console
>eth.syncing
```

Press CTRL + D to exit.

### Step 11 Import Validator Keys

To import the keys into Prysm, we'll need to get them onto the same machine.

#### Copy Validator Keystore File(s) to Server

Before we transfer over the Validator Keystore file(s), we'll need to create a place to store them:

```console
sudo mkdir -p $HOME/staking-deposit-cli/validator_keys
```

Next, ensure your user has control of that folder:

```console
sudo chown -R {yourusername}:{yourusername} $HOME/staking-deposit-cli/validator_keys
```

Now, plug the USB into your Node from Step 1 (remember Step 1?).

Back in terminal, check to see if the drive is recognized:

```console
sudo fdisk -l
```

This will list all available disks and partitions. You should see the USB drive listed as a block device, such as /dev/sdb or /dev/sdc, and specific drives underneath. Look for your USB drive and note its code (e.g. sdb1 or sdc1).

Create a mount point for the USB drive by running the following command:

```console
sudo mkdir /mnt/usb
```

Then, mount the USB drive to the mount point, replacing sdb1:

```console
sudo mount /dev/{sdb1} /mnt/usb
```

Check that the USB drive is connected by looking at all mounted drives:

```console
df -h
```

Now, it's time to copy the files from the USB to the proper folders within the Node. First, let's get a list of all files by running:

```console
ls /mnt/usb
```

This should show something like the following

>deposit_data-1682896118.json
keystore-m_12381_3600_0_0_0-1682896115.json

Note that while you will only ever have 1 deposit file (regardless of the amount of validators), you will have 1 keystore file for each validator you are setting up on the Node. You only need to move the keystore file(s) to the validator_keys folder.

Now that we have the file names, we issue a command to copy those files from /mnt/usb to $HOME/staking-deposit-cli/validator_keys:

```console
cp /mnt/usb/{keystore-filename.json} $HOME/staking-deposit-cli/validator_keys/
```

If you have more than 1 validator key, you will need to rerun the above command once for each. **BE SURE TO ONLY HAVE 1 COPY OF EACH VALIDATOR KEY**.

Before unmounting the USB, let's verify that the files were placed into the folder correctly by running:

```console
ls $HOME/staking-deposit-cli/validator_keys/
```

If you see 1 copy of each validator key you intended to move, you're all set!

Now, unmount the USB:

```console
sudo umount /mnt/usb
```

#### Import the Validator Keystore Files into Prysm

**REMEMBER: If you import the same keystore twice OR run the same keystore on multiple nodes at the same time YOU WILL GET [SLASHED](https://www.blocknative.com/blog/an-ethereum-stakers-guide-to-slashing-other-penalties)!**

Now we will run the validator import process. You will need to provide the directory where the generated keystore-[..].json files are located. E.g. $HOME/staking-deposit-cli/validator_keys (as determined above in this step)

```console
sudo /usr/local/bin/validator accounts import --keys-dir=$HOME/staking-deposit-cli/validator_keys --wallet-dir=/var/lib/prysm/validator --mainnet
```

You will then be presented with a terms of use which you will need to accept in order to continue.

Following your acceptance, you'll be prompted to create a wallet password. Note that this is a **different** password than the validator password set in step 1 when generating the keystore files. This password will be used by Prysm to decrypt the validator files. Note this password on the variables document.

After setting your wallet password, you'll be asked to enter the validator keystore password, this is the one referenced above and created during step 1. Once this password is entered, all validator keystore file(s) will be imported.

#### Create a Wallet Password File

Create a file to store the wallet password so the Prysm validator service (set up below) can access the wallet without you having to supply the password:

```console
sudo nano /var/lib/prysm/validator/password.txt
```

This will create a new text file and open a nano text editor. Type your password you just created for your validator wallet into the the file.

Press CTRL + X then Y then ENTER to save and exit.

Let's now check that Prysm can see the password:

```console
sudo systemctl status prysmvalidator
```

Before continuing to the deposit step, let's do one more permissions check:

```console
sudo chown -R prysmvalidator:prysmvalidator /var/lib/prysm/validator && sudo chown -R {yourusername}:{yourusername} /var/lib/prysm/validator
sudo systemctl daemon-reload
```

### Step 12 Fund the Validators

Now that the Consensus Client is up and running, to actually begin staking on the Ethereum network you will need to deposit ETH to fund your validators.

**Note: DO NOT continue until your execution and consensus clients are fully synced. If they have not and your validator(s) become active on the network, you would be subject to inactivity penalties. You can determine sync status by checking the status of the Beacon Chain or through attaching the Geth console, both methods are described above.**

With the deposit file in hand and an EOA with 32ETH per validator + some spare ETH for gas, head to the [Ethereum Launchpad](https://launchpad.ethereum.org/)

Click on Become a Validator, click through the warning steps and continue through the screens until you get to the Generate Key Pairs section. Select the number of validators you are going to run. Choose a value that matches the number of validators you created in Step 1.

Scroll down, check the box if you agree, and click Continue.

You will be asked to upload the deposit_data-[timestamp].json file. You generated this file in Step 1. *(Note: There are no security concerns copying the file or having access to it on a public computer)*. Double check that inside the file the withdrawal address is set correctly. When satisfied, browse or drag the file to upload and click continue.

Connect your wallet. Choose MetaMask (or one of the other supported wallets), log in, select the account where you have your ETH and click Continue.

Your MetaMask balance will be displayed. The site will allow you to continue only if you have selected Mainnet and you have a sufficient ETH balance.

A summary shows the number of validators and total amount of ETH required. Tick the boxes if you agree and click continue.

If you are ready to deposit click on `Initiate All Transactions`.

This will pop open MetaMask (or one of the other supported wallets) where you can confirm and broadcast each transaction.

Once all the transactions have successfully completed you are done! WOOOOOOO! Congratulations you have deposited your stake!

#### Check the Status of Your Validator Deposits

Newly added validators can take a while to activate. You can check the status of your keys with these steps:

1. Copy your wallet address used to make the deposit
2. Go to [Beaconcha.in](https://beaconcha.in/)
3. Search for your key(s) using your wallet address

Digging into a specific validator we can see a `Status` section that provides an activation estimate time for each validator.

That’s it. You now have a functioning Execution and Consensus client and the staking deposit done. Once your deposit is active you will automatically begin staking and earning rewards.

Probably a good time to *touch grass*.

![SolarNode](.imgs/SolarNode.jpg)
