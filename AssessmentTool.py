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

import getpass
import pprint
from networkAssessmentComponents import EapiAccess, Plotter, BgpValidate, MlagValidate

# Read the list of switch IP addresses

file_switches = "switches.txt"

switches = []

with open(file_switches) as readfile:
    for line in readfile:
        switches.append(line.strip())

# Get the username and password to connect to switches

my_username = raw_input("Enter your username: ")
my_password = getpass.getpass("Enter your password: ")


# Initiate the content for html file to write the assessment report

my_report = """<!DOCTYPE html>
<html>
<head>
<title>Post Deployment Network Validation</title>
</head>
<body>
<h1>Post Deployment Network Validation Report</h1>
<p>
This report shows if the state of the BGP neighbor is not in the "Established" state.
BGP neighbor state is verified against the configured BGP neighbors under each VRF.
This report is generated only for ipv4 neighbors.
The report also shows the state of MLAG control plane and the port channels.
</p>
"""

# Write a reusable function to write html report

def write_report(my_report, result):
    for each_switch in result:
        my_report += "<p>"
        my_report += each_switch + " :  " + str(result[each_switch])
        my_report += "</p>"

    return my_report

# Verify the eAPI connectivity to the switches.
# Remove the switches that has eAPI connectivity issue from the list

print "Validating eAPI connectivity to the switches"

device_eapi_access = EapiAccess(switches, my_username, my_password)
device_eapi_access.validate_switches()
switches = device_eapi_access.get_hostnames()

# Draw Physical Topology

print "Working on Drawing Physical Topology"

network_topology = Plotter(switches, my_username, my_password)
network_topology.draw()

print "Physical Topology is drawn."

# BGP Assessment

print "Working on BGP Assessment"
bgp_assessment = BgpValidate(switches, my_username, my_password)
bgp_assessment.bgp_validate()

if bool(bgp_assessment.get_bgp_status()):
    pprint.pprint(bgp_assessment.get_bgp_status())
    result = bgp_assessment.get_bgp_status()
    my_report += """ <h1>BGP Validation</h1>
    """
    for each_switch in result:
        my_report += "<h2>" + str(each_switch) + "</h2>"
        if isinstance(result[each_switch], dict):
            for each_vrf in result[each_switch]:
                my_report += "<h3>" + str(each_vrf) + "</h3>"
                my_report = write_report(my_report, result[each_switch][each_vrf])
        else:
            my_report += "<p>" + str(result[each_switch]) + "</p>"

    print "BGP Assessment Completed."

# MLAG Assessment
print "Working on MLAG Assessment"
mlag_assessment = MlagValidate(switches, my_username, my_password)
mlag_assessment.mlag_validate()

if bool(mlag_assessment.mlag_status):
    pprint.pprint(mlag_assessment.mlag_status)
    result = mlag_assessment.get_mlag_status()
    my_report += """ <h1>MLAG Validation</h1>
    """
    for each_switch in result:
        my_report += "<h2>" + str(each_switch) + "</h2>"
        if isinstance(result[each_switch], dict):
            my_report = write_report(my_report, result[each_switch])
        else:
            my_report += "<p>" + str(result[each_switch]) + "</p>"

    print "MLAG Assessment Completed."


# Prepare to write a report

if bool(device_eapi_access.errors) or bool(network_topology.errors) or bool(bgp_assessment.errors):
    my_report += """ <h1>eAPI Access Issues</h1>
    """

if bool(device_eapi_access.errors):
    print "There are connectivity issues with some of the switches."
    pprint.pprint(device_eapi_access.errors)
    my_report += "<h2>eAPI or Switch Connectivity Issues</h2>"
    result = device_eapi_access.errors
    my_report = write_report(my_report, result)

if bool(network_topology.errors):
    print "There are connectivity issues with some of the switches."
    pprint.pprint(network_topology.errors)
    my_report += "<h2>Network Topology Related EOS Commands Error</h2>"
    result = network_topology.errors
    my_report = write_report(my_report, result)

if bool(bgp_assessment.errors):
    pprint.pprint(bgp_assessment.errors)
    my_report += "<h2>BGP Assessment Related EOS Commands Error</h2>"
    result = bgp_assessment.errors
    my_report = write_report(my_report, result)

if bool(mlag_assessment.errors):
    pprint.pprint(mlag_assessment.errors)
    my_report += "<h2>MLAG Assessment Related EOS Commands Error</h2>"
    result = mlag_assessment.errors
    my_report = write_report(my_report, result)


# Writing the content to HTML File for Reporting

with open("network_validation.html", "w") as writefile:
    writefile.write(my_report)
