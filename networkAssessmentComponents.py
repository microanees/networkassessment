# Copyright (c) 2016, Arista Networks, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
#   Neither the name of Arista Networks nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL ARISTA NETWORKS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#
# Author = Anees Mohammed
#

import networkx as nx
import pyeapi
import re


class Commands(object):

    """
        Commands Library used by all the Use Cases (BGP & MLAG)
    """

    def __init__(self, switch, username, password):
        self.node = pyeapi.connect(transport="https",
                                   host=switch,
                                   username=username,
                                   password=password,
                                   port=None)

    def getlldpinfo(self):
        eos_command = "show lldp neighbors"
        response = self.node.execute([eos_command])
        neighbors = response["result"][0]["lldpNeighbors"]
        return neighbors

    def getspeed(self, interface_name):
        eos_command = "show interfaces status"
        response = self.node.execute([eos_command])
        speed = (response["result"][0]["interfaceStatuses"]
                         [interface_name]["bandwidth"])
        return (speed/1000000000)

    def hostname(self):
        eos_command = "show hostname"
        response = self.node.execute([eos_command])
        host_name = str(response["result"][0]["fqdn"])
        return host_name

    def runningconfig(self):
        eos_command = ["enable", "show running-config"]
        response = self.node.execute(eos_command)
        running_config = response["result"][1]["cmds"]
        return running_config

    def bgpsummary(self):
        eos_command = "show ip bgp summary vrf all"
        response = self.node.execute([eos_command])
        bgp_summary = response["result"][0]["vrfs"]
        return bgp_summary

    def mlag(self):
        eos_command = "show mlag"
        response = self.node.execute([eos_command])
        sh_mlag = response["result"][0]
        return sh_mlag


class DefineEapiVariables(object):

    """
        Parent Class for all the Use Cases (BGP & MLAG)
    """
    def __init__(self, devices, username, password):
        self.devices = devices
        self.username = username
        self.password = password
        self.hostnames = {}
        self.errors = {}


class EapiAccess(DefineEapiVariables):

    def validate_switches(self):
        """
        This MUST be the first method used by tools script
        This verifies the eAPI connectivity to all the switches
            listed in the switches.txt file
        Save the IP address of the switches reachable by eAPI in hostnames
            dictionary
        Save the IP address of the switches not reachable in errors
            dictionary

        ALl the other use cases (BGP and MLAG) uses the IP addresses
            that are reachable
        """
        for switch in self.devices:
            try:
                eos_commands = Commands(switch, self.username, self.password)
                self.hostnames[switch] = eos_commands.hostname()

            except pyeapi.eapilib.ConnectionError:
                self.errors[switch] = "ConnectionError: unable to connect " \
                                        "to eAPI"

            except pyeapi.eapilib.CommandError:
                self.errors[switch] = "CommandError: Check your EOS command " \
                                        "syntax"

    def get_hostnames(self):
        return self.hostnames

    def get_errors(self):
        return self.errors


class Plotter(DefineEapiVariables):

    def draw(self):
        """
        networkx script examples
        https://www.udacity.com/wiki/creating-network-graphs-with-python
        """
        # Define Graph

        G = nx.MultiGraph()

        # Draw Edges

        for switch in self.devices:
            try:
                eos_commands = Commands(switch, self.username, self.password)
                lldpinfo = eos_commands.getlldpinfo()
                for neighbor in lldpinfo:
                    print "Scanning details for neighbor %s" \
                            % (neighbor["neighborDevice"])
                    localport = neighbor["port"]
                    remoteport = neighbor["neighborPort"]
                    speedint = eos_commands.getspeed(localport)

                    edge_key = (neighbor["neighborDevice"] +
                                "_" +
                                self.devices[switch] +
                                "_" +
                                remoteport +
                                localport)

                    if (G.has_edge(neighbor["neighborDevice"],
                            self.devices[switch], key=edge_key) == False):
                        G.add_edge(self.devices[switch],
                                   neighbor["neighborDevice"],
                                   port=localport,
                                   neighborPort=remoteport,
                                   speed=speedint,
                                   key=edge_key)

            except pyeapi.eapilib.ConnectionError:
                self.errors[switch] = "ConnectionError: unable to connect" \
                                        " to eAPI"

            except pyeapi.eapilib.CommandError:
                self.errors[switch] = "CommandError: Check your EOS command" \
                                        " syntax"

        # Create Network Graph

        print "Creating the network diagram file network.graphml"
        nx.write_graphml(G, 'network.graphml')


