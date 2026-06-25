# !/usr/bin/env python3
import logging
import lxml.etree as ET
import lxml.objectify as objectify
from json2xml import json2xml
from itertools import combinations
import ipaddress
import uuid

def run(xml_object, dep_class, dep_name, dep_namespace, test_run, rule_name, rule_namespace):
    result = {}
    result_list = []
    utf8_parser = ET.XMLParser(encoding='utf-8', recover=True)
    root = ET.fromstring(xml_object.encode('utf-8'), parser=utf8_parser)
    ##### To remove the namespace if its present
    for elem in root.iter():
        if not hasattr(elem.tag, 'find'): continue  # (1)
        i = elem.tag.find('}')
        if i >= 0:
            elem.tag = elem.tag[i + 1:]
    objectify.deannotate(root, cleanup_namespaces=True)

    try:
        if dep_class == "subservice.interface.health" and dep_name == "vpn-if-health-list" and \
                dep_namespace == "custom" and rule_namespace == "custom" and \
                rule_name in ("Rule-L3VPN-Demo", "Rule-L3VPN-NM-VPN-Node"):
            return extract_subservice_vpn_interfaces_payload(root, test_run)
        elif dep_class == "subservice.ebgp.nbr.health" and \
                dep_namespace == "custom" and \
                rule_name == "Rule-L3VPN-Demo" and rule_namespace == "custom":
            return extract_subservice_ebgp_nbr_health_payload(root, test_run)
        elif rule_name in ("Rule-L3VPN-Demo", "Rule-L3VPN-NM-VPN-Node") and rule_namespace == "custom" and \
                dep_class == "subservice.vrf.plain.lsp.reachability":
            return extract_subservice_vrf_plain_lsp_reachability_payload(root, test_run)
        elif rule_name in ("Rule-L3VPN-Demo", "Rule-L3VPN-NM-VPN-Node") and rule_namespace == "custom" and \
                dep_class == "subservice.dynamic.l3vpn.sr.policy":
            return extract_subservice_dynamic_l3vpn_sr_policy_payload(root, test_run)
        elif rule_name in ("Rule-L3VPN-Demo", "Rule-L3VPN-NM-VPN-Node") and rule_namespace == "custom" and \
                dep_class == "subservice.probe.session.health":
            return extract_subservice_dynamic_probe_session_payload(root, test_run)
        else:
            return result_list
    except Exception as exception:
        return "exception in running the plugin(Iter9). Error {error}".format(error=exception)


# Payload Extraction logic for subservice.vrf.plain.lsp.reachability
def extract_subservice_vrf_plain_lsp_reachability_payload(root, test_run):
    result_list = []
    if test_run:
        result_list = ["device", "vrf", "peer-vpn-addr-list"]
        return result_list

    all_vpn_ip_records = root.xpath(".//vpn-network-accesses/vpn-network-access/ip-connection/*/local-address")
    all_vpn_prefix_length = root.xpath(".//vpn-network-accesses/vpn-network-access/ip-connection/*/prefix-length")
    all_ip_records = []
    for ip in all_vpn_ip_records:
        all_ip_records.append(ip.text)

    for vpn_node in root.findall("./vpn-node"):
        result = {}
        device = vpn_node.find(".//vpn-node-id")
        result["device"] = device.text
        vrf = root.find(".//vpn-service/vpn-id")
        result["vrf"] = vrf.text
        self_vpn_ip = vpn_node.find(".//vpn-network-accesses/vpn-network-access/ip-connection/*/local-address")

        # Fetch all IP addresses except for self one
        peer_ntw_list = []
        for ip_record in all_vpn_ip_records:
            if ip_record.text != self_vpn_ip.text:
                version = ipaddress.ip_interface(ip_record.text).version
                prefix_index = all_vpn_ip_records.index(ip_record)
                ip_plus_prefix_str = ip_record.text + "/" + all_vpn_prefix_length[prefix_index].text

                if version == 4:
                    ip_ntw_str = ipaddress.IPv4Interface(ip_plus_prefix_str)
                else:
                    ip_ntw_str = ipaddress.IPv6Interface(ip_plus_prefix_str)

                peer_ntw_str = "%s" % ip_ntw_str.network

                peer_ntw_list.append(peer_ntw_str)

        result["peer-vpn-addr-list"] = peer_ntw_list
        result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True,
                                       attr_type=False).to_xml()
        result_list.append(result_xml)

    return result_list

