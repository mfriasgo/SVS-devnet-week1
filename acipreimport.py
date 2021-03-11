#!/usr/bin/env python

# Copyright (c) 2015 by Cisco Systems, Inc.
#
# THIS SAMPLE CODE IS PROVIDED "AS IS" WITHOUT ANY EXPRESS OR IMPLIED WARRANTY
# BY CISCO SOLELY FOR THE PURPOSE of PROVIDING PROGRAMMING EXAMPLES.
# CISCO SHALL NOT BE HELD LIABLE FOR ANY USE OF THE SAMPLE CODE IN ANY
# APPLICATION.
#
# Redistribution and use of the sample code, with or without
# modification, are permitted provided that the following conditions
# are met:
# Redistributions of source code must retain the above disclaimer.

'''
Prepare ACI config export to import into lab

It support both json and xml format

The following is done:
    1. Remove apic-1 oob management IP, so that lab apic oob mgmt ip is kept. If -a is passed in, remove all oob mgmt IP,
        this is because if these mgmt IP overlapping with lab TEP pool, import will fail
    2. Remove admin user config, so that current lab admin user password is kept
    3. Change default and console authentication to local
    4. Remove TepPool configuration if it is in the config. import will fail if Tep Pool is different

@author Ming Li(mingli@cisco.com)
'''



import json
import xml.etree.ElementTree as ET
import argparse
import tarfile
import fnmatch
import os

def prepareJsonContent(content, fileName = 'N/A', removeAllOob = False):
    for polUniChild in content['polUni']['children']:
        # Remove apic oob mgmt ip
        if 'fvTenant' in polUniChild and polUniChild['fvTenant']['attributes']['dn'] == 'uni/tn-mgmt':
            for tenentChild in polUniChild['fvTenant']['children']:
                if 'mgmtMgmtP' in tenentChild:
                    for mgmtChild in tenentChild['mgmtMgmtP']['children']:
                        if 'mgmtOoB' in mgmtChild:
                            if removeAllOob:
                                mgmtChild['mgmtOoB'].pop('children', None)
                                print("!! Removing all oob mgmt ip ")
                            else:
                                toRemove = []
                                for oobChild in mgmtChild['mgmtOoB']['children']:
                                    apicNodeId = ['topology/pod-1/node-'+str(i) for i in range(1,2)]
                                    if 'mgmtRsOoBStNode' in oobChild and oobChild['mgmtRsOoBStNode']['attributes']['tDn'] in apicNodeId:
                                        print ("!! Removing oob mgmt ip {:}: {:}").format(fileName, oobChild['mgmtRsOoBStNode']['attributes']['tDn'])
                                        toRemove.append(oobChild)
                                [mgmtChild['mgmtOoB']['children'].remove(t) for t in toRemove]

        # Remove admin user config
        if 'aaaUserEp' in polUniChild:
            toRemove = []
            for aaaChild in polUniChild['aaaUserEp']['children']:
                if 'aaaUser' in aaaChild and aaaChild['aaaUser']['attributes']['name'] == 'admin':
                    toRemove.append(aaaChild)
            [polUniChild['aaaUserEp']['children'].remove(t) for t in toRemove]

        # Change default log in to local
        if 'aaaUserEp' in polUniChild:
            for aaaChild in polUniChild['aaaUserEp']['children']:
                if 'aaaAuthRealm' in aaaChild:
                    aaaChild['aaaAuthRealm']['children'][0]['aaaDefaultAuth']['attributes']['realm'] = 'local'
                    aaaChild['aaaAuthRealm']['children'][1]['aaaConsoleAuth']['attributes']['realm'] = 'local'

        #Remove fabricSetupP, as TepPool cannot be changed
        if 'ctrlrInst' in  polUniChild:
            for ctrlChild in polUniChild['ctrlrInst']['children']:
                if 'fabricSetupPol' in ctrlChild:
                    toRemove = None
                    for fspChild in ctrlChild['fabricSetupPol']['children']:
                        if 'fabricSetupP' in fspChild:
                            toRemove = fspChild
                            break
                    ctrlChild['fabricSetupPol']['children'].remove(toRemove)


def prepareXmlContent(content, fileName = 'N/A', removeAllOob = False):
    root = content.getroot()
    #Remove apic oob mgmt address
    mgmtOob = root.find('fvTenant[@dn="uni/tn-mgmt"]/mgmtMgmtP/mgmtOoB')
    if mgmtOob is not None:
        if removeAllOob:
            toremove = mgmtOob.findall('mgmtRsOoBStNode')
            if toremove is not None:
                [mgmtOob.remove(t) for t in toremove]

        else:
            apicNodeId = ['topology/pod-1/node-'+str(i) for i in range(1,2)]
            for apic in apicNodeId:
                toremove = mgmtOob.find('mgmtRsOoBStNode[@tDn="'+apic+'"]')
                if toremove is not None:
                    mgmtOob.remove(toremove)
    # Remove admin user config
    aaaUserEp = root.find('aaaUserEp')
    if aaaUserEp is not None:
        adminUser = aaaUserEp.find('aaaUser[@name="admin"]')
        if adminUser is not None:
            aaaUserEp.remove(adminUser)
    # Change default log in to local
    aaaAuthRealm = root.find('aaaUserEp/aaaAuthRealm')
    if aaaAuthRealm is not None:
        defaultAuth = aaaAuthRealm.find('aaaDefaultAuth')
        if defaultAuth is not None:
            defaultAuth.set('realm', 'local')
        consoleAuth = aaaAuthRealm.find('aaaConsoleAuth')
        if consoleAuth is not None:
            consoleAuth.set('realm', 'local')
    # Remove fabricSetupP, as TepPool cannot be changed
    fabricSetupPol = root.find('ctrlrInst/fabricSetupPol')
    if fabricSetupPol is not None:
        fabricSetupP = fabricSetupPol.find('fabricSetupP')
        if fabricSetupP is not None:
            fabricSetupPol.remove(fabricSetupP)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Remove APIC oob addr/admin user config.')
    parser.add_argument('file', help='aci config export files')
    parser.add_argument('-a', '--all_oob', help='Remove all node OOB, in case OOB addr overlapping with lab VTEP pool', action='store_true', default=False)
    args = parser.parse_args()

    confExport = tarfile.open(name=args.file, mode='r')
    newConfExport = tarfile.open(name='converted_'+args.file, mode="w|gz")

    for tarinfo in confExport:
        fileName = tarinfo.name
        print(fileName)
        if tarinfo.isdir():
            newConfExport.addfile(tarinfo, confExport.extractfile(fileName))
        elif fnmatch.fnmatch(fileName, "*/*"):
            newConfExport.addfile(tarinfo, confExport.extractfile(fileName))
        elif fnmatch.fnmatch(fileName, "*.json"):
            content = json.load(confExport.extractfile(fileName))
            prepareJsonContent(content, fileName, args.all_oob)

            fp = open(fileName, 'w')
            json.dump(content, fp)
            fp.close()
            newConfExport.add(fileName)
            os.remove(fileName)


        elif fnmatch.fnmatch(fileName, "*.xml"):
            content = ET.parse(confExport.extractfile(fileName))
            prepareXmlContent(content, fileName, args.all_oob)
            content.write(fileName)
            newConfExport.add(fileName)
            os.remove(fileName)

        else:
            newConfExport.add(tarinfo, confExport.extractfile(fileName))

    newConfExport.close()


