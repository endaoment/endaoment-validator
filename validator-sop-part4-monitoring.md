# Validator SOP Part 4: Monitoring and Dashboard Creation

## Table of Contents

- [Step 1 Adjust Firewall](#step-1-adjust-firewall)
- [Step 2 Install Prerequisite Software](#step-2-install-prerequisite-software)
- [Step 3 Install Reporting Software](#step-3-install-reporting-software)
  - [Prometheus](#prometheus)
  - [Node Exporter](#node-exporter)
  - [JSON Exporter](#json-exporter)
  - [Ethereum Metrics Exporter](#ethereum-metrics-exporter)
  - [Grafana](#grafana)
- [Step 4 Configure Ethereum Clients](#step-4-configure-ethereum-clients)
- [Step 5 Configure Reporting Software](#step-5-configure-reporting-software)
  - [Configure JSON_Exporter](#configure-json_exporter)
  - [Configure Prometheus Rules](#configure-prometheus-rules)
  - [Configure Ethereum Metrics Exporter](#configure-ethereum-metrics-exporter)
- [Step 6 Configure Prometheus Jobs + Targets](#step-6-configure-prometheus-jobs--targets)
  - [Prometheus Jobs](#prometheus-jobs)
  - [Base Targets](#base-targets)
  - [Validator Public Key Targets](#validator-public-key-targets)
  - [Restart All Services](#restart-all-services)
- [Step 7 Set up Dashboard](#step-7-set-up-dashboard)

## Abstract

This document will detail the process for setting up a Grafana monitoring dashboard for an Ethereum validator. This guide assumes you followed [Validator SOP Part 1: Set Up](./validator-sop-part1-setup.md). Please note that dashboards are highly customizable, and as such small changes can be made to either the reporting software or the dashboard itself to accommodate specific use cases. This guide is written with the initial Endaoment node set up in mind, a node with five validators utilizing Geth/Prysm. While the majority of things covered by this guide do not touch the underlying services that run the validator, caution should be exercised as there are some changes that must be made to validator/beacon-chain service files.

### Step 1 Adjust Firewall

Before we can get started, we need to open ports in the UFW firewall to allow Prometheus and Grafana listening ports:

```console
sudo ufw allow 3000/tcp
sudo ufw allow 9090/tcp
```

Next, check to ensure the rules were properly applied:

```console
sudo ufw status numbered
```

### Step 2 Install Prerequisite Software

This guide will utilize the `make` utility as well as `go`, and additionally relies on the Stake Local GitHub Repository. We'll get that all set up before we start installing the reporting software.

First, let's run a quick update, ensure we can use APT via HTTPS, and ensure we have common utilities like wget installed, and ensure they are automatically updated:

```console
sudo apt-get update
sudo apt-get install apt-transport-https
sudo apt-get install software-properties-common wget
sudo apt-mark auto apt-transport-https
sudo apt-mark auto software-properties-common
sudo apt-mark auto wget
```

Install make:

```console
sudo apt-get install make
```

Check to ensure it was properly installed:

```console
make --version
```

Install go (or skip to Step 3 if you did this while setting up MEV-Boost)

```console
cd
wget https://go.dev/dl/go1.20.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.20.linux-amd64.tar.gz
sudo ln -s /usr/local/go/bin/go /usr/bin/go
```

Check to ensure it was properly installed:

```console
go version
```

Clean up installation files:

```console
rm go1.20.linux-amd64.tar.gz
```

### Step 3 Install Reporting Software

We'll now install Grafana, Prometheus, Node_Exporter and JSON_exporter software, that will all work together to generate our dashboard.

#### Prometheus

Download the latest release of Prometheus by going [here](https://prometheus.io/download/) and copying the download link for the latest linux-amd64.tar.gz file. Please be sure to replace the link below using the current version. As of 6/11/23, version 2.44.0 is current. Download the repository, extract the files, and move them to the /bin:

```console
cd ~
curl -LO https://github.com/prometheus/prometheus/releases/download/v2.44.0/prometheus-2.44.0.linux-amd64.tar.gz
tar xvf prometheus-2.44.0.linux-amd64.tar.gz
sudo cp prometheus-2.44.0.linux-amd64/prometheus /usr/local/bin/
sudo cp prometheus-2.44.0.linux-amd64/promtool /usr/local/bin/
```

Modify file names and clean up:

```console
sudo cp -r prometheus-2.44.0.linux-amd64/consoles /etc/prometheus
sudo cp -r prometheus-2.44.0.linux-amd64/console_libraries /etc/prometheus
rm prometheus-2.44.0.linux-amd64.tar.gz
rm -r prometheus-2.44.0.linux-amd64
```

Set up an account for the services to run under (note: this type of account cannot log into the server):

```console
sudo useradd --no-create-home --shell /bin/false prometheus
```

Set up the directories for prometheus:

```console
sudo mkdir -p /var/lib/prometheus
```

Create a configuration file for prometheus:

```console
sudo nano /etc/prometheus/prometheus.yml
```

Copy and paste text into this configuration file so it matches [prometheus.yml](.imgs/prometheus.yml).

Press CTRL + X then Y then ENTER to save and exit.

Set directory permissions for prometheus  to modify the directories:

```console
sudo chown -R prometheus:prometheus /etc/prometheus
sudo chown -R prometheus:prometheus /var/lib/prometheus
```

Create a systemd service config file to configure the service:

```console
sudo nano /etc/systemd/system/prometheus.service
```

Paste the following text into the configuration file:

```console
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target
[Service]
Type=simple
User=prometheus
Group=prometheus
Restart=always
RestartSec=5
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus \
  --web.console.templates=/etc/prometheus/consoles \
  --web.console.libraries=/etc/prometheus/console_libraries
[Install]
WantedBy=multi-user.target
```

Press CTRL + X then Y then ENTER to save and exit.

Reload systemd to reflect the changes and start the service. Check the status to make sure it’s running correctly:

```console
sudo systemctl daemon-reload
sudo systemctl start prometheus
sudo systemctl status prometheus
```

If it says "active (running)" in green text, you've done it! Press Q to quit (this will not effect the Prometheus service).

Use the journal output to follow the progress or check for errors by running the following command:

```console
sudo journalctl -fu prometheus
```

Finally, enable the service to automatically start on reboot:

```console
sudo systemctl enable prometheus
```

#### Node Exporter

Download the latest release of Node Explorer by going [here](https://prometheus.io/download/#node_exporter) and copying the download link for the latest linux-amd64.tar.gz file. Please be sure to replace the link below using the current version. As of 6/11/23, version 1.6.0 is current. Download the repository, extract the files, and move them to the /bin:

```console
cd ~
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.0/node_exporter-1.6.0.linux-amd64.tar.gz
tar xvf node_exporter-1.6.0.linux-amd64.tar.gz
sudo cp node_exporter-1.6.0.linux-amd64/node_exporter /usr/local/bin/
```

Clean up:

```console
rm node_exporter-1.6.0.linux-amd64.tar.gz
rm -r node_exporter-1.6.0.linux-amd64
```

Set up an account for the services to run under (note: this type of account cannot log into the server):

```console
sudo useradd --no-create-home --shell /bin/false node_exporter
```

Create a configuration file for node_exporter:

```console
sudo nano /etc/systemd/system/node_exporter.service
```

Copy and paste the following into this configuration file:

```console
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target
[Service]
User=node_exporter
Group=node_exporter
Type=simple
Restart=always
RestartSec=5
ExecStart=/usr/local/bin/node_exporter
[Install]
WantedBy=multi-user.target
```

Press CTRL + X then Y then ENTER to save and exit.

Reload systemd to reflect the changes and start the service. Check the status to make sure it’s running correctly:

```console
sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl status node_exporter
```

If it says "active (running)" in green text, you've done it! Press Q to quit (this will not effect the Node Exporter service).

Use the journal output to follow the progress or check for errors by running the following command:

```console
sudo journalctl -fu node_exporter
```

Finally, enable the service to automatically start on reboot:

```console
sudo systemctl enable node_exporter
```

#### JSON Exporter

Download the latest release of Node Explorer by going [here](https://github.com/prometheus-community/json_exporter/releases) and copying the download link for the latest linux-amd64.tar.gz file. Please be sure to replace the link below using the current version. As of 6/11/23, version 0.6.0 is current. Download the repository and move them to /git:

```console
mkdir ~/git
cd git
git clone --depth 1 --branch v0.6.0 https://github.com/prometheus-community/json_exporter.git
cd ~
```

Build json_exporter from the source code you just downloaded:

```console
cd git/json_exporter
make build
```

Copy the executable file to the /bin, and check to ensure it installed correctly (should show the current version):

```console
sudo cp json_exporter /usr/local/bin/
/usr/local/bin/json_exporter --version --help
```

Clean up time:

```console
cd ~
rm -rf ~/git/json_exporter
```

Set up an account for the services to run under (note: this type of account cannot log into the server):

```console
sudo useradd --no-create-home --shell /bin/false json_exporter
```

Create a directory and the configuration file for json_exporter:

```console
sudo mkdir /etc/json_exporter
sudo nano /etc/systemd/system/json_exporter.service
sudo chown -R json_exporter:json_exporter /etc/json_exporter
```

Copy and paste the following into this configuration file:

```console
[Unit]
Description=JSON Exporter

[Service]
Type=simple
Restart=always
RestartSec=5
User=json_exporter
ExecStart=/usr/local/bin/json_exporter --config.file /etc/json_exporter/json_exporter.yml

[Install]
WantedBy=multi-user.target
```

Press CTRL + X then Y then ENTER to save and exit.

Reload systemd to reflect the changes and start the service. Check the status to make sure it’s running correctly:

```console
sudo systemctl daemon-reload
sudo systemctl start json_exporter
sudo systemctl status json_exporter
```

It will not say "active (running)" in green text, as `'/etc/json_exporter/json_exporter.yml' does not exist`, this is expected. We will configure the YML file in step 5.

Use the journal output to follow the progress or check for errors by running the following command:

```console
sudo journalctl -fu json_exporter
```

Running this command will confirm the above, as you'll see the error.

Finally, enable the service to automatically start on reboot:

```console
sudo systemctl enable json_exporter
```

#### Ethereum Metrics Exporter

Download and build the latest version of the Ethereum Metrics Exporter, and move it to the /bin:

```console
go install github.com/ethpandaops/ethereum-metrics-exporter@latest
sudo cp ~/go/bin/ethereum-metrics-exporter /usr/local/bin
```

Set up an account for the services to run under (note: this type of account cannot log into the server):

```console
sudo useradd --no-create-home --shell /bin/false eth-metrics
```

Create a directory and the configuration file for eth_exporter:

```console
sudo mkdir -p /var/local/lib/eth-metrics /etc/eth-metrics
sudo nano /etc/systemd/system/eth-metrics.service
```

Copy and paste the following into this configuration file:

```console
[Unit]
Description=Ethereum Metrics Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=eth-metrics
Group=eth-metrics
Type=simple
Restart=always
RestartSec=5
ExecStart=/usr/local/bin/ethereum-metrics-exporter \
                --config /etc/eth-metrics/eth-metrics.yml \
                --metrics-port 9095

[Install]
WantedBy=multi-user.target
```

Press CTRL + X then Y then ENTER to save and exit.

Reload systemd to reflect the changes and start the service. Check the status to make sure it’s running correctly:

```console
sudo systemctl daemon-reload
sudo systemctl start eth-metrics
sudo systemctl status eth-metrics
```

It will not say "active (running)" in green text, as `'/etc/eth-metrics/eth-metrics.yml' does not exist`, this is expected. We will configure the YML file in step 5.

Use the journal output to follow the progress or check for errors by running the following command:

```console
sudo journalctl -fu eth-metrics
```

Running this command will confirm the above, as you'll see the error.

Finally, enable the service to automatically start on reboot:

```console
sudo systemctl enable eth-metrics
```

#### Grafana

Download the Grafana GPG key and add Grafana to the APT sources:

```console
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
```

You may get a warning about apt-key being depreciated, it is ok to ignore this warning.

Refresh the apt cache:

```console
sudo apt install grafana && sudo apt update
```

Ensure Grafana is linked to the repository:

```console
apt-cache policy grafana
```

Ensure the output looks like the below and matches the latest [version](https://grafana.com/grafana/download)

`grafana:
  Installed: 9.5.3
  Candidate: 9.5.3
  Version table:`

Note that Grafana version 9.5.3 is current as of 6/11/23.

Install Grafana:

```console
sudo apt install -y grafana
```

Start Grafana, then check the status to make sure it’s running correctly:

```console
sudo systemctl start grafana-server
sudo systemctl status grafana-server
```

If it says "active (running)" in green text, you've done it! Press Q to quit (this will not effect the Grafana service)

Use the journal output command to check for errors:

```console
sudo journalctl -fu grafana-server
```

Press CTRL+ C to exit (will not affect the Geth service).

Next, enable the Geth service to automatically start on reboot:

```console
sudo systemctl enable grafana-server
```

Now that you have Grafana up and running, you can navigate to `https://{yourserverIP}:3000` to access the Grafana interface. You should see a login screen. Enter `admin` for both the username and password. You'll be immediately prompted to change your password, which you should, and note on your variables document.

Time to configure the Grafana data source! Navigate to `https://{yourserverIP}:3000/datasources`and click on `Add data source`. Choose Prometheus, enter `http://localhost:9090` for the URL, and then click on Save and Test.

If you see `Successfully queried the Prometheus API`, you're all set!

### Step 4 Configure Ethereum Clients

Each consensus and execution client must have the appropriate metrics services and APIs enabled and accessible to the reporting software. As a reminder, the below instructions assume Prysm/Geth.

Adjust your Prysm Beacon service file:

```console
sudo nano /etc/systemd/system/prysmbeacon.service
```

Add the following flag at the bottom of the `ExecStart` list, note that you may need to add a`\` at the end of the previous line, depending on how your file is formatted.

`--monitoring-host 0.0.0.0`

Press CTRL + X then Y then ENTER to save and exit.

Adjust your Prysm Validator service file:

```console
sudo nano /etc/systemd/system/prysmvalidator.service
```

Add the following flag at the bottom of the `ExecStart` list, note that you may need to add a`\` at the end of the previous line, depending on how your file is formatted.

`--monitoring-host 0.0.0.0`

Press CTRL + X then Y then ENTER to save and exit.

Adjust your Geth service file:

```console
sudo nano /etc/systemd/system/geth.service
```

Add the following flag at the bottom of the `ExecStart` list, note that you may need to add a`\` at the end of the previous line, depending on how your file is formatted.

`--metrics \
--http \
--http.api net,web3,eth,txpool`

Press CTRL + X then Y then ENTER to save and exit.

Finally, restart everything you just adjusted. Please note that if the validator is attesting, you should first ensure there are no upcoming attestations or proposals, as there will be ~30 seconds of downtime.

```console
sudo systemctl daemon-reload
sudo systemctl restart geth
sudo systemctl restart prysmbeacon
sudo systemctl restart prysmvalidator
```

You should then check the status of each of the services you just restarted to ensure that changing the configuration files haven't messed with anything:

```console
sudo systemctl status geth
sudo systemctl status prysmbeacon
sudo systemctl status prysmvalidator
```

After reviewing each one, press CTRL + C to exit, which will trigger the next status to show.

### Step 5 Configure Reporting Software

With all software installed and your Ethereum clients configured, we can now configure all the software to talk to each other properly. Remember those errors from before? Now we fix.

#### Configure JSON_Exporter

Edit the configuration file for json_exporter:

```console
sudo nano /etc/json_exporter/json_exporter.yml
```

Copy and paste the contents of [this file](.imgs/json_exporter.yml) into that file. Then press CTRL + X followed by Y to save.

#### Configure Prometheus Rules

Edit the rules.d file for prometheus:

```console
sudo mkdir -p /etc/prometheus/rules.d/
sudo nano /etc/prometheus/rules.d/stakelocal_rules.yml
```

Copy and paste the contents of [this file](.imgs/stakelocal_rules.yml) into that file. Then press CTRL + X followed by Y to save.

#### Configure Ethereum Metrics Exporter

Edit the configuration file for eth-metrics:

```console
sudo nano /etc/eth-metrics/eth-metrics.yml
```

Copy and paste the following into that file:

```console
consensus:
  enabled: true
  url: "<http://localhost:3500>"
  name: "Prysm Beacon"
execution:
  enabled: true
  url: "<http://localhost:8545>"
  name: “Geth”
  modules:
    - "eth"
    - "net"
    - "web3"
    - "txpool"
pair:
  enabled: true
```

Then press CTRL + X followed by Y to save.

### Step 6 Configure Prometheus Jobs + Targets

A Prometheus `job` represents a set of rules for processing metrics from similar data sources/targets. A Prometheus target is a single data source from which Prometheus should collect and process data using the rules of a specific job. Prometheus jobs are collections of targets for which the same rules are applied. Here, we'll be setting up the Prometheus jobs that feed data to the dashboard.

#### Prometheus Jobs

Since we've already edited the Prometheus configuration file, we simply need to check that the rules are being read:

```console
sudo promtool check config /etc/prometheus/prometheus.yml
```

While there will be a number of warnings (expected), you should see `SUCCESS: 46 rules found` at the bottom of the returned text.

#### Base Targets

Before we can do specific configuring, we will need to copy in an archive of all target configuration files. To save time, all 24 files come pre-edited as needed, you're welcome.

Create the folder to store things in:

```console
sudo mkdir -p /etc/prometheus/files_sd
```

In order to copy files from your local environment to your linux server (which you can SSH into), you'll need to use the scp command **from your laptop in a new terminal window**. Note that the specifics of this command may be different depending on where you've stored this repository (endaoment/endaoment-operations), and that the command should be run **from a new terminal window** on your laptop or PC.

Copy the folder and all files within to your node:

```console
scp -r -P {YourSSHPortNumber} {repository/location}/endaoment/endaoment-operations/.imgs/stakelocal/ {yourusername}@{node_name OR node_IP}:~/files_sd
```

Then, copy the files_sd folder to the correct location:

```console
sudo mkdir /etc/prometheus/files_sd/stakelocal/
sudo mv ~/files_sd/* /etc/prometheus/files_sd/stakelocal/
```

Finally, check to ensure things were copied correctly (you should see a folder called stakelocal):

```console
ls /etc/prometheus/files_sd/
```

Clean up:

```console
rm -rf files_sd
```

#### Validator Public Key Targets

Edit the validator configuration file to include a list of coma separated public keys of your validator(s):

```console
sudo nano /etc/prometheus/files_sd/stakelocal/validators.yml
```

Copy and paste the following into that file:

```console
    - targets: [ {validators} ]
      labels:
        network: 'Mainnet'
        host: 'Default Host'
        service: 'Prysm Beacon'
        group: 'Prysm/Geth'
        instance: '127.0.0.1:3500'
        explorer: 'beaconcha.in'
```

Make sure to replace {validators} with a comma separated list of your validator public keys (discoverable via Beaconcha.in if unknown) in the style of `-targets: [ 0x123, 0x456, ... 0xXYZ ]`.

If the consensus client being queried is not on the local host or uses a non-standard port, update those on the `instance` line.

Then press CTRL + X followed by Y to save.

#### Restart All Services

We just made a lot of changes to many reporting services and their configuration files, let's now restart them and check that they've started up correctly.

Restart all reporting services:

```console
sudo systemctl daemon-reload
sudo systemctl restart prometheus grafana-server node_exporter json_exporter eth-metrics
```

Now, check the status of each of these services (hold return to move down through the statuses called all at once):

```console
sudo systemctl status prometheus grafana-server node_exporter json_exporter eth-metrics
```

If you need additional detail, you can check the logs:

```console
sudo journalctl -fu prometheus
sudo journalctl -fu grafana-server
sudo journalctl -fu node_exporter
sudo journalctl -fu json_exporter
sudo journalctl -fu eth-metrics
```

### Step 7 Set up Dashboard

Log into your Grafana instance ({YourIp}:3000) using the password you set up earlier. In the menu, click on Dashboard > New > Import. Copy and paste [this file](.imgs/grafana-dashboard.json) into the `Import via panel json` area and click `Load`. On the next screen, give your dashboard a unique name, feel free to change the UID, and click `Import`.

⚠️ **You're going to see a lot of errors, that is expected!** ⚠️

These errors are because we need to update the data source for all panels you just imported. Head back to the data sources menu (Home > Connection > Data sources) and click on Prometheus. From here, click on Dashboards, and click `Build a Dashboard` (we will delete this later). Click `Import dashboard` and use the import code `3662`, then click load, select the prometheus data source, then import.

Navigate to that dashboard (it should automatically open), click the gear to head to settings, and then click on JSON Model on the left menu. Copy the UID contained in line 19. This is your data source's UUID!

After ensuring you have the UID copied, click on General, scroll to the bottom, and click `Delete Dashboard`.

Armed with the correct UID, let's fix the validator dashboard. Click on Dashboards at the top of the screen, and navigate back to your dashboard. From there, click the gear to head to settings, and then click on JSON Model. Press CTRL + F and click the down arrow to prepare a find and replace. Paste your data sources UID into the Replace section, and `bdaeb540-4cdb-4740-95d4-2fabfb32fb5b` into the Find section (note this is the UID in line 37). Finally, click the replace all button to update your dashboard. To save, FIRST click `save changes` at the bottom and THEN `save dashboard` at the top of the screen, and finally click `save`.

IT'S TIME! Head back to your dashboard and witness a thing of beauty. Well done kid.