def extract_subservice_dynamic_l3vpn_sr_policy_payload(root, test_run):
    result_list = []
    if test_run:
        result_list = ["device", "vpnServiceId", "vpnAddr"]
        return result_list

    vpn_records = root.findall(".//vpn-node/vpn-node-id")
    vpn_nodes = [vpn_record.text for vpn_record in vpn_records]

    for vpn_node in vpn_nodes:
        result = {}
        device_config = get_device_config(root, vpn_node)
        if device_config is None or not device_has_route_policy(device_config):
            continue
        result["device"] = vpn_node

        vpn_serviceId_path = ".//vpn-service/vpn-id"
        vpn_serviceId_record = root.find(vpn_serviceId_path)
        result["vpnServiceId"] = vpn_serviceId_record.text
        vpn_addr_path = ".//vpn-node[vpn-node-id='{vpn_node}']/vpn-network-accesses/vpn-network-access[1]/ip-connection/*/local-address".format(
            vpn_node=vpn_node)
        vpn_addr_record = root.find(vpn_addr_path)
        result["vpnAddr"] = vpn_addr_record.text

        result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
        result_list.append(result_xml)

    return result_list


def get_device_config(root, device_name):
    device_nodes = root.xpath(".//*[local-name()='devices']/*[local-name()='device']")
    if root.xpath("local-name()") == "device":
        device_nodes.append(root)

    for direct_device in root.xpath(".//*[local-name()='device']"):
        if direct_device not in device_nodes:
            device_nodes.append(direct_device)

    for device in device_nodes:
        for key_name in ("key", "name", "device-name"):
            key = device.find("./{key_name}".format(key_name=key_name))
            if key is None:
                key = device.xpath("./*[local-name()='{key_name}']".format(key_name=key_name))
                key = key[0] if len(key) != 0 else None
            if key is not None and key.text == device_name:
                return device
    return None


def device_has_route_policy(device_config):
    route_policy_paths = (
        ".//config/vrf/vrf-list/address-family/*/unicast/export/route-policy",
        ".//config/vrf/vrf-list/address-family/*/unicast/import/route-policy",
    )
    for path in route_policy_paths:
        if device_config.xpath(path):
            return True
    return False


def resolve_device_interface_id(root, device_name, service_interface_id, subinterface_id):
    device_config = get_device_config(root, device_name)
    if device_config is None or subinterface_id == "":
        return service_interface_id

    generated_interface_id = find_generated_interface_for_subinterface(device_config, subinterface_id)
    if generated_interface_id != "":
        return generated_interface_id

    return service_interface_id


def find_generated_interface_for_subinterface(device_config, subinterface_id):
    interface_nodes = device_config.xpath(
        ".//*[local-name()='configuration']"
        "/*[local-name()='interfaces']"
        "/*[local-name()='interface']"
    )
    for interface_node in interface_nodes:
        interface_name_nodes = interface_node.xpath("./*[local-name()='name']")
        interface_name_node = interface_name_nodes[0] if len(interface_name_nodes) != 0 else None
        if interface_name_node is None or interface_name_node.text is None or interface_name_node.text == "":
            continue

        unit_name_nodes = interface_node.xpath("./*[local-name()='unit']/*[local-name()='name']")
        for unit_name_node in unit_name_nodes:
            if unit_name_node.text == subinterface_id:
                return interface_name_node.text

    routing_instance_interfaces = device_config.xpath(
        ".//*[local-name()='configuration']"
        "/*[local-name()='routing-instances']"
        "/*[local-name()='instance']"
        "/*[local-name()='interface']"
        "/*[local-name()='name']/text()"
    )
    for interface_name in routing_instance_interfaces:
        if interface_name.endswith("." + subinterface_id):
            return interface_name.rsplit(".", 1)[0]

    return ""