class BgpValidate(DefineEapiVariables):

    def __init__(self, devices, username, password):
        super(BgpValidate, self).__init__(devices, username, password)
        self.bgp_status = {}

    @staticmethod
    def is_ipv4_ipv6(neighbor_data):
        """
        Verifies whether the address in neighbor/network statement is
        an  IPv4 address.
        Called by bgp_statement_parser method
        """
        pattern_ip = re.compile(r'((([0-9]){1,3})\.){3}([0-9]){1,3}')
        is_ipv4 = pattern_ip.search(neighbor_data)
        if bool(is_ipv4):
            return "ipv4"
        return "None"

    @staticmethod
    def find_bgp_neighbors(bgp_data, each_statement, vrf):
        """
        Retrieves IP addresses from neighbor <x.y.z.w> statement
        Called by bgp_statement_parser method
        """
        if vrf not in bgp_data.keys():
            bgp_data[vrf] = {}

        if "neighbors" not in bgp_data[vrf]:
            bgp_data[vrf]["neighbors"] = []

        if each_statement.split()[1] not in bgp_data[vrf]["neighbors"]:
            bgp_data[vrf]["neighbors"].append(str(each_statement.split()[1]))

        return bgp_data

    @staticmethod
    def find_bgp_networks(bgp_data, each_statement, vrf):
        """
        Retrieves network address from the network <x.y.z.0/24> statement
        Called by bgp_statement_parser method
        """
        if vrf not in bgp_data.keys():
            bgp_data[vrf] = {}

        if "networks" not in bgp_data[vrf]:
            bgp_data[vrf]["networks"] = []

        if each_statement.split()[1] not in bgp_data[vrf]["networks"]:
            bgp_data[vrf]["networks"].append(str(each_statement.split()[1]))

        return bgp_data

    def bgp_statement_parser(self, bgp_config):
        """
        Retrieves BGP Neighbor IP addresses from the BGP configuration
        Also retrieves Network addresses advertised using network statement
        This method is called by bgp_validate method.
        """
        bgp_data = {}
        for each_statement in bgp_config:
            if not each_statement.find("neighbor"):
                verify_ipv4_ipv6 = self.is_ipv4_ipv6(each_statement.split()[1])
                if verify_ipv4_ipv6 == "ipv4":
                    vrf = "default"
                    bgp_data = self.find_bgp_neighbors(bgp_data,
                                                       each_statement, vrf)

            if not each_statement.find("network"):
                verify_ipv4_ipv6_subnet = self.is_ipv4_ipv6(
                    each_statement.split()[1]
                    )
                if verify_ipv4_ipv6_subnet == "ipv4":
                    vrf = "default"
                    bgp_data = self.find_bgp_networks(
                        bgp_data, each_statement, vrf
                        )

            if not each_statement.find("address-family ipv4"):
                bgp_per_af_config = bgp_config[each_statement]["cmds"]
                vrf = "default"

                for each_statement_within_af in bgp_per_af_config:
                    if not each_statement_within_af.find("network"):
                        bgp_data = self.find_bgp_networks(
                            bgp_data, each_statement_within_af, vrf
                            )

            if not each_statement.find("vrf"):
                vrf = str(each_statement.split()[1])
                bgp_per_vrf_config = bgp_config[each_statement]["cmds"]

                for each_statement_within_vrf in bgp_per_vrf_config:
                    if not each_statement_within_vrf.find("neighbor"):
                        verify_ipv4_ipv6 = self.is_ipv4_ipv6(
                            each_statement_within_vrf.split()[1]
                            )
                        if verify_ipv4_ipv6 == "ipv4":
                            bgp_data = self.find_bgp_neighbors(
                                bgp_data, each_statement_within_vrf, vrf
                                )

                    if not each_statement_within_vrf.find("network"):
                        verify_ipv4_ipv6_subnet = self.is_ipv4_ipv6(
                            each_statement_within_vrf.split()[1]
                            )
                        if verify_ipv4_ipv6_subnet == "ipv4":
                            bgp_data = self.find_bgp_networks(
                                bgp_data, each_statement_within_vrf, vrf
                                )

                    if not each_statement_within_vrf.find(
                            "address-family ipv4"):
                        bgp_per_vrf_af_config = (bgp_per_vrf_config
                                                 [each_statement_within_vrf]
                                                 ["cmds"])

                        for each_statement_within_vrf_af in \
                                bgp_per_vrf_af_config:
                            if (not each_statement_within_vrf_af.find
                                    ("network")):
                                bgp_data = self.find_bgp_networks(
                                    bgp_data, each_statement_within_vrf_af, vrf
                                    )

        return bgp_data

    @staticmethod
    def bgp_config_exist(running_config):
        """
        This method verifies whether BGP is configured
        This method is called by bgp_validate method.
        """
        bgp_config = ["None"]
        bgp_data = {}
        for each in running_config:
            if not each.find("router bgp"):
                bgp_config = running_config[each]["cmds"]
                bgp_config["local_As"] = str(each.split()[2])

        return bgp_config

    @staticmethod
    def bgp_status_check(bgp_config, bgp_summary):
        """
        Checks BGP State against configured BGP neighbors
        This method is called by bgp_validate method.
        """
        device_bgp_status = {}
        for each_vrf in bgp_config:
            device_bgp_status[each_vrf] = {}
            if each_vrf in bgp_summary:
                for each_neighbor in bgp_config[each_vrf]["neighbors"]:
                    if each_neighbor in bgp_summary[each_vrf]["peers"]:
                        bgp_peer_state = (bgp_summary[each_vrf]
                                                     ["peers"]
                                                     [each_neighbor]
                                                     ["peerState"])

                        if bgp_peer_state != "Established":
                            device_bgp_status[each_vrf][str(each_neighbor)] = (
                                str("Neighbor state is " + bgp_peer_state))
                    else:
                        device_bgp_status[each_vrf][str(each_neighbor)] = (
                            "BGP is NOT operational for this neighbor")

                if not device_bgp_status[each_vrf]:
                    device_bgp_status[each_vrf]["Status"] = (
                        "All the configured BGP peers are up in this VRF")
                    device_bgp_status[each_vrf]["Configured Neighbors"] = (
                        bgp_config[each_vrf]["neighbors"])
                else:
                    device_bgp_status[each_vrf]["Configured Neighbors"] = (
                        bgp_config[each_vrf]["neighbors"])
            else:
                device_bgp_status[each_vrf]["Status"] = (
                    "There are no operational BGP neighbors in this VRF.")
                device_bgp_status[each_vrf]["Configured Neighbors"] = (
                    bgp_config[each_vrf]["neighbors"])

        return device_bgp_status

    def bgp_validate(self):
        """
        1. This is the method called from the Assessment Tool
        2. This method collects the show run using Commands Class
        3. Checks if BGP is configured using bgp_config_exist static method.
        4. Retrieves BGP Configuration from the show run
            using bgp_statement_parser method.
        5. Collect show ip bgp summary using Commands Class
        6. Checks BGP Adjacency using bgp_status_check static method.
        7. Document BGP Adjacency state in the bgp_status dictionary
        8. Document eAPI connectivity issues in errors dictionary

        """
        for switch in self.devices:
            self.bgp_status[switch] = {}
            try:
                eos_commands = Commands(switch, self.username, self.password)

                # Collect Show run
                running_config = eos_commands.runningconfig()

                # Verify BGP is configured
                bgp_config = self.bgp_config_exist(running_config)

                if "None" not in bgp_config:
                    # If configured, retrieve BGP Neighbor IP addresses
                    get_bgp_config = self.bgp_statement_parser(bgp_config)

                    # Collect show ip bgp summary
                    bgp_summary = eos_commands.bgpsummary()

                    # Validate BGP Adjacency
                    self.bgp_status[switch] = self.bgp_status_check(
                        get_bgp_config, bgp_summary)

                else:
                    # If BGP configuration not found, document it
                    self.bgp_status[switch] = (
                        "BGP is not configured on this switch.")

            except pyeapi.eapilib.ConnectionError:
                self.errors[switch] = (
                    "ConnectionError: unable to connect to eAPI")

            except pyeapi.eapilib.CommandError:
                self.errors[switch] = (
                    "CommandError: Check your EOS command syntax")

            if not self.bgp_status[switch]:
                """
                If unable to connect to switch, delete entry for that switch
                in the bgp_status dictionary
                """
                del self.bgp_status[switch]

    def get_bgp_status(self):
        return self.bgp_status

    def get_errors(self):
        return self.errors

