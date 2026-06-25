# !/usr/bin/env python3
import logging
import lxml.etree as ET
import lxml.objectify as objectify
from json2xml import json2xml
import ipaddress


# from bs4 import BeautifulSoup


# logger = logging.getLogger("Extractor")
# handler = logging.FileHandler('./system_plugin.log')
# formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
# handler.setFormatter(formatter)
# logger.addHandler(handler)
# logger.setLevel(logging.ERROR)

# dep_namespace:
def run(xml_object, dep_class, dep_name, dep_namespace, test_run, rule_name, rule_namespace):

    # Test messages
    logging.info("Entering into run method in l2vpn_plugin.py")

    result = {}
    result_list = []
    utf8_parser = ET.XMLParser(encoding='utf-8', recover=True)
    root = ET.fromstring(xml_object.encode('utf-8'), parser=utf8_parser)
    # #### To remove the namespace if its present
    for elem in root.iter():
        if not hasattr(elem.tag, 'find'): continue  # (1)
        i = elem.tag.find('}')
        if i >= 0:
            elem.tag = elem.tag[i + 1:]
    objectify.deannotate(root, cleanup_namespaces=True)
    # ####

    try:
        if dep_class == "subservice.interface.health" and dep_name == "vpn-if-health-list" and \
                dep_namespace == "system" and \
                rule_name == "Rule-L2VPN-MP" and rule_namespace == "system":
            return extract_subservice_vpn_interfaces_payload(root, test_run)

        else:
            return result_list
    except Exception as exception:
        logging.error("Exception encountered while running the l2vpn_plugin.py for Dependency Class: {dep_class}, Dependency Name: {dep_name}, Dependency Namespace: {dep_namespace}, Rule Name: {rule_name}, Rule Namespace: {rule_namespace}. Error:{error}" \
                                                                                           "".format(dep_class=dep_class, dep_name=dep_name, dep_namespace=dep_namespace, rule_name=rule_name, rule_namespace=rule_namespace, error=exception))
        return "Exception encountered while running the l2vpn_plugin.py for Dependency Class: {dep_class}, Dependency Name: {dep_name}, Dependency Namespace: {dep_namespace}, Rule Name: {rule_name}, Rule Namespace: {rule_namespace}. Error {error}" \
                                                                                           "".format(dep_class=dep_class, dep_name=dep_name, dep_namespace=dep_namespace, rule_name=rule_name, rule_namespace=rule_namespace, error=exception)



def extract_subservice_vpn_interfaces_payload(root, test_run):
    result_list = []

    if test_run:
        result_list = ["device", "ifId"]
        return result_list

    device_records = root.findall('.//vpn-service/vpn-nodes/vpn-node/vpn-node-id')
    devices = [device_record.text for device_record in device_records]


    for device in devices:
        # Each result is a dictionary that can be used to instantiate one Subservice instance

        # vpn_network_access_records = root.findall(".//vpn-nodes/vpn-node[vpn-node-id='{device}']/vpn-network-accesses/vpn-network-access").format(device=device)

        vpn_network_access_id_record = ".//vpn-nodes/vpn-node[vpn-node-id='{device}']/vpn-network-accesses/vpn-network-access/id".format(device=device)
        vpn_network_access_id_records = root.findall(vpn_network_access_id_record)
        vpn_network_access_ids = [vpn_network_access_id_record.text for vpn_network_access_id_record in vpn_network_access_id_records]
        for vpn_network_access_id in vpn_network_access_ids:
            result = {}
            result["device"] = device
            vpn_interface_type_path = ".//vpn-nodes/vpn-node[vpn-node-id='{device}']/vpn-network-accesses/vpn-network-access[id='{vpn_network_access_id}']/connection/encapsulation/encap-type".format(
                device=device,vpn_network_access_id=vpn_network_access_id)

            vpn_interface_type_record = root.xpath(vpn_interface_type_path)
            if vpn_interface_type_record[0].text == "x:dot1q":
                phy_interface_path = ".//vpn-nodes/vpn-node[vpn-node-id='{device}']/vpn-network-accesses/vpn-network-access[id='{vpn_network_access_id}']/interface-id".format(
                    device=device,vpn_network_access_id=vpn_network_access_id)
                phy_interface_record = root.xpath(phy_interface_path)
                vlan_id_path = ".//vpn-nodes/vpn-node[vpn-node-id='{device}']/vpn-network-accesses/vpn-network-access[id='{vpn_network_access_id}']/connection/l2-termination-point".format(
                    device=device,vpn_network_access_id=vpn_network_access_id)
                vlan_id_record = root.xpath(vlan_id_path)
                if  len(vlan_id_record) != 0:
                    result["ifId"] = phy_interface_record[0].text + "." + vlan_id_record[0].text
                else:
                    result["ifId"] = phy_interface_record[0].text
            else:
                # TBD: this needs to return error if its not dot1q
                phy_interface_path = ".//vpn-nodes/vpn-node[vpn-node-id='{device}']/vpn-network-accesses/vpn-network-access[id='{vpn_network_access_id}']/interface-id".format(
                    device=device,vpn_network_access_id=vpn_network_access_id)
                phy_interface_record = root.xpath(phy_interface_path)
                vlan_id_path = ".//vpn-nodes/vpn-node[vpn-node-id='{device}']/vpn-network-accesses/vpn-network-access[id='{vpn_network_access_id}']/connection/dot1q-interface/dot1q/c-vlan-id".format(
                    device=device,vpn_network_access_id=vpn_network_access_id)
                vlan_id_record = root.xpath(vlan_id_path)
                if len(vlan_id_record) != 0:
                    result["ifId"] = phy_interface_record[0].text + "." + vlan_id_record[0].text
                else:
                    result["ifId"] = phy_interface_record[0].text

            result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
            result_list.append(result_xml)

            # TODO: Each result is a dictionary that can be used to instantiate one Subservice instance
        # vpn_network_access_records = root.findall(".//vpn-nodes/vpn-node[vpn-node-id='{device}']/vpn-network-accesses/vpn-network-access".format(device=device))
        # result = {}
        # for vpn_network_access_record in vpn_network_access_records:
        #     vna_id = vpn_network_access_record.xpath('./id/text()')
        #
        #     # Create one record for each VPN Network Access
        #     result["device"] = device
        #     result["vpn-network-access-id"] = vna_id
        #
        #     encap_type = vpn_network_access_record.xpath('./connection/encapsulation-type/text()')
        #     if encap_type == 'vpn-common:dot1q':
        #         phy_intf = vpn_network_access_record.xpath('./connection/dot1q-interface/dot1q/physical-inf/text()')
        #         vlan_id = vpn_network_access_record.xpath('./connection/dot1q-interface/dot1q/c-vlan-id/text()')
        #         intf_id = phy_intf + "." + vlan_id
        #         result["interface_id"] = intf_id
        #         result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
        #         result_list.append(result_xml)
        #     # else:
        #     #     print("Not Supported")
        #     #     result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
        #     #     result_list.append(result_xml)

    return result_list