def extract_subservice_dynamic_probe_session_payload(root, test_run):
    subservice_limit = 0
    max_subservice_limit = 200
    accedian = 'ACCEDIAN'

    result_list = []
    vpn_node_string = "vpn-node"
    if test_run:
        result_list = ["vpnServiceId", "proxyDevice","device", "peerDevice","probeSessionId"]
        return result_list

    exist = root.find(".//probes")
    if exist is None:
        return result_list

    probe_records = root.findall('.//probes/endpoint/id')

    probe_nodes = [probe_record.text for probe_record in probe_records]
    dict_nodes_map = {}
    for probe_node in probe_nodes:
        dict_nodes_map[probe_node] = {}
        vpn_node_path = ".//probes/endpoint[id='{probe_node}']/vpn-node".format(
            probe_node=probe_node)
        vpn_node = root.find(vpn_node_path)
        dict_nodes_map[probe_node][vpn_node_string] = vpn_node.text

    def generate_uuid(id):
        ns_uuid = uuid.UUID('123e4567-e89b-12d3-a456-426614174000')
        uuid_obj = uuid.uuid5(ns_uuid, id)
        uuid_str = str(uuid_obj)
        return uuid_str

    vpn_serviceId_path = ".//vpn-service/vpn-id"
    vpn_serviceId_record = root.find(vpn_serviceId_path).text

    point_to_point_list = root.find('.//probes/point-to-point')
    mesh = root.find('.//probes/mesh')
    hub_spoke_list = root.find('.//probes/hub-and-spoke')

    if point_to_point_list is not None:
        for connection in point_to_point_list.iter('connection'):
            result = {"vpnServiceId": vpn_serviceId_record, "proxyDevice": accedian}
            source_id = ''
            destination_id = ''
            for child in connection:
                if child.tag == 'source':
                    result["device"] = dict_nodes_map[child.text][vpn_node_string]
                    source_id = child.text
                if child.tag == 'destination':
                    result["peerDevice"] = dict_nodes_map[child.text][vpn_node_string]
                    destination_id = child.text
            result["probeSessionId"] = generate_uuid(vpn_serviceId_record +'_'+source_id + '_' + destination_id)
            result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
            result_list.append(result_xml)
            subservice_limit = subservice_limit + 1
            if subservice_limit == max_subservice_limit:
                return result_list

    if mesh is not None:
        # sorting the nodes based on the endpoint id
        sorted_nodes_map = {k: v for k, v in sorted(dict_nodes_map.items())}
        # creating unique pair of combination from the sorted key
        combinations_nodes_list = list(combinations(sorted_nodes_map.keys(), 2))
        for source, destination in combinations_nodes_list:
            source_id = source
            destination_id = destination
            result = {"vpnServiceId": vpn_serviceId_record,
                      "proxyDevice": accedian,
                      "device": dict_nodes_map[source][vpn_node_string],
                      "peerDevice": dict_nodes_map[destination][vpn_node_string],
                      "probeSessionId": generate_uuid(vpn_serviceId_record+'_'+source_id + '_' + destination_id)}
            result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
            result_list.append(result_xml)
            subservice_limit = subservice_limit + 1
            if subservice_limit == max_subservice_limit:
                return result_list

    if hub_spoke_list is not None:
        for hub_spoke in root.iter('hub-and-spoke'):
            hub_list = []
            spoke_list = []
            for child in hub_spoke:
                if child.tag == 'hub':
                    hub_list.append(child.text)
                if child.tag == 'spoke':
                    spoke_list.append(child.text)
            for hub in sorted(hub_list):
                for spoke in sorted(spoke_list):
                    source_id = hub
                    destination_id = spoke
                    result = {"vpnServiceId": vpn_serviceId_record,
                              "proxyDevice": accedian,
                              "device": dict_nodes_map[hub][vpn_node_string],
                              "peerDevice": dict_nodes_map[spoke][vpn_node_string],
                              "probeSessionId": generate_uuid(vpn_serviceId_record+'_'+source_id + '_' + destination_id)}
                    result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
                    result_list.append(result_xml)
                    subservice_limit = subservice_limit + 1
                    if subservice_limit == max_subservice_limit:
                        return result_list
    return result_list


