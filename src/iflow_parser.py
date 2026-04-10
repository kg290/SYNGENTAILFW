"""iFlow XML Parser - Extracts data from SAP CPI BPMN2 XML files."""
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import xml.etree.ElementTree as ET
import re
import logging

logger = logging.getLogger(__name__)


class IFlowParserError(Exception):
    """Custom exception for iFlow parsing errors."""
    pass


# SAP CPI XML Namespaces
NS = {
    'bpmn2': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
    'ifl': 'http:///com.sap.ifl.model/Ifl.xsd',
}


def format_key(key: str) -> str:
    """Convert camelCase/snake_case to Title Case."""
    key = key.replace("_", " ")
    key = re.sub(r"(?<!^)(?=[A-Z])", " ", key)
    return key.title()


class IFlowParser:
    """Parser for SAP CPI iFlow BPMN2 XML files."""
    
    def __init__(self, iflow_path: Path):
        self.iflow_path = Path(iflow_path)
        
        if not self.iflow_path.exists():
            raise IFlowParserError(f"iFlow file not found: {self.iflow_path}")
        
        if not self.iflow_path.suffix.lower() == '.iflw':
            raise IFlowParserError(f"Not an iFlow file (.iflw): {self.iflow_path}")
        
        self.tree: Optional[Any] = None
        self.root: Optional[ET.Element] = None
        self.iflow_name = self.iflow_path.stem
    
    def parse(self) -> ET.Element:
        """Load and parse the iFlow XML file."""
        try:
            parsed_tree = ET.parse(str(self.iflow_path))
            parsed_root = parsed_tree.getroot()
            self.tree = parsed_tree
            self.root = parsed_root
            logger.debug(f"Parsed iFlow: {self.iflow_name}")
            return parsed_root
        except ET.ParseError as e:
            raise IFlowParserError(f"Invalid XML in iFlow file: {e}")
        except Exception as e:
            raise IFlowParserError(f"Failed to parse iFlow: {e}")
    
    def get_root(self) -> ET.Element:
        """Get parsed root, parsing if needed."""
        if self.root is None:
            self.parse()
        if self.root is None:
            raise IFlowParserError("Failed to parse iFlow root element")
        return self.root
    
    def extract_section_xml(self, xpath: str) -> str:
        """Extract XML section as string."""
        root = self.get_root()
        elems = root.findall(xpath)
        return "\n".join([ET.tostring(e, encoding="unicode") for e in elems])
    
    def extract_properties_from_extension(self, elem: ET.Element) -> List[List[str]]:
        """Extract properties from extension elements."""
        props = []
        for ext in elem.findall(".//{http:///com.sap.ifl.model/Ifl.xsd}property"):
            key = ext.findtext("key")
            value = ext.findtext("value")
            if key:
                props.append([format_key(key), value if value else ""])
        return props
    
    def build_id_name_map(self) -> Dict[str, str]:
        """Build mapping of element IDs to names."""
        root = self.get_root()
        id_name = {}
        for elem in root.iter():
            id_ = elem.attrib.get("id")
            if not id_:
                continue
            name = elem.attrib.get("name")
            id_name[id_] = name if name else id_
        return id_name
    
    def extract_collaboration_xml(self) -> str:
        """Extract collaboration section XML."""
        return self.extract_section_xml(
            ".//{http://www.omg.org/spec/BPMN/20100524/MODEL}collaboration"
        )
    
    def extract_process_xml(self) -> str:
        """Extract process section XML."""
        return self.extract_section_xml(
            ".//{http://www.omg.org/spec/BPMN/20100524/MODEL}process"
        )
    
    def extract_message_flows_xml(self) -> str:
        """Extract message flows section XML."""
        return self.extract_section_xml(
            ".//{http://www.omg.org/spec/BPMN/20100524/MODEL}messageFlow"
        )
    
    def extract_security_properties(self) -> List[List[str]]:
        """Extract security properties from collaboration."""
        root = self.get_root()
        for collab in root.findall(
            ".//{http://www.omg.org/spec/BPMN/20100524/MODEL}collaboration"
        ):
            ext_elems = collab.findall(
                "{http://www.omg.org/spec/BPMN/20100524/MODEL}extensionElements"
            )
            if ext_elems:
                return self.extract_properties_from_extension(ext_elems[0])
        return []
    
    def extract_message_flows_with_names(self) -> List[Tuple[str, str, str]]:
        """Extract message flows with resolved names."""
        root = self.get_root()
        id_name = self.build_id_name_map()
        flows = []
        for msg in root.findall(
            ".//{http://www.omg.org/spec/BPMN/20100524/MODEL}messageFlow"
        ):
            source_id = msg.attrib.get("sourceRef") or ""
            target_id = msg.attrib.get("targetRef") or ""
            source_name = id_name.get(source_id, source_id)
            target_name = id_name.get(target_id, target_id)
            name = msg.attrib.get("name") or ""
            flows.append((source_name, target_name, name))
        return flows
    
    def extract_sequence_flows_with_names(self) -> List[Tuple[str, str, str]]:
        """Extract sequence flows with resolved names."""
        root = self.get_root()
        id_name = self.build_id_name_map()
        flows = []
        for seq in root.findall(
            ".//{http://www.omg.org/spec/BPMN/20100524/MODEL}sequenceFlow"
        ):
            source_id = seq.attrib.get("sourceRef") or ""
            target_id = seq.attrib.get("targetRef") or ""
            source_name = id_name.get(source_id, source_id)
            target_name = id_name.get(target_id, target_id)
            name = seq.attrib.get("name") or ""
            flows.append((source_name, target_name, name))
        return flows
    
    def get_all_processes(self) -> List[ET.Element]:
        """Get all process elements dynamically."""
        root = self.get_root()
        return root.findall(".//{http://www.omg.org/spec/BPMN/20100524/MODEL}process")
    
    def get_process_info(self, process: ET.Element) -> Dict[str, Any]:
        """Get process information including ID, name, and XML."""
        return {
            'id': process.attrib.get('id', ''),
            'name': process.attrib.get('name', process.attrib.get('id', 'Unknown')),
            'xml': ET.tostring(process, encoding="unicode"),
            'element': process
        }
    
    def get_integration_processes(self) -> List[Dict[str, Any]]:
        """Get all integration processes with their info."""
        processes = self.get_all_processes()
        return [self.get_process_info(p) for p in processes]
    
    def extract_all_processes_xml(self) -> List[Dict[str, str]]:
        """Extract all processes as list with name and XML."""
        result = []
        for process in self.get_all_processes():
            result.append({
                'id': process.attrib.get('id', ''),
                'name': process.attrib.get('name', process.attrib.get('id', 'Unknown')),
                'xml': ET.tostring(process, encoding="unicode")
            })
        return result
    
    def extract_components_from_process(self, process: ET.Element) -> List[List[str]]:
        """Extract component properties from a process element."""
        components = []
        proc_name = process.attrib.get("name", "Unknown")
        for ext_elem in process.findall(
            "{http://www.omg.org/spec/BPMN/20100524/MODEL}extensionElements"
        ):
            props = self.extract_properties_from_extension(ext_elem)
            for key, value in props:
                components.append([proc_name, key, value])
        if not components:
            components.append([proc_name, "", ""])
        return components
    
    def extract_child_properties(self, process_elem: ET.Element) -> List[Dict[str, Any]]:
        """Extract properties from child elements of a process."""
        results = []
        for child in list(process_elem):
            tag_name = child.tag.split("}")[-1]
            child_name = child.attrib.get("name", "")
            heading = f"{tag_name} {child_name}".strip()
            props = []
            for ext_elem in child:
                if ext_elem.tag.endswith("extensionElements"):
                    for prop in ext_elem:
                        if prop.tag.endswith("property"):
                            key = prop.findtext("key")
                            value = prop.findtext("value")
                            if key:
                                props.append([format_key(key), value if value else ""])
            results.append({"heading": heading, "properties": props})
        return results
    
    def extract_sender_properties(self) -> List[List[str]]:
        """Extract sender adapter properties."""
        root = self.get_root()
        sender_props = []
        for msg in root.findall(".//bpmn2:messageFlow", NS):
            for ext_elem in msg.findall("bpmn2:extensionElements", NS):
                is_sender = False
                for prop in ext_elem.findall("ifl:property", NS):
                    key = prop.findtext("key")
                    value = prop.findtext("value")
                    if key and key.strip().lower() == "direction" and value and value.strip().lower() == "sender":
                        is_sender = True
                        break
                if is_sender:
                    for prop in ext_elem.findall("ifl:property", NS):
                        key = prop.findtext("key")
                        value = prop.findtext("value")
                        if key:
                            sender_props.append([format_key(key), value if value else ""])
        return sender_props
    
    def extract_receiver_properties(self) -> List[List[str]]:
        """Extract receiver adapter properties."""
        root = self.get_root()
        receiver_props = []
        for msg in root.findall(".//bpmn2:messageFlow", NS):
            for ext_elem in msg.findall("bpmn2:extensionElements", NS):
                is_receiver = False
                for prop in ext_elem.findall("ifl:property", NS):
                    key = prop.findtext("key")
                    value = prop.findtext("value")
                    if key and key.strip().lower() == "direction" and value and value.strip().lower() == "receiver":
                        is_receiver = True
                        break
                if is_receiver:
                    for prop in ext_elem.findall("ifl:property", NS):
                        key = prop.findtext("key")
                        value = prop.findtext("value")
                        if key:
                            receiver_props.append([format_key(key), value if value else ""])
        return receiver_props
    
    def extract_mapping_properties(self) -> List[List[List[str]]]:
        """Extract mapping activity properties."""
        root = self.get_root()
        mappings = []
        for process in root.findall(".//bpmn2:process", NS):
            for call_activity in process.findall("bpmn2:callActivity", NS):
                for ext_elem in call_activity.findall("bpmn2:extensionElements", NS):
                    for prop in ext_elem.findall("ifl:property", NS):
                        key = prop.findtext("key")
                        value = prop.findtext("value")
                        if key and value and key.strip() == "activityType" and value.strip() == "Mapping":
                            mapping_props = []
                            for p in ext_elem.findall("ifl:property", NS):
                                k = p.findtext("key")
                                v = p.findtext("value")
                                if k:
                                    mapping_props.append([k, v if v else ""])
                            mappings.append(mapping_props)
        return mappings
    
    def extract_exception_properties(self) -> List[Dict[str, Any]]:
        """Extract exception subprocess properties."""
        root = self.get_root()
        exceptions = []
        for process in root.findall(".//bpmn2:process", NS):
            for sub_proc in process.findall("bpmn2:subProcess", NS):
                found = False
                for ext_elem in sub_proc.findall("bpmn2:extensionElements", NS):
                    for prop in ext_elem.findall("ifl:property", NS):
                        key = prop.findtext("key")
                        value = prop.findtext("value")
                        if key and value and key.strip() == "activityType" and value.strip() == "ErrorEventSubProcessTemplate":
                            found = True
                            break
                    if found:
                        subproc_props = []
                        for p in ext_elem.findall("ifl:property", NS):
                            k = p.findtext("key")
                            v = p.findtext("value")
                            if k:
                                subproc_props.append([k, v if v else ""])
                        exc_data = {"subproc_props": subproc_props, "children": []}
                        for child in list(sub_proc):
                            for ext_elem_child in child.findall("bpmn2:extensionElements", NS):
                                child_props = []
                                for prop in ext_elem_child.findall("ifl:property", NS):
                                    k = prop.findtext("key")
                                    v = prop.findtext("value")
                                    if k:
                                        child_props.append([k, v if v else ""])
                                if child_props:
                                    exc_data["children"].append({
                                        "tag": child.tag.split("}")[-1],
                                        "name": child.attrib.get("name", ""),
                                        "props": child_props,
                                    })
                        exceptions.append(exc_data)
                        break
        return exceptions
    
    def extract_metadata(self) -> Dict[str, str]:
        """Extract metadata properties from iFlow."""
        root = self.get_root()
        metadata = {}
        for prop in root.findall(".//{http:///com.sap.ifl.model/Ifl.xsd}property"):
            key = prop.findtext("key")
            value = prop.findtext("value")
            if key and value:
                if key.lower() in ["componentversion", "author", "description", 
                                   "componentns", "componentswcvname", "componentswcvid"]:
                    metadata[key] = value
        return metadata
    
    def sender_props_to_xml(self) -> str:
        """Convert sender properties to XML string."""
        sender_props = self.extract_sender_properties()
        xml = "<SenderProperties>\n"
        for key, value in sender_props:
            xml += f"  <Property>\n    <Key>{key}</Key>\n    <Value>{value}</Value>\n  </Property>\n"
        xml += "</SenderProperties>"
        return xml
    
    def receiver_props_to_xml(self) -> str:
        """Convert receiver properties to XML string."""
        receiver_props = self.extract_receiver_properties()
        xml = "<ReceiverProperties>\n"
        for key, value in receiver_props:
            xml += f"  <Property>\n    <Key>{key}</Key>\n    <Value>{value}</Value>\n  </Property>\n"
        xml += "</ReceiverProperties>"
        return xml
    
    def mapping_props_to_xml(self) -> str:
        """Convert mapping properties to XML string."""
        mapping_props_list = self.extract_mapping_properties()
        xml = "<Mappings>\n"
        for idx, mapping_props in enumerate(mapping_props_list, 1):
            xml += f'  <MappingActivity id="{idx}">\n'
            for key, value in mapping_props:
                xml += f"    <Property>\n      <Key>{key}</Key>\n      <Value>{value}</Value>\n    </Property>\n"
            xml += "  </MappingActivity>\n"
        xml += "</Mappings>"
        return xml
    
    def exception_props_to_xml(self) -> str:
        """Convert exception properties to XML string."""
        exceptions = self.extract_exception_properties()
        xml = "<Exceptions>\n"
        for idx, exc in enumerate(exceptions, 1):
            xml += f'  <ExceptionSubProcess id="{idx}">\n'
            xml += "    <Properties>\n"
            for key, value in exc["subproc_props"]:
                xml += f"      <Property>\n        <Key>{key}</Key>\n        <Value>{value}</Value>\n      </Property>\n"
            xml += "    </Properties>\n"
            for child in exc["children"]:
                xml += f'    <ChildElement type="{child["tag"]}" name="{child["name"]}">\n'
                for key, value in child["props"]:
                    xml += f"      <Property>\n        <Key>{key}</Key>\n        <Value>{value}</Value>\n      </Property>\n"
                xml += "    </ChildElement>\n"
            xml += "  </ExceptionSubProcess>\n"
        xml += "</Exceptions>"
        return xml
    
    def metadata_to_xml(self) -> str:
        """Convert metadata to XML string."""
        metadata = self.extract_metadata()
        xml = "<Metadata>\n"
        for k, v in metadata.items():
            xml += f"<{k}>{v}</{k}>\n"
        xml += "</Metadata>"
        return xml