class MlagValidate(DefineEapiVariables):

    def __init__(self, devices, username, password):
        super(MlagValidate, self).__init__(devices, username, password)
        self.mlag_status = {}

    @staticmethod
    def mlag_status_check(show_mlag):

        device_mlag_status = {}

        # verify MLAG is configured
        mlag_configs = show_mlag.keys()

        if ("domainId" in mlag_configs and
                "peerLink" in mlag_configs and
                "localInterface" in mlag_configs):
            if show_mlag["state"] == "active":
                device_mlag_status["MLAG Control Plane"] = (
                    "MLAG Control Plane is active")
                if show_mlag["mlagPorts"]["Active-full"] != 0:
                    device_mlag_status["MLAG Active-full Port Channels"] = (
                        str(show_mlag["mlagPorts"]["Active-full"]))
                if show_mlag["mlagPorts"]["Inactive"] != 0:
                    device_mlag_status["MLAG Inactive Port Channels"] = (
                        str(show_mlag["mlagPorts"]["Inactive"]))
                if show_mlag["mlagPorts"]["Active-partial"] != 0:
                    device_mlag_status["MLAG Active-partial Port Channels"] = (
                        str(show_mlag["mlagPorts"]["Active-partial"]))
            else:
                device_mlag_status["MLAG Control Plane"] = (
                    "MLAG Control Plane is not Active. Its current state is " +
                    str(show_mlag["state"]))
        else:
            device_mlag_status = "MLAG is not configured in this switch"

        return device_mlag_status

    def mlag_validate(self):

        for switch in self.devices:
            self.mlag_status[switch] = {}
            try:
                eos_commands = Commands(switch, self.username, self.password)

                # Execute the desired command
                show_mlag = eos_commands.mlag()
                self.mlag_status[switch] = self.mlag_status_check(show_mlag)

            except pyeapi.eapilib.ConnectionError:
                self.errors[switch] = (
                    "ConnectionError: unable to connect to eAPI")

            except pyeapi.eapilib.CommandError:
                self.errors[switch] = (
                    "CommandError: Check your EOS command syntax")

            if not self.mlag_status[switch]:
                del self.mlag_status[switch]

    def get_mlag_status(self):
        return self.mlag_status

    def get_errors(self):
        return self.errors