# Payload Extraction logic for subservice.ebgp.nbr.health
def extract_subservice_ebgp_nbr_health_payload(root, test_run):
    result_list = []
    if test_run:
        result_list = ["device", "vrf", "bgp_nbr_type", "bgp_nbr_ipaddrs"]
        return result_list

    device_records = root.findall('.//endpoint/pe-device')
    devices = [device_record.text for device_record in device_records]
    for device in devices:
        # Each result is a dictionary that can be used to instantiate one Subservice instance
        result = {}
        result["device"] = device

        vrf = root.find(".//l3vpn/name")
        result["vrf"] = vrf.text

        # currently model has exactly 1 pe-ce interface
        vpn_network_accesses_path = ".//endpoint[pe-device='{device}']".format(device=device)
        vpn_network_access  = root.find(vpn_network_accesses_path)

        # This is currently not used
        result["bgp_nbr_type"] = "eBGP"

        bgp_nbr_ipaddrs_records = vpn_network_access.findall("ce-ipv4-address")
        if len(bgp_nbr_ipaddrs_records) == 0:
            continue
        bgp_nbr_ipaddrs = [bgp_ipaddr_record.text for bgp_ipaddr_record in bgp_nbr_ipaddrs_records]
        result["bgp_nbr_ipaddrs"] = bgp_nbr_ipaddrs

        result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
        result_list.append(result_xml)

    return result_list




def extract_subservice_vpn_interfaces_payload(root, test_run):
    result_list = []

    if test_run:
        result_list = ["device", "ifId", "interfaceId", "subInterfaceId"]
        return result_list

    device_records = root.findall('.//endpoint/pe-device')
    if len(device_records) != 0:
        devices = [device_record.text for device_record in device_records]

        for device in devices:
            # Each result is a dictionary that can be used to instantiate one Subservice instance
            result = {}
            result["device"] = device

            # currently model has exactly 1 pe-ce interface
            vpn_network_accesses_path = ".//endpoint[pe-device='{device}']".format(device=device)
            vpn_network_access = root.find(vpn_network_accesses_path)
            if vpn_network_access is None:
                continue

            interface_id = vpn_network_access.find(".//pe-interface")
            if interface_id is None or interface_id.text is None or interface_id.text == "":
                continue

            cvlan_id = vpn_network_access.find(".//pe-subinterface")
            subinterface_id = cvlan_id.text if cvlan_id is not None and cvlan_id.text != "" else ""
            resolved_interface_id = resolve_device_interface_id(root, device, interface_id.text, subinterface_id)
            if_id = resolved_interface_id + "." + subinterface_id if subinterface_id != "" else resolved_interface_id

            result["device"] = device
            result["ifId"] = if_id
            result["interfaceId"] = resolved_interface_id
            result["subInterfaceId"] = subinterface_id

            result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
            result_list.append(result_xml)

        return result_list

    device_records = root.findall('.//vpn-node/vpn-node-id')
    devices = [device_record.text for device_record in device_records]

    for device in devices:
        vpn_network_accesses_path = ".//vpn-node[vpn-node-id='{device}']/vpn-network-accesses".format(device=device)
        vpn_network_accesses = root.find(vpn_network_accesses_path)
        if vpn_network_accesses is None:
            continue

        for vpn_network_access in vpn_network_accesses.findall(".//vpn-network-access"):
            interface_id = vpn_network_access.find(".//interface-id")
            if interface_id is None or interface_id.text is None or interface_id.text == "":
                continue

            cvlan_id = vpn_network_access.find(".//connection/encapsulation/dot1q/cvlan-id")
            subinterface_id = cvlan_id.text if cvlan_id is not None and cvlan_id.text != "" else ""
            resolved_interface_id = resolve_device_interface_id(root, device, interface_id.text, subinterface_id)
            if_id = resolved_interface_id + "." + subinterface_id if subinterface_id != "" else resolved_interface_id

            result = {}
            result["device"] = device
            result["ifId"] = if_id
            result["interfaceId"] = resolved_interface_id
            result["subInterfaceId"] = subinterface_id

            result_xml = json2xml.Json2xml(result, wrapper="plugin-output", pretty=True, attr_type=False).to_xml()
            result_list.append(result_xml)

    return result_list